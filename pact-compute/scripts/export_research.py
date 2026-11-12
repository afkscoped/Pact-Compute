"""Verify repeated frozen artifacts and export figures without changing algorithms."""
import hashlib
import json
from pathlib import Path
import subprocess
import os

os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / '.local' / 'matplotlib'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT.parent / 'reports' / 'final-validation'


def main():
    first = ROOT / '.local' / 'validation' / 'research' / 'evaluations'
    second = ROOT / '.local' / 'validation' / 'research-repeat' / 'evaluations'
    files = []
    for path in sorted(first.iterdir()):
        other = second / path.name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert other.is_file() and hashlib.sha256(other.read_bytes()).hexdigest() == digest, path.name
        files.append({'file': path.name, 'sha256': digest, 'bytes': path.stat().st_size, 'repeat_identical': True})
    study = json.loads((first / 'publication-study.json').read_bytes())
    manifest = {'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'study_version': study['version'], 'dataset': study['source_card'], 'files': files,
                'configurations': {mode: body['config'] for mode, body in study['scheduler'].items()},
                'scope': study['scope']}
    (REPORTS / 'experiment-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    for name in ('publication-metrics.csv', 'publication-seeds.csv', 'runtime-baselines-slices.csv', 'scheduler-baselines.csv'):
        (REPORTS / name).write_bytes((first / name).read_bytes())
    summary = study['scheduler']['calibrated']['summary']
    arms = ['fcfs', 'edf', 'policy_only', 'carbon_aware']
    labels = ['FCFS', 'EDF', 'Policy only', 'Carbon aware']
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout='constrained')
    for axis, metric, ylabel in zip(axes, ('carbon_g', 'wait_p95_min'), ('Modeled CO₂ per run (g)', 'Mean run p95 wait (minutes)')):
        axis.bar(labels, [summary[arm][metric] for arm in arms], color=['#718797', '#718797', '#417c91', '#20734a'])
        axis.set_ylabel(ylabel)
        axis.tick_params(axis='x', labelrotation=15)
        axis.spines[['top', 'right']].set_visible(False)
    fig.suptitle('Frozen modeled replay: 20 paired seeds × 90 trace-derived jobs\nHistorical GB grid intensity; calibrated lifecycle estimates')
    fig.savefig(REPORTS / 'scheduler-tradeoff.png', dpi=180)
    fig.savefig(REPORTS / 'scheduler-tradeoff.svg')
    plt.close(fig)
    comparison = study['runtime']['comparison']
    names = ['training_median', 'training_p90', 'calibrated_group_bound']
    labels = ['Median', 'Training p90', 'Calibrated bound']
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), layout='constrained')
    axes[0].bar(labels, [100 * comparison[name]['coverage'] for name in names], color='#417c91')
    axes[0].axhline(90, color='#9e3838', linestyle='--', label='90% nominal target')
    axes[0].set_ylabel('Held-out lifecycle coverage (%)')
    axes[0].legend(fontsize=8)
    axes[1].bar(labels, [comparison[name]['pinball_s'] for name in names], color='#718797')
    axes[1].set_ylabel('p90 pinball loss (seconds; lower is better)')
    for axis in axes:
        axis.spines[['top', 'right']].set_visible(False)
        axis.tick_params(axis='x', labelrotation=15)
    fig.suptitle('Runtime proxy evaluation: 46 chronological test observations\nCoverage gains come with wider, less useful bounds')
    fig.savefig(REPORTS / 'runtime-negative-result.png', dpi=180)
    fig.savefig(REPORTS / 'runtime-negative-result.svg')
    plt.close(fig)
    print(f'{len(files)} frozen artifacts reproduced byte-for-byte; tables, manifests and figures exported')


if __name__ == '__main__':
    main()
