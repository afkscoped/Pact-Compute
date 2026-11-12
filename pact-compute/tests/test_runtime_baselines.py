import hashlib
import json
import math
import random

import pytest

from pact import runtime_baselines as rb
from pact import runtime_model
from pact.live import predicted_seconds


def synthetic(n=120, seed=3):
    rng = random.Random(seed)
    pods = []
    for i in range(n):
        arrival = 1000 + i * 100
        run = math.exp(rng.gauss(7, 1.2))
        pods.append({'source_id': f'p{i}', 'arrival_relative_s': arrival, 'scheduled_relative_s': arrival + 5,
                     'deleted_relative_s': arrival + 5 + run, 'phase': 'Succeeded', 'qos': rng.choice(['LS', 'Burstable']),
                     'gpu_count': rng.choice([1, 1, 1, 8]), 'gpu_milli': 1000, 'gpu_models': rng.choice([[], ['T4'], ['G2']]),
                     'host_ram_mib': 1024, 'cpu_milli': 4000, 'runtime_proxy_s': run})
    return pods


def test_live_runtime_formula_is_unchanged():
    assert [predicted_seconds(n) for n in (1, 4, 16)] == [41, 50, 86]


def test_split_is_chronological_and_leak_free():
    train, calibration, test, cutoffs = rb.frozen_split(synthetic())
    assert max(r['arrival_relative_s'] for r in train) < min(r['arrival_relative_s'] for r in calibration) <= max(r['arrival_relative_s'] for r in calibration) < min(r['arrival_relative_s'] for r in test)
    assert all(r['deleted_relative_s'] < cutoffs['train_outcomes_before'] for r in train)
    assert all(r['deleted_relative_s'] < cutoffs['calibration_outcomes_before'] for r in calibration)
    ids = lambda rows: {r['source_id'] for r in rows}
    assert not (ids(train) & ids(calibration)) and not (ids(calibration) & ids(test)) and not (ids(train) & ids(test))


def test_conformal_quantile_and_wilson_helpers():
    assert rb.conformal_quantile(list(range(1, 10))) == 9            # n=9 -> rank ceil(10*.9)=9
    assert rb.conformal_quantile([1, 2, 3]) == math.inf             # too few residuals cannot support 90%
    low, high = rb.wilson(9, 10)
    assert 0.55 < low < 0.9 < high <= 1
    assert rb.wilson(0, 0) == [None, None]


def test_linear_solver_recovers_known_coefficients():
    assert rb.solve([[2, 0], [0, 4]], [6, 8]) == pytest.approx([3, 2])
    with pytest.raises(ValueError):
        rb.solve([[1, 1], [1, 1]], [1, 2])


def test_synthetic_evaluation_is_deterministic_and_reports_every_slice():
    first, second = rb.evaluate(synthetic()), rb.evaluate(synthetic())
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert len(first['candidates']) == 6
    for result in first['candidates'].values():
        assert set(result['by_slice']) == {'gpu_model_request', 'gpu_count'}
        assert set(result['by_slice']['gpu_model_request']) >= {'all', 'T4', 'unconstrained model'}
        assert all(0 <= row['coverage'] <= 1 and row['median_width_s'] > 0 for groups in result['by_slice'].values() for row in groups.values())


def test_too_little_data_is_refused():
    with pytest.raises(ValueError):
        rb.evaluate(synthetic(20))


def test_real_snapshot_artifacts_are_reproducible_and_hash_verified(tmp_path):
    from pact import datasets
    card = datasets.import_sources()
    _, pods, _, _ = datasets.read_snapshot(card['id'])
    first, manifest = rb.run(tmp_path / 'a', pods, card['id'])
    second, again = rb.run(tmp_path / 'b', pods, card['id'])
    assert manifest == again and first == second
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((tmp_path / 'a' / name).read_bytes()).hexdigest() == digest
        assert (tmp_path / 'a' / name).read_bytes() == (tmp_path / 'b' / name).read_bytes()
    assert first['split']['sizes'] == {'train': 102, 'calibration': 37, 'test': 46}
    existing = runtime_model.evaluate(pods)['split']
    assert first['split']['time_ranges']['test'] == existing['test']['time_range']
    assert (first['snapshot_id'], first['target_coverage']) == (card['id'], .90)
