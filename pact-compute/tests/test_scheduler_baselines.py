import hashlib
import json
import random
from collections import Counter

import pytest

from pact import research, scheduler_baselines as sb


def provider(pid='p1', devices=2):
    return {'id': pid, 'devices': devices}


def option(job, start, devices, pred, occupied, quote=100, pid='p1'):
    return {'job': job, 'provider': provider(pid), 'start': start, 'slots': list(range(start, start + pred)), 'devices': tuple(devices),
            'quote': quote, 'occupied': occupied}


def job(jid, arrival, due=20, units=1000, count=1, priority='flexible'):
    return {'id': jid, 'arrival': arrival, 'due': due, 'units': units, 'count': count, 'priority': priority}


def test_arm_lists_keep_the_original_arms_and_add_the_baselines_separately():
    assert research.ARMS == ('fcfs', 'edf', 'policy_only', 'carbon_aware', 'unconstrained')
    assert research.BASELINE_ARMS == ('easy_backfill', 'edf_aging')
    assert sb.ALL_ARMS == research.ARMS + research.BASELINE_ARMS


def test_conservative_backfilling_never_delays_an_earlier_reservation():
    # Device 0 is busy for slots 0-2. Job A needs both devices, so its earliest start is slot 3.
    occupied = Counter({('p1', 0, t): 1000 for t in range(3)})
    a, b, c = job('A', 0, count=2), job('B', 1), job('C', 2)
    options = [option(a, 3, (0, 1), 2, occupied),
               option(b, 0, (1,), 2, occupied),                       # finishes at slot 2, before A starts: may backfill now
               option(b, 5, (1,), 2, occupied),
               option(c, 0, (1,), 5, occupied),                       # would still run at slot 3 and collide with A's reservation
               option(c, 5, (1,), 5, occupied)]
    chosen = research.conservative_backfill(options, tick=0)
    assert [o['job']['id'] for o in chosen] == ['B']


def test_conservative_backfilling_starts_the_head_job_when_it_fits_now():
    occupied = Counter()
    first, second = job('A', 0), job('B', 1)
    chosen = research.conservative_backfill([option(second, 0, (0,), 2, occupied), option(first, 0, (0,), 2, occupied)], tick=0)
    assert [o['job']['id'] for o in chosen] == ['A']          # arrival order wins the single device


def test_edf_with_aging_promotes_a_long_waiting_job():
    occupied = Counter()
    old, fresh = job('old', 0, due=12), job('fresh', 7, due=10)
    options = [option(fresh, 8, (0,), 1, occupied), option(old, 8, (0,), 1, occupied)]
    assert [o['job']['id'] for o in research.greedy(options, 8, 'edf')] == ['fresh']             # earlier absolute deadline
    assert [o['job']['id'] for o in research.greedy(options, 8, 'edf_aging')] == ['old']         # waited 8 slots: effective due 8 < 10


def test_plan_metrics_account_every_job_the_same_way():
    jobs = [{'id': str(i)} for i in range(4)]
    tape = [{'capacity': 2}] * 4
    place = lambda arrival, start, finish, status, due: {'arrival': arrival, 'start': start, 'finish': finish, 'status': status, 'due': due, 'charge': 200,
                                                         'carbon_g': 3.0, 'energy_kwh': .01, 'gpu_slot_units': 1000, 'violations': []}
    result = {'placements': [place(0, 0, 2, 'succeeded', 5), place(0, 2, 4, 'succeeded', 3), place(1, 1, 3, 'overrun', 9)]}
    m = sb.plan_metrics(jobs, tape, result)
    assert (m['admitted_fraction'], m['completed_fraction'], m['on_time_fraction'], m['not_admitted'], m['overruns']) == (.75, .5, .25, 1, 1)
    assert m['wait_p50_min'] == 0 and m['wait_p95_min'] == 60
    assert m['bounded_slowdown_mean'] == pytest.approx((1.0 + (2 + 2) / 2) / 2)         # (wait+run)/run for each completed job
    assert m['cost_credits'] == 6 and m['cost_per_completed'] == 3 and m['carbon_g_per_completed'] == 4.5
    assert m['gpu_utilization'] == pytest.approx(3000 / 8000)
    assert sb.plan_metrics(jobs, tape, {'placements': []})['cost_per_completed'] is None


def test_bootstrap_and_verdicts_are_conservative():
    rng = random.Random(1)
    assert sb.bootstrap([1.0, 2.0], rng) is None                       # too few pairs for an interval
    interval = sb.bootstrap([-3.0, -2.0, -4.0, -3.5, -2.5], rng)
    assert interval[1] < 0
    assert sb.verdict(-3, interval, 'lower') == 'better' and sb.verdict(-3, interval, 'higher') == 'worse'
    assert sb.verdict(0.1, [-1, 1], 'lower') == 'no clear difference' and sb.verdict(None, None, 'lower') == 'insufficient pairs'


def test_real_replay_is_deterministic_uses_shared_inputs_and_hash_verified(tmp_path):
    from pact import datasets
    card = datasets.import_sources()
    _, pods, _, carbon = datasets.read_snapshot(card['id'])
    first, manifest = sb.run(tmp_path / 'a', card, pods, carbon, seeds=2, jobs=45)
    second, again = sb.run(tmp_path / 'b', card, pods, carbon, seeds=2, jobs=45)
    assert manifest == again
    for name, digest in manifest['files'].items():
        data = (tmp_path / 'a' / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest and data == (tmp_path / 'b' / name).read_bytes() and b'\r\n' not in data
    assert json.loads((tmp_path / 'a' / 'scheduler-baselines.json').read_bytes())['version'] == sb.VERSION
    for item in first['per_seed']:
        assert set(item['arms']) == set(sb.ALL_ARMS) and len(item['inputs_sha256']) == 64
        for arm in sb.ALL_ARMS:
            assert set(item['arms'][arm]) == set(sb.METRICS)
    assert len({item['seed'] for item in first['per_seed']}) == 2
    assert set(first['value_labels']) == {'trace-derived', 'measured', 'modeled'}
    assert all(first['metrics'][name]['label'] in ('simulated', 'modeled') for name in first['metrics'])
    assert 'easy_backfill minus carbon_aware' in first['paired'] and 'edf_aging minus edf' in first['paired']
    assert all(set(row) == {'delta', 'ci95', 'pairs', 'verdict'} for row in first['paired']['easy_backfill minus edf'].values())
