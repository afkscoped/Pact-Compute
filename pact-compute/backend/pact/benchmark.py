"""Deterministic policy regression corpus with labels defined independently of extraction."""

import json
from collections import Counter
from pathlib import Path

from .datasets import write_atomic
from .policy import compile_local


FAMILIES = (
    ('vram', 'Jobs need at least {gib} GiB VRAM.', lambda n: {'min_vram_mib': 1024 * (n + 1)}, ()),
    ('vram_mib', 'Minimum of {mem} MiB of GPU memory.', lambda n: {'min_vram_mib': 640 * n}, ()),
    ('relative_deadline', 'Workloads shall complete within {n} minutes of submission.', lambda n: {'deadline_seconds': n * 60}, ()),
    ('absolute_deadline', 'Jobs must finish by 2027-01-{day}T00:00:00Z.', lambda n: {'deadline_utc': 1798761600 + (n - 1) * 86400}, ()),
    ('charge', 'Total charge must not exceed {n}.25 compute credits.', lambda n: {'max_charge_cents': n * 100 + 25}, ()),
    ('exclusive_charge', 'Cost must be under {n}.5 credits.', lambda n: {'max_charge_cents': n * 100 + 50}, ()),
    ('rate', 'Maximum rate is {n} credits per GPU-hour.', lambda n: {'max_rate_cents': n * 100}, ()),
    ('deferral', 'Flexible jobs may be deferred by at most {n} minutes.', lambda n: {'max_deferral_seconds': n * 60}, ()),
    ('carbon', 'Estimated emissions must not exceed {n} g CO2 per job.', lambda n: {'carbon_limit_g': n}, ()),
    ('combined', 'Jobs require {count} GPUs.\nJobs must run only in grid zone GB.\nEnergy reporting is required.',
     lambda n: {'gpu_count': 1 + n % 8, 'grid_zone': 'GB', 'report_required': True}, ()),
    ('ambiguous', 'Jobs must finish by {n}:00.\nPrefer lower-carbon execution.', lambda n: {'prefer_low_carbon': True}, ('ambiguous_deadline',)),
    ('unsupported_exception', 'Jobs must finish within {n} minutes unless the customer has waived the deadline.\nEnergy reporting is required.',
     lambda n: {'report_required': True}, ('unsupported',)),
)


def corpus():
    for index, (family, template, expected, issues) in enumerate(FAMILIES):
        split = 'development' if index < 8 else ('validation' if index < 10 else 'holdout')
        for value in range(1, 16):
            yield {'id': f'{family}-{value:02}', 'family': family, 'split': split,
                   'source': template.format(n=value, gib=value + 1, mem=value * 640, day=f'{value:02}', count=1 + value % 8),
                   'rules': expected(value), 'issues': list(issues), 'strict': ['max_charge_cents'] if family == 'exclusive_charge' else []}


def evaluate(folder: Path):
    samples = list(corpus())
    totals = Counter()
    exact = Counter()
    failures = []
    for sample in samples:
        rules, issues = compile_local(sample['source'])
        actual = {rule.kind: rule.value for rule in rules}
        strict = sorted(rule.kind for rule in rules if rule.strict)
        codes = sorted(item['code'] for item in issues)
        totals[sample['split']] += 1
        if actual == sample['rules'] and strict == sample['strict'] and codes == sample['issues']:
            exact[sample['split']] += 1
        else:
            failures.append({'id': sample['id'], 'rules': actual, 'issues': codes, 'strict': strict})
    report = {'suite': 'synthetic-policy-regression-v1', 'examples': len(samples),
              'splits': {name: {'exact': exact[name], 'total': total} for name, total in totals.items()},
              'failures': failures, 'scope': 'Template regression suite with family-grouped splits. Independent human review is pending.'}
    write_atomic(folder / 'policy-corpus.jsonl', ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in samples).encode())
    write_atomic(folder / 'policy-evaluation.json', json.dumps(report, indent=2).encode())
    return report
