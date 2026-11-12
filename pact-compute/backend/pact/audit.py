from collections import Counter, defaultdict
from statistics import median

from .policy import exceeds


def compliance(job, policy, events, attempts):
    started = next((event for event in events if event.kind == 'JobStarted'), None)
    dispatch = next((event for event in events if event.kind == 'JobDispatched'), None)
    finished = next((event for event in reversed(events) if event.kind == 'JobFinished'), None)
    result = attempts[-1].result or {} if attempts else {}
    findings = []
    lifecycle = {'id': 'approval', 'rule': 'approval', 'expected': 'An approved revision predates dispatch',
                 'observed': policy.status, 'evidence': [dispatch.seq] if dispatch else []}
    lifecycle['status'] = ('pass' if policy.approved_at and policy.approved_at <= dispatch.at else 'fail') if dispatch else 'unknown'
    findings.append(lifecycle)
    for rule in policy.rules:
        key, target = rule['kind'], rule['value']
        observed = None
        compliant = None
        evidence = []
        if key in {'min_vram_mib', 'gpu_model', 'grid_zone', 'gpu_count', 'carbon_limit_g', 'max_rate_cents'} and dispatch:
            evidence = [dispatch.seq]
            if key == 'min_vram_mib':
                observed = dispatch.details['vram_mib']
                compliant = observed >= target
            elif key == 'gpu_model':
                observed = dispatch.details['device']
                compliant = target.lower() in observed.lower()
            elif key == 'grid_zone':
                observed = dispatch.details.get('zone')
                compliant = observed == target
            elif key == 'gpu_count':
                observed = job.decision['gpu_count']
                compliant = observed == target
            elif key == 'carbon_limit_g':
                observed = dispatch.details.get('estimated_carbon_g')
                compliant = None if observed is None else not exceeds(policy.rules, key, observed)
            elif key == 'max_rate_cents':
                observed = job.decision['rate_cents']
                compliant = not exceeds(policy.rules, key, observed)
        elif key in {'deadline_seconds', 'deadline_utc'} and finished:
            evidence = [finished.seq]
            observed = round(finished.at - job.created_at, 3) if key == 'deadline_seconds' else finished.at
            compliant = finished.details['status'] == 'succeeded' and observed <= target
        elif key == 'max_deferral_seconds' and started and job.spec['flexible']:
            evidence = [started.seq]
            observed = round((job.start_after if target == 0 else started.at) - job.created_at, 3)
            compliant = observed <= target
        elif key == 'max_charge_cents' and finished:
            evidence = [finished.seq]
            observed = result.get('charged_cents')
            compliant = observed is not None and not exceeds(policy.rules, key, observed)
        elif key == 'report_required' and finished:
            evidence = [finished.seq]
            observed = {'board_energy_kwh': result.get('gpu_energy_kwh'), 'samples': result.get('power_samples', 0),
                        'coverage': result.get('telemetry_coverage', 0)}
            compliant = observed['board_energy_kwh'] is not None and observed['coverage'] >= 0.5
        if key == 'prefer_low_carbon' or (key == 'max_deferral_seconds' and not job.spec['flexible']):
            status = 'informational'
        else:
            status = 'unknown' if compliant is None else ('pass' if compliant else 'fail')
        findings.append({'id': key, 'rule': key, 'expected': target, 'observed': observed, 'status': status,
                         'source_span': [rule['start'], rule['end']], 'evidence': evidence})
    return findings


def action(row, prev):
    if not prev:
        return 'open'
    delta = row['price'] - prev['price']
    return 'raise' if delta >= 12 else ('cut' if delta <= -12 else 'hold')


def context(row, previous_rival, earlier_rival):
    if row['pressure'] >= 0.9:
        return 'scarcity'
    if earlier_rival is not None and previous_rival is not None and previous_rival < earlier_rival - 15:
        return 'rival_undercut'
    return 'normal'


def state_name(history, row):
    if row['context'] == 'scarcity':
        return 'scarcity'
    if row['context'] == 'rival_undercut':
        return 'after_undercut'
    if history and history[-1]['action'] == 'cut':
        return 'recovery'
    return 'steady'


def learned_transducer(series):
    """Merge short histories with the same observable context and action distribution."""
    fit = max(4, int(len(series) * .65))
    counts = defaultdict(Counter)
    for i, row in enumerate(series[:fit]):
        counts[state_name(series[:i], row)][row['action']] += 1
    aliases = {}
    profiles = {}
    for state, stats in sorted(counts.items()):
        total = sum(stats.values())
        distribution = {a: stats[a] / total for a in ('open', 'hold', 'raise', 'cut')}
        matches = [name for name, profile in profiles.items() if name != 'scarcity' and state != 'scarcity'
                   and sum(abs(distribution[a] - profile[a]) for a in distribution) <= .25]
        aliases[state] = matches[0] if matches else state
        if not matches:
            profiles[state] = distribution
    edges = defaultdict(list)
    correct = 0
    covered = 0
    for i, row in enumerate(series):
        raw = state_name(series[:i], row)
        label = aliases.get(raw, raw)
        row['state'] = label
        if i:
            edges[series[i - 1]['state'], label, row['action']].append(row['round'])
        if i >= fit and raw in counts:
            covered += 1
            correct += counts[raw].most_common(1)[0][0] == row['action']
    return {'states': sorted({row['state'] for row in series}),
            'transitions': [{'from': a, 'to': b, 'action': c, 'count': len(rounds), 'rounds': rounds[:12]}
                            for (a, b, c), rounds in sorted(edges.items())],
            'heldout_accuracy': correct / covered if covered else None, 'heldout_coverage': covered / max(1, len(series) - fit)}


def analyze_offers(rounds):
    providers = sorted({offer['provider'] for frame in rounds for offer in frame['offers']})
    result = []
    for provider in providers:
        series = []
        rival = []
        for frame in rounds:
            own = next((offer for offer in frame['offers'] if offer['provider'] == provider), None)
            competitor = [o['price'] for o in frame['offers'] if o['provider'] != provider]
            if own:
                row = {'round': frame['round'], 'price': own['price'], 'cost': own['cost'],
                       'pressure': frame['pressure']}
                row['action'] = action(row, series[-1] if series else None)
                row['context'] = context(row, rival[-1] if rival else None, rival[-2] if len(rival) > 1 else None)
                series.append(row)
            rival.append(min(competitor) if competitor else None)
        graph = learned_transducer(series)
        exposed = [row for row in series if row['context'] == 'rival_undercut']
        control = [row for row in series if row['context'] == 'normal']
        response = []
        for i, row in enumerate(series):
            if row not in exposed or row['action'] != 'cut':
                continue
            recovery = next((other for other in series[i + 1:i + 5] if other['action'] == 'raise' and other['context'] != 'scarcity'), None)
            if recovery:
                response.append({'undercut_response_round': row['round'], 'recovery_round': recovery['round']})
        normal_rate = sum(row['action'] == 'cut' for row in control) / len(control) if control else None
        exposure_rate = len(response) / len(exposed) if exposed else None
        enough = len(exposed) >= 2 and len(control) >= 5
        flag = enough and len(response) >= 2 and exposure_rate >= normal_rate + .25
        result.append({'provider': provider, **graph, 'status': 'review' if flag else ('clear' if enough else 'insufficient_evidence'),
                       'motifs': response, 'exposures': len(exposed), 'matched_controls': len(control),
                       'baseline_markup': median(row['price'] / row['cost'] for row in series) >= 1.45,
                       'summary': 'Repeated price cuts after rival undercuts followed by recovery.' if flag else
                       'The event sequence did not meet the minimum support and response criteria.'})
    return result
