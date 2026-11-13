"""Evidence and estimates for a marketplace quote."""

import math
from statistics import median

from sqlalchemy import select

from . import datasets
from .carbon import estimate
from .db import Attempt, CapacityOffer, Job
from .pricing_model import action

REPLAY_POWER_W = 150
DEMO_GRID_BOUNDARY = 1759435200  # 2 October 2025, 20:00 UTC
MIN_RUNTIME_SAMPLES = 5


def runtime_bound(observations):
    ordered = sorted(observations)
    p90 = ordered[math.ceil(.90 * len(ordered)) - 1]
    return max(10, math.ceil(p90 + 5)), p90


def runtime_plan(db, org, runner_id, spec, baseline):
    """Estimate from completed jobs with the same buyer, GPU, workload and batch size."""
    rows = db.execute(
        select(Job.spec, Attempt.result).join(Job, Job.id == Attempt.job_id)
        .where(Job.org_id == org, Attempt.runner_id == runner_id, Attempt.status == 'succeeded')
        .order_by(Attempt.finished_at.desc()).limit(100)
    )
    observations = []
    for saved, result in rows:
        duration = (result or {}).get('duration_s')
        if (saved.get('template') == spec.template and saved.get('sample_count') == spec.sample_count
                and (result or {}).get('artifact_id') and type(duration) in (int, float)
                and 0 < duration <= 86400):
            observations.append(duration)
        if len(observations) >= 30:
            break
    plan = {'method': 'fixed', 'baseline_s': baseline, 'runtime_s': baseline,
            'sample_count': len(observations), 'observed_median_s': round(median(observations), 2) if observations else None,
            'minimum_samples': MIN_RUNTIME_SAMPLES}
    if len(observations) >= MIN_RUNTIME_SAMPLES:
        estimate_s, p90 = runtime_bound(observations)
        plan.update(method='measured_p90', runtime_s=estimate_s, observed_p90_s=round(p90, 2))
    # Evaluate each later observation using only earlier completed jobs.
    chronological = list(reversed(observations))
    pairs = [(runtime_bound(chronological[:i])[0], chronological[i])
             for i in range(MIN_RUNTIME_SAMPLES, len(chronological))]
    if pairs:
        n = len(pairs)
        plan['backtest'] = {
            'n': n,
            'fixed_mae_s': round(sum(abs(baseline - actual) for _, actual in pairs) / n, 2),
            'quote_mae_s': round(sum(abs(predicted - actual) for predicted, actual in pairs) / n, 2),
            'fixed_coverage': sum(actual <= baseline for _, actual in pairs) / n,
            'quote_coverage': sum(actual <= predicted for predicted, actual in pairs) / n,
        }
    return plan


def energy_plan(candidate, duration):
    """Use the verified envelope for the live estimate, with full forecast coverage."""
    if not candidate.get('forecast_intervals') or not candidate.get('power_bound_w'):
        return None
    return estimate({'intervals': candidate['forecast_intervals']},
                    candidate['start'], candidate['start'] + duration, candidate['power_bound_w'])


def price_history(db, offer):
    rows = db.scalars(select(CapacityOffer).where(CapacityOffer.org_id == offer.org_id,
                     CapacityOffer.runner_id == offer.runner_id)
                     .order_by(CapacityOffer.created_at.desc(), CapacityOffer.id.desc()).limit(16)).all()
    history = []
    for row in reversed(rows):
        transition = action(history[-1]['rate_cents'], row.rate_cents) if history else 'open'
        history.append({'at': row.created_at, 'rate_cents': row.rate_cents, 'action': transition})
    return history


def clause_evidence(policy, candidate, flexible, now):
    observed = {
        'min_vram_mib': candidate.get('vram_mib'),
        'gpu_count': candidate.get('gpu_count'),
        'gpu_model': candidate.get('device'),
        'grid_zone': candidate.get('zone'),
        'max_charge_cents': candidate.get('envelope_cents'),
        'max_rate_cents': candidate.get('rate_cents'),
        'carbon_limit_g': candidate.get('estimated_carbon_g'),
    }
    if 'start' in candidate:
        observed['max_deferral_seconds'] = round(candidate['start'] - now)
        # The scheduler allows an extra dispatch window in the deadline check.
        finish = candidate['start'] + candidate['runtime_s'] + 10
        observed['deadline_seconds'] = round(finish - now)
        observed['deadline_utc'] = finish
    rows = []
    for rule in policy.rules:
        kind = rule['kind']
        start, end = rule.get('start'), rule.get('end')
        reasons = [reason['message'] for reason in candidate['reasons'] if reason['rule'] == kind]
        if kind == 'report_required':
            status = 'after_execution'
        elif kind == 'prefer_low_carbon':
            status = 'preference'
        elif kind == 'max_deferral_seconds' and not flexible:
            status = 'not_requested'
        else:
            status = 'blocked' if reasons else 'eligible'
        rows.append({'kind': kind, 'source': policy.source[start:end] if start is not None and end is not None else None,
                     'observed': observed.get(kind), 'status': status, 'reasons': reasons})
    return rows


def historical_signal(now):
    """Replay a fixed GB window with a day-ago planning signal, as in the research replay."""
    try:
        cards = datasets.available()
        if not cards:
            return None
        card, _, _, carbon = datasets.read_snapshot(cards[0]['id'])
    except (OSError, ValueError):
        return None
    # 19:58 UTC, two minutes before the next half-hour at the demo anchor.
    anchor = next((i for i, row in enumerate(carbon) if row['start'] == DEMO_GRID_BOUNDARY), None)
    if anchor is None or anchor < 49:
        return None
    clock = carbon[anchor]['start'] - 120
    shift = now - clock
    observed = []
    predicted = []
    for i in range(anchor - 1, min(len(carbon), anchor + 48)):
        row = carbon[i]
        interval = {'start': row['start'] + shift, 'end': row['end'] + shift}
        observed.append({**interval, 'intensity': row['actual_g_per_kwh']})
        predicted.append({**interval, 'intensity': carbon[min(i - 48, anchor - 2)]['actual_g_per_kwh']})
    return {'forecast': {'intervals': predicted, 'source': 'NESO GB historical replay', 'retrieved_at': now},
            'observed': {'intervals': observed}, 'snapshot_id': card['id'], 'clock': clock}


def replay_comparison(result, signal, now, power):
    feasible = [row for row in result['candidates'] if not row['reasons'] and row['estimated_carbon_g'] is not None]
    if not feasible:
        return None
    earliest = min(feasible, key=lambda row: row['start'])
    selected = min(feasible, key=lambda row: (row['estimated_carbon_g'], row['start']))

    def slot(row):
        end = row['start'] + row['runtime_s']
        predicted = estimate(signal['forecast'], row['start'], end, power)
        actual = estimate(signal['observed'], row['start'], end, power)
        return {'historical_start': signal['clock'] + row['start'] - now, 'delay_s': round(row['start'] - now),
                'predicted_g': round(predicted, 4) if predicted is not None else None,
                'scored_g': round(actual, 4) if actual is not None else None}

    return {'snapshot_id': signal['snapshot_id'], 'power_w': power, 'earliest': slot(earliest),
            'selected': slot(selected), 'alternatives': len(feasible)}
