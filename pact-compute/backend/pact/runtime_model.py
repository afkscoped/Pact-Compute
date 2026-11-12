import math
from collections import defaultdict
from statistics import mean, median


def cohort(row):
    return (row['qos'], min(row['gpu_count'], 2), row['gpu_milli'] < 1000)


def quantile(values, level):
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(level * len(ordered)) - 1))]


def successful(pods):
    return sorted((row for row in pods if row['gpu_count'] > 0 and row['runtime_proxy_s']),
                  key=lambda row: (row['arrival_relative_s'], row['source_id']))


def observed_before(rows, cutoff):
    return [row for row in rows if row['deleted_relative_s'] is not None and row['deleted_relative_s'] < cutoff]


def fit(train, calibration, coverage=.90):
    if not train or not calibration:
        raise ValueError('Runtime training and calibration each require successful lifecycle observations.')
    groups = defaultdict(list)
    target = [row['runtime_proxy_s'] for row in train]
    for row in train:
        groups[cohort(row)].append(row['runtime_proxy_s'])
    upper = {group: quantile(values, .80) for group, values in groups.items() if len(values) >= 6}
    default = quantile(target, .80)
    scores = [row['runtime_proxy_s'] - upper.get(cohort(row), default) for row in calibration]
    correction = max(0, quantile(scores, min(1, math.ceil((len(scores) + 1) * coverage) / len(scores))))
    return {'groups': upper, 'default_s': default, 'correction_s': correction, 'target_coverage': coverage,
            'baseline_s': int(median(target)), 'train_rows': len(train), 'calibration_rows': len(calibration)}


def predict(model, row):
    return model['groups'].get(cohort(row), model['default_s']) + model['correction_s']


def metrics(predictions, targets, level=.90):
    errors = [target - prediction for target, prediction in zip(targets, predictions, strict=True)]
    return {'n': len(errors), 'coverage': mean(error <= 0 for error in errors),
            'mae_s': mean(abs(error) for error in errors),
            'pinball_s': mean(max(level * error, (level - 1) * error) for error in errors),
            'mean_prediction_s': mean(predictions)}


def evaluate(pods):
    rows = successful(pods)
    first, second = round(len(rows) * .55), round(len(rows) * .75)
    calibration_start, test_start = rows[first]['arrival_relative_s'], rows[second]['arrival_relative_s']
    train = observed_before(rows[:first], calibration_start)
    calibration = observed_before(rows[first:second], test_start)
    test = rows[second:]
    model = fit(train, calibration)
    targets = [row['runtime_proxy_s'] for row in test]
    candidates = {'training_median': [model['baseline_s']] * len(test),
                  'training_p90': [quantile([r['runtime_proxy_s'] for r in train], .90)] * len(test),
                  'calibrated_group_bound': [predict(model, row) for row in test]}
    return {'method': 'grouped empirical quantiles with one-sided split calibration', 'target_coverage': .90,
            'availability_cutoffs': {'training_outcomes_before': calibration_start, 'calibration_outcomes_before': test_start},
            'split': {name: {'n': len(part), 'source_ids': [row['source_id'] for row in part],
                             'time_range': [part[0]['arrival_relative_s'], part[-1]['arrival_relative_s']]}
                      for name, part in [('train', train), ('calibration', calibration), ('test', test)]},
            'model': {**model, 'groups': [{'qos': group[0], 'gpu_count_band': group[1], 'fractional': group[2], 'base_s': bound}
                                        for group, bound in sorted(model['groups'].items())]},
            'comparison': {name: metrics(values, targets) for name, values in candidates.items()},
            'observations': [{'source_id': row['source_id'], 'actual_proxy_s': target,
                              **{name: values[index] for name, values in candidates.items()}}
                             for index, (row, target) in enumerate(zip(test, targets, strict=True))]}
