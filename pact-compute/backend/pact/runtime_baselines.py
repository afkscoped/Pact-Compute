"""Runtime-prediction baselines on the Alibaba snapshot, with a frozen chronological split and conformal calibration.

Research artifact only. The live job runtime formula (live.predicted_seconds: 38 + 3 x images) is not touched by this module.

Protocol (fixed before looking at test results):
  * Rows are successful GPU pod lifecycles ordered by arrival. Target = scheduled-to-deleted seconds (a lifecycle proxy).
  * Frozen split by arrival order: first 55% train, next 20% calibration (the later window), last 25% test.
    A row only counts as observed if its outcome was known before the next window began (no future outcomes leak backwards).
  * Models are fitted on train only and predict log runtime: global median, per-slice median, and a ridge-regularised linear
    model on request features. Residuals on the calibration window give split-conformal intervals (two-sided, 90% target).
  * Coverage and interval width are reported on the untouched test window per hardware slice, with a Wilson 95% interval,
    because slices are small. Nothing is tuned on the test window.
"""
import csv
import hashlib
import io
import json
import math
from statistics import mean, median

from . import runtime_model

VERSION = 'runtime-baselines-1'
TARGET_COVERAGE = .90
SPLIT_FRACTIONS = (.55, .75)  # train | calibration | test, by arrival order
MIN_SLICE_CALIBRATION = math.ceil(TARGET_COVERAGE / (1 - TARGET_COVERAGE))  # fewer residuals cannot support a 90% quantile
INDICATIVE_BELOW = 20


def model_slice(row):
    models = row['gpu_models']
    if not models:
        return 'unconstrained model'
    return 'T4' if models == ['T4'] else 'other or multiple models'


def count_slice(row):
    return 'single GPU' if row['gpu_count'] <= 1 else 'multi-GPU'


SLICERS = {'gpu_model_request': model_slice, 'gpu_count': count_slice}


def features(row):
    slice_name = model_slice(row)
    return [1.0, slice_name == 'T4', slice_name == 'unconstrained model', row['gpu_count'] > 1, row['gpu_milli'] < 1000,
            row['qos'] == 'LS', math.log1p(row['cpu_milli'] or 0), math.log1p(row['host_ram_mib'] or 0)]


def solve(matrix, vector):
    n = len(vector)
    rows = [list(map(float, matrix[i])) + [float(vector[i])] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(rows[r][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        if abs(rows[col][col]) < 1e-12:
            raise ValueError('Singular linear system.')
        for r in range(n):
            if r != col:
                factor = rows[r][col] / rows[col][col]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[col])]
    return [rows[i][n] / rows[i][i] for i in range(n)]


def fit_linear(train, ridge=1.0):
    x = [list(map(float, features(row))) for row in train]
    y = [math.log(row['runtime_proxy_s']) for row in train]
    width = len(x[0])
    means = [mean(col) for col in zip(*x)]
    scales = [math.sqrt(mean((v - m) ** 2 for v in col)) or 1.0 for col, m in zip(zip(*x), means)]
    means[0], scales[0] = 0.0, 1.0  # keep the intercept unscaled
    z = [[(v - m) / s for v, m, s in zip(row, means, scales)] for row in x]
    gram = [[sum(r[i] * r[j] for r in z) + (ridge if i == j and i > 0 else 0) for j in range(width)] for i in range(width)]
    moment = [sum(r[i] * t for r, t in zip(z, y)) for i in range(width)]
    return {'weights': solve(gram, moment), 'means': means, 'scales': scales}


def predict_linear(model, row):
    z = [(v - m) / s for v, m, s in zip(map(float, features(row)), model['means'], model['scales'])]
    return sum(w * v for w, v in zip(model['weights'], z))


def build_predictors(train):
    logs = [math.log(row['runtime_proxy_s']) for row in train]
    overall = median(logs)
    by_slice = {}
    for row in train:
        by_slice.setdefault(model_slice(row), []).append(math.log(row['runtime_proxy_s']))
    slice_medians = {name: median(values) for name, values in by_slice.items() if len(values) >= 5}
    linear = fit_linear(train)
    return {
        'global_median': lambda row: overall,
        'slice_median': lambda row: slice_medians.get(model_slice(row), overall),
        'linear_log': lambda row: predict_linear(linear, row),
    }, {'global_median_s': math.exp(overall), 'slice_median_s': {k: math.exp(v) for k, v in sorted(slice_medians.items())},
        'linear': {'features': ['intercept', 'T4 request', 'unconstrained model', 'multi-GPU', 'fractional GPU', 'QoS LS',
                                'log cpu_milli', 'log host memory'], 'weights': linear['weights'], 'ridge': 1.0}}


def conformal_quantile(scores, alpha=1 - TARGET_COVERAGE):
    ordered = sorted(scores)
    rank = math.ceil((len(ordered) + 1) * (1 - alpha))
    return math.inf if rank > len(ordered) else ordered[rank - 1]


def wilson(hits, n, z=1.96):
    if not n:
        return [None, None]
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [max(0.0, centre - spread), min(1.0, centre + spread)]


def frozen_split(pods):
    rows = runtime_model.successful(pods)
    first, second = round(len(rows) * SPLIT_FRACTIONS[0]), round(len(rows) * SPLIT_FRACTIONS[1])
    calibration_start, test_start = rows[first]['arrival_relative_s'], rows[second]['arrival_relative_s']
    train = runtime_model.observed_before(rows[:first], calibration_start)
    calibration = runtime_model.observed_before(rows[first:second], test_start)
    test = rows[second:]
    return train, calibration, test, {'train_outcomes_before': calibration_start, 'calibration_outcomes_before': test_start}


def interval(prediction, radius):
    return math.exp(prediction - radius), math.exp(prediction + radius)


def score(rows, bounds, slicer):
    groups = {'all': list(range(len(rows)))}
    for index, row in enumerate(rows):
        groups.setdefault(slicer(row), []).append(index)
    out = {}
    for name, indexes in sorted(groups.items()):
        hits = sum(bounds[i][0] <= rows[i]['runtime_proxy_s'] <= bounds[i][1] for i in indexes)
        widths = [bounds[i][1] - bounds[i][0] for i in indexes]
        out[name] = {'n': len(indexes), 'coverage': hits / len(indexes), 'coverage_wilson95': wilson(hits, len(indexes)),
                     'median_width_s': median(widths), 'mean_width_s': mean(widths),
                     'median_upper_over_lower': median(bounds[i][1] / bounds[i][0] for i in indexes),
                     'indicative_only': len(indexes) < INDICATIVE_BELOW}
    return out


def evaluate(pods):
    train, calibration, test, cutoffs = frozen_split(pods)
    if min(len(train), len(calibration), len(test)) < 10:
        raise ValueError('The snapshot has too few successful lifecycles for a train/calibration/test split.')
    predictors, parameters = build_predictors(train)
    results = {}
    for name, predictor in predictors.items():
        residuals = [abs(math.log(row['runtime_proxy_s']) - predictor(row)) for row in calibration]
        global_radius = conformal_quantile(residuals)
        by_slice = {}
        for row, residual in zip(calibration, residuals):
            by_slice.setdefault(model_slice(row), []).append(residual)
        slice_radius = {key: (conformal_quantile(values) if len(values) >= MIN_SLICE_CALIBRATION else None) for key, values in by_slice.items()}
        for calibration_name, radius_for in (('global conformal', lambda row: global_radius),
                                             ('per-slice conformal', lambda row: global_radius if slice_radius.get(model_slice(row)) is None else slice_radius[model_slice(row)])):
            bounds = [interval(predictor(row), min(radius_for(row), 50.0)) for row in test]
            point_errors = [abs(row['runtime_proxy_s'] - math.exp(predictor(row))) for row in test]
            results[f'{name} + {calibration_name}'] = {
                'model': name, 'calibration': calibration_name,
                'global_radius_log': global_radius if math.isfinite(global_radius) else None,
                'slice_radius_log': {k: v for k, v in sorted(slice_radius.items())},
                'test_mae_s': mean(point_errors), 'test_median_abs_error_s': median(point_errors),
                'overall': score(test, bounds, lambda row: 'all')['all'],
                'by_slice': {slicer_name: score(test, bounds, slicer) for slicer_name, slicer in SLICERS.items()},
            }
    ids = {name: [row['source_id'] for row in part] for name, part in (('train', train), ('calibration', calibration), ('test', test))}
    return {
        'version': VERSION, 'target_coverage': TARGET_COVERAGE, 'interval': 'two-sided split conformal on log runtime',
        'target': 'successful pod lifecycle seconds (scheduled to deleted); a proxy, not measured GPU job runtime',
        'live_formula': 'unchanged: 38 + 3 x images seconds (live.predicted_seconds)',
        'split': {'fractions': list(SPLIT_FRACTIONS), 'availability_cutoffs': cutoffs,
                  'sizes': {k: len(v) for k, v in ids.items()},
                  'time_ranges': {k: [part[0]['arrival_relative_s'], part[-1]['arrival_relative_s']]
                                  for k, part in (('train', train), ('calibration', calibration), ('test', test))},
                  'source_ids_sha256': {k: hashlib.sha256(json.dumps(v).encode()).hexdigest() for k, v in ids.items()}},
        'parameters': parameters, 'candidates': results,
        'caveats': ['Few rows: 185 successful GPU lifecycles in total, so slice results have wide uncertainty (see wilson95).',
                    'Slices under 20 test rows are marked indicative_only.',
                    'Conformal coverage is a marginal guarantee under exchangeability. Drift between windows can break it per slice.',
                    'The target is the scheduled-to-deleted time of successful pods in a production trace. It is not a measurement of image-embedding jobs on this platform.'],
    }


def slice_csv(report):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(('candidate', 'slicing', 'slice', 'n', 'coverage', 'wilson_low', 'wilson_high', 'median_width_s',
                     'median_upper_over_lower', 'indicative_only'))
    for name, result in sorted(report['candidates'].items()):
        for slicing, groups in result['by_slice'].items():
            for slice_name, row in groups.items():
                low, high = row['coverage_wilson95']
                writer.writerow((name, slicing, slice_name, row['n'], round(row['coverage'], 4), round(low, 4), round(high, 4),
                                 round(row['median_width_s'], 1), round(row['median_upper_over_lower'], 2), row['indicative_only']))
    return out.getvalue()


def run(folder, pods, snapshot_id):
    from pathlib import Path

    report = {**evaluate(pods), 'snapshot_id': snapshot_id}
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    body = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    table = slice_csv(report)
    (folder / 'runtime-baselines.json').write_bytes(body.encode())  # bytes, so the stored file matches its hash on any OS
    (folder / 'runtime-baselines-slices.csv').write_bytes(table.encode())
    manifest = {'version': VERSION, 'snapshot_id': snapshot_id,
                'files': {'runtime-baselines.json': hashlib.sha256(body.encode()).hexdigest(),
                          'runtime-baselines-slices.csv': hashlib.sha256(table.encode()).hexdigest()}}
    (folder / 'runtime-baselines-manifest.json').write_bytes(json.dumps(manifest, indent=2, sort_keys=True).encode())
    return report, manifest
