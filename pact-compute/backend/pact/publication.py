import csv
import io
import json
import random
from copy import deepcopy
from statistics import mean

from . import pricing_model, runtime_model
from .datasets import import_sources, read_snapshot, write_atomic
from .protocol import observe, presence_verdict
from .research import Scenario, experiment

VERSION = 'pact-study-2'


def fixture(kind, seed):
    # Expectations are defined by the test author, independently of the monitor.
    terms = {'quote_id': f'quote-{seed}', 'policy_id': 'reviewed-01', 'rate_cents': 120 + seed % 70,
             'offer_version': 2, 'envelope_cents': 400}
    start = seed * 100
    trace = []

    def event(name, after, **details):
        trace.append({'kind': name, 'at': start + after, 'details': details, 'seq': len(trace) + 1})

    event('QuoteIssued', 0, **terms, expires_at=start + 30)
    event('JobSubmitted', 1)
    event('MarketQuoteAccepted', 2, **terms)
    event('CapacityReserved', 3)
    event('JobDispatched', 4, policy_id='reviewed-01', attempt_id='attempt-01')
    event('JobStarted', 5, attempt_id='attempt-01')
    event('JobFinished', 8, attempt_id='attempt-01', status='succeeded', charged_cents=85)
    event('CapacityReleased', 9)
    verdict = 'fail'
    if kind == 'success':
        verdict = 'pass'
    elif kind == 'cancel_before_dispatch':
        trace = trace[:4]
        event('CancellationRequested', 4)
        event('ReservationCancelled', 5)
        event('CapacityReleased', 6)
        verdict = 'pass'
    elif kind == 'reconciled':
        trace = trace[:6]
        event('ExecutionUncertain', 6, attempt_id='attempt-01')
        event('ExecutionReconciled', 9, attempt_id='attempt-01')
        event('CapacityReleased', 10)
        verdict = 'pass'
    elif kind == 'expired_reservation':
        trace = trace[:4]
        event('ReservationExpired', 15)
        event('CapacityReleased', 16)
        verdict = 'pass'
    elif kind == 'unfinished':
        trace = trace[:6]
        verdict = 'incomplete'
    elif kind == 'expired_quote':
        trace[0]['details']['expires_at'] = start + 2
    elif kind == 'changed_terms':
        trace[2]['details']['rate_cents'] += 25
    elif kind == 'changed_policy':
        trace[4]['details']['policy_id'] = 'unreviewed'
    elif kind == 'double_dispatch':
        trace.insert(5, deepcopy(trace[4]))
    elif kind == 'charge_above_cap':
        trace[6]['details']['charged_cents'] = 490
    elif kind == 'wrong_attempt':
        trace[6]['details']['attempt_id'] = 'attempt-other'
    elif kind == 'success_without_start':
        del trace[5]
    elif kind == 'release_during_execution':
        trace[6]['kind'], trace[7]['kind'] = trace[7]['kind'], trace[6]['kind']
    return {'family': kind, 'seed': seed, 'expected': verdict, 'trace': trace}


def protocol_benchmark():
    groups = {
        'development': ('success', 'expired_quote', 'double_dispatch', 'unfinished'),
        'validation': ('reconciled', 'changed_terms', 'wrong_attempt'),
        'heldout': ('cancel_before_dispatch', 'expired_reservation', 'changed_policy', 'charge_above_cap',
                    'success_without_start', 'release_during_execution'),
    }
    result = []
    for split, families in groups.items():
        for family in families:
            for seed in range(1, 13):
                item = fixture(family, seed)
                baseline = presence_verdict(item['trace'])
                verified = observe(item['trace'], market=True)
                result.append({'split': split, **item, 'presence_baseline': baseline, 'temporal_monitor': verified['verdict'],
                               'violations': verified['violations']})
    heldout = [row for row in result if row['split'] == 'heldout']
    def metrics(name):
        return {'n': len(heldout), 'accuracy': mean(item[name] == item['expected'] for item in heldout),
                'unsafe_accepts': sum(item[name] == 'pass' and item['expected'] == 'fail' for item in heldout),
                'valid_rejects': sum(item[name] != 'pass' and item['expected'] == 'pass' for item in heldout)}
    return {'comparison': {name: metrics(name) for name in ('presence_baseline', 'temporal_monitor')},
            'split_families': groups, 'cases': result,
            'transition_coverage': sorted({step['event'] for row in result for step in observe(row['trace'], market=True)['steps']})}


def paired(a, b, field):
    pairs = [y[field] - x[field] for x, y in zip(a, b, strict=True) if x[field] is not None and y[field] is not None]
    if not pairs:
        return {'n': 0, 'delta': None, 'interval95': None}
    rng = random.Random(297)
    samples = sorted(mean(rng.choices(pairs, k=len(pairs))) for _ in range(1000)) if len(pairs) >= 3 else []
    return {'n': len(pairs), 'delta': mean(pairs), 'interval95': [samples[24], samples[974]] if samples else None}


def run(folder, *, seeds=20, jobs=90, progress=lambda _: None):
    card = import_sources()
    _, pods, _, _ = read_snapshot(card['id'])
    protocol = protocol_benchmark()
    runtime = runtime_model.evaluate(pods)
    pricing = pricing_model.evaluate(seeds=30)
    arms = {}
    for mode in ('median', 'calibrated'):
        scenario = Scenario(title='Publication replay ' + mode, dataset_id=card['id'], jobs=jobs, seeds=seeds,
                            seed=6021, scarcity=2, carbon_weight=12, runtime_model=mode,
                            strategies=['cost_plus', 'scarcity', 'scripted_response', 'q_learning'])
        result, full = experiment(scenario, [], lambda pct: progress(f'{mode} replay {pct}%') if pct % 10 == 0 else None)
        arms[mode] = {'config': scenario.model_dump(), 'summary': result['summary'],
                      'per_seed': [{'seed': item['seed'], 'mapping': item['mapping'], 'carbon_anchor': item['carbon_anchor'],
                                    'arms': {key: item['arms'][key]['metrics'] for key in item['arms']}}
                                   for item in full['episodes']],
                      'first_episode': result['first_episode'], 'paired_carbon_vs_policy': result['paired']}
    base = [item['arms']['carbon_aware'] for item in arms['median']['per_seed']]
    calibrated = [item['arms']['carbon_aware'] for item in arms['calibrated']['per_seed']]
    metrics = ('completed', 'on_time_rate', 'overruns', 'wait_p95_min', 'carbon_g', 'carbon_g_per_completed', 'energy_kwh')
    report = {'version': VERSION, 'source_card': card, 'protocol': protocol, 'pricing': pricing, 'runtime': runtime,
              'scheduler': arms, 'paired_calibrated_minus_median': {key: paired(base, calibrated, key) for key in metrics},
              'scope': ['Contract traces and pricing labels are controlled fixtures.',
                        'The runtime target is a successful-pod lifecycle proxy. It does not cover censored jobs.',
                        'Scheduling combines recorded arrivals and grid data with modeled duration, capacity, prices and power.',
                        'Paired results compare the same seeds. Availability and service still need partner validation.']}
    write_atomic(folder / 'publication-study.json', json.dumps(report, allow_nan=False, indent=2).encode())
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(('module', 'condition', 'metric', 'value'))
    for module, comparison in [('protocol', protocol['comparison']), ('pricing', pricing['classification']), ('runtime', runtime['comparison'])]:
        for condition, stats in comparison.items():
            writer.writerows((module, condition, metric, value) for metric, value in stats.items())
    for name, values in [('merged_fsm', pricing['fsm']), ('majority_action', pricing['fsm']['majority_baseline'])]:
        writer.writerows(('action_prediction', name, metric, values[metric]) for metric in ('accuracy', 'coverage', 'log_loss'))
    for mode, data in arms.items():
        for name, stats in data['summary'].items():
            writer.writerows(('scheduler', mode + '/' + name, metric, stats[metric]) for metric in metrics)
    write_atomic(folder / 'publication-metrics.csv', output.getvalue().encode())
    seed_output = io.StringIO()
    seed_writer = csv.writer(seed_output)
    seed_writer.writerow(('runtime_model', 'seed', 'scheduler', *metrics))
    for mode, data in arms.items():
        for episode in data['per_seed']:
            seed_writer.writerows((mode, episode['seed'], name, *(stats[metric] for metric in metrics))
                                  for name, stats in episode['arms'].items())
    write_atomic(folder / 'publication-seeds.csv', seed_output.getvalue().encode())
    return report
