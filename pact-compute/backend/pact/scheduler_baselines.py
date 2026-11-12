"""Scheduler baselines in the research replay: conservative backfilling and EDF with aging next to the existing arms.

Every arm replays the same jobs, provider inventory, offer tape, carbon window and seed, and is scored by one metric function
(`plan_metrics`) from its placements, so differences cannot come from different accounting. Results are paired per seed with
bootstrap intervals. Artifacts are written as bytes and carry a hash manifest; a rerun is byte-identical.

Value labels (see LABELS): `trace-derived` inputs come from the Alibaba pod trace (arrival order, runtimes, GPU requests, QoS);
`measured` is only the NESO grid actuals; everything else is `modeled` (provider supply and prices, job budgets and values,
runtime predictions, power model). Waits, utilization and cost are simulated outcomes, not measurements of the live platform."""
import csv
import hashlib
import io
import json
import math
import random
from pathlib import Path
from statistics import mean

from . import research
from .research import ARMS, BASELINE_ARMS, Scenario, build_jobs, offer_tape, run_arm, sub_rng

VERSION = 'scheduler-baselines-1'
ALL_ARMS = ARMS + BASELINE_ARMS
SLOT_MINUTES = 30
SLOWDOWN_BOUND_MIN = 10  # the bounded-slowdown threshold: runs shorter than this count as this long
# metric -> (direction, label, unit)
METRICS = {
    'admitted_fraction': ('higher', 'simulated', 'share of submitted jobs given a start'),
    'completed_fraction': ('higher', 'simulated', 'share of submitted jobs that finished inside their reservation'),
    'on_time_fraction': ('higher', 'simulated', 'share of submitted jobs that finished by their deadline'),
    'wait_p50_min': ('lower', 'simulated', 'minutes from arrival to start, admitted jobs'),
    'wait_p95_min': ('lower', 'simulated', 'minutes from arrival to start, admitted jobs'),
    'bounded_slowdown_mean': ('lower', 'simulated', '(wait + run) / max(run, 10 min), completed jobs, at least 1'),
    'bounded_slowdown_p95': ('lower', 'simulated', 'same, 95th percentile'),
    'gpu_utilization': ('higher', 'simulated', 'used GPU slot-units / offered GPU slot-units'),
    'cost_credits': ('lower', 'modeled', 'total buyer charge, compute credits (configured prices)'),
    'cost_per_completed': ('lower', 'modeled', 'buyer charge per completed job, credits'),
    'carbon_g': ('lower', 'modeled', 'GPU power model x measured NESO actual intensity, grams CO2'),
    'carbon_g_per_completed': ('lower', 'modeled', 'grams CO2 per completed job'),
    'energy_kwh': ('lower', 'modeled', 'GPU-only energy estimate'),
    'not_admitted': ('lower', 'simulated', 'jobs rejected or still unplaced at the evaluation boundary'),
    'overruns': ('lower', 'simulated', 'admitted jobs stopped at their reservation boundary'),
    'policy_violations': ('lower', 'simulated', 'violations of the approved agreement (none is configured here)'),
}
LABELS = {
    'trace-derived': ['job arrival order and gaps (time-scaled)', 'job runtimes (held-out successful lifecycle proxy)', 'GPU count, GPU fraction, QoS class'],
    'measured': ['NESO Great Britain actual carbon intensity series'],
    'modeled': ['provider inventory, offers, prices and costs', 'job budgets, values and urgency beyond QoS', 'runtime predictions used for reservations',
                'GPU power model', 'all scheduler outcomes (simulated)'],
}
PAIRS = [('easy_backfill', ref) for ref in ('fcfs', 'edf', 'policy_only', 'carbon_aware')] + \
        [('edf_aging', ref) for ref in ('fcfs', 'edf', 'policy_only', 'carbon_aware')] + [('easy_backfill', 'edf_aging')]


def nearest_rank(values, q):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)] if ordered else None


def plan_metrics(jobs, tape, result):
    placements = result['placements']
    n = len(jobs)
    completed = [d for d in placements if d['status'] == 'succeeded']
    waits = [(d['start'] - d['arrival']) * SLOT_MINUTES for d in placements]
    slowdowns = [max(1.0, ((d['start'] - d['arrival']) + (d['finish'] - d['start'])) * SLOT_MINUTES /
                     max((d['finish'] - d['start']) * SLOT_MINUTES, SLOWDOWN_BOUND_MIN)) for d in completed]
    capacity = sum(frame['capacity'] for frame in tape) * 1000
    cost = sum(d['charge'] for d in placements) / 100
    carbon = sum(d['carbon_g'] for d in placements)
    return {
        'admitted_fraction': len(placements) / n, 'completed_fraction': len(completed) / n,
        'on_time_fraction': sum(d['finish'] <= d['due'] for d in completed) / n,
        'wait_p50_min': nearest_rank(waits, .5), 'wait_p95_min': nearest_rank(waits, .95),
        'bounded_slowdown_mean': mean(slowdowns) if slowdowns else None, 'bounded_slowdown_p95': nearest_rank(slowdowns, .95),
        'gpu_utilization': sum(d['gpu_slot_units'] for d in placements) / capacity,
        'cost_credits': cost, 'cost_per_completed': cost / len(completed) if completed else None,
        'carbon_g': carbon, 'carbon_g_per_completed': carbon / len(completed) if completed else None,
        'energy_kwh': sum(d['energy_kwh'] for d in placements),
        'not_admitted': n - len(placements), 'overruns': len(placements) - len(completed),
        'policy_violations': sum(len(d['violations']) for d in placements),
    }


def bootstrap(values, rng, resamples=1000):
    values = [v for v in values if v is not None]
    if len(values) < 3:
        return None
    draws = sorted(mean(rng.choices(values, k=len(values))) for _ in range(resamples))
    return [draws[int(.025 * resamples)], draws[int(.975 * resamples) - 1]]


def verdict(delta, interval, direction):
    if interval is None or delta is None:
        return 'insufficient pairs'
    if interval[0] <= 0 <= interval[1]:
        return 'no clear difference'
    improved = delta > 0 if direction == 'higher' else delta < 0
    return 'better' if improved else 'worse'


def replay(card_id, pods, carbon, seeds, jobs, seed):
    scenario = Scenario(title='Scheduler baselines', dataset_id=card_id, jobs=jobs, seeds=seeds, seed=seed, scarcity=2, carbon_weight=12,
                        runtime_model='median', strategies=['cost_plus', 'scarcity', 'scripted_response', 'q_learning'])
    per_seed = []
    for index in range(seeds):
        episode_seed = seed + index
        episode_jobs, mapping = build_jobs(pods, scenario, episode_seed)
        ticks = max(job['due'] for job in episode_jobs) + 8
        anchor = sub_rng(episode_seed, 'grid-window').randrange(50, len(carbon) - ticks - 16)
        providers, tape = offer_tape(episode_jobs, scenario, episode_seed, ticks)
        fingerprint = hashlib.sha256(json.dumps([episode_jobs, providers, tape, anchor], sort_keys=True, default=str).encode()).hexdigest()
        arms = {}
        for arm in ALL_ARMS:
            result = run_arm(episode_jobs, providers, tape, carbon, anchor, scenario, [], arm, episode_seed)
            arms[arm] = plan_metrics(episode_jobs, tape, result)
        after = hashlib.sha256(json.dumps([episode_jobs, providers, tape, anchor], sort_keys=True, default=str).encode()).hexdigest()
        if after != fingerprint:
            raise RuntimeError('An arm modified the shared episode inputs.')
        per_seed.append({'seed': episode_seed, 'inputs_sha256': fingerprint, 'jobs': len(episode_jobs), 'carbon_anchor': carbon[anchor]['start'],
                         'mapping': mapping, 'arms': arms})
    return scenario, per_seed


def summarize(per_seed, seed):
    rng = sub_rng(seed, 'scheduler-baselines-bootstrap')
    summary = {}
    for arm in ALL_ARMS:
        summary[arm] = {}
        for metric in METRICS:
            values = [item['arms'][arm][metric] for item in per_seed]
            present = [v for v in values if v is not None]
            summary[arm][metric] = {'mean': mean(present) if present else None, 'ci95': bootstrap(present, rng), 'n': len(present)}
    paired = {}
    for new, reference in PAIRS:
        paired[f'{new} minus {reference}'] = {}
        for metric, (direction, _, _) in METRICS.items():
            deltas = [item['arms'][new][metric] - item['arms'][reference][metric] for item in per_seed
                      if item['arms'][new][metric] is not None and item['arms'][reference][metric] is not None]
            interval = bootstrap(deltas, rng)
            delta = mean(deltas) if deltas else None
            paired[f'{new} minus {reference}'][metric] = {'delta': delta, 'ci95': interval, 'pairs': len(deltas), 'verdict': verdict(delta, interval, direction)}
    return summary, paired


def tables(summary, paired):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(('table', 'arm_or_pair', 'metric', 'label', 'mean_or_delta', 'ci95_low', 'ci95_high', 'n_or_pairs', 'verdict'))
    for arm, metrics in summary.items():
        for metric, row in metrics.items():
            low, high = row['ci95'] or ('', '')
            writer.writerow(('arm', arm, metric, METRICS[metric][1], '' if row['mean'] is None else f"{row['mean']:.6g}", '' if low == '' else f'{low:.6g}',
                             '' if high == '' else f'{high:.6g}', row['n'], ''))
    for pair, metrics in paired.items():
        for metric, row in metrics.items():
            low, high = row['ci95'] or ('', '')
            writer.writerow(('paired', pair, metric, METRICS[metric][1], '' if row['delta'] is None else f"{row['delta']:.6g}", '' if low == '' else f'{low:.6g}',
                             '' if high == '' else f'{high:.6g}', row['pairs'], row['verdict']))
    return out.getvalue()


def run(folder, card, pods, carbon, *, seeds=20, jobs=90, seed=6021):
    scenario, per_seed = replay(card['id'], pods, carbon, seeds, jobs, seed)
    summary, paired = summarize(per_seed, seed)
    report = {
        'version': VERSION, 'engine': research.ENGINE_VERSION, 'snapshot_id': card['id'], 'config': scenario.model_dump(),
        'arms': list(ALL_ARMS), 'new_arms': list(BASELINE_ARMS),
        'definitions': {'easy_backfill': 'Conservative backfilling: jobs in arrival order each reserve their earliest feasible start from predicted runtimes; a job starts only when that start is now, so it cannot delay an earlier job. Looks 8 slots ahead.',
                        'edf_aging': 'Earliest deadline first where waiting shortens the effective deadline by one slot per two slots waited, with first-fit placement.',
                        'shared': 'All arms use the same jobs, providers, offer tape, carbon window and seed. fcfs, edf, easy_backfill and edf_aging use no policy hard rules; no agreement is configured in this study.'},
        'metrics': {name: {'direction': d, 'label': label, 'unit': unit} for name, (d, label, unit) in METRICS.items()},
        'value_labels': LABELS, 'summary': summary, 'paired': paired, 'per_seed': per_seed,
        'caveats': ['Simulated outcomes on trace-derived arrivals with modeled supply; none are measurements of the live platform.',
                    f'{seeds} seeds of {jobs} jobs each; intervals are bootstrap intervals over seeds and are wide when seeds are few.',
                    'Runtime predictions are the training median (median mode); calibrated-versus-median with backfilling is not covered here.',
                    'Fragmentation and fairness metrics from the plan are not reported by this study.']}
    body = json.dumps(report, indent=2, sort_keys=True, allow_nan=False).encode()
    table = tables(summary, paired).encode()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'scheduler-baselines.json').write_bytes(body)
    (folder / 'scheduler-baselines.csv').write_bytes(table)
    manifest = {'version': VERSION, 'snapshot_id': card['id'], 'seeds': seeds, 'jobs': jobs, 'seed': seed,
                'files': {'scheduler-baselines.json': hashlib.sha256(body).hexdigest(), 'scheduler-baselines.csv': hashlib.sha256(table).hexdigest()}}
    (folder / 'scheduler-baselines-manifest.json').write_bytes(json.dumps(manifest, indent=2, sort_keys=True).encode())
    return report, manifest
