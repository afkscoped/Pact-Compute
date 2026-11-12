"""Run isolated local release checks and retain commands, logs and return codes.

Use the project's Python: python scripts/validate.py baseline|final|research.
No .env values are read by this driver; database/provider settings are overridden.
"""
import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path
import subprocess
import sys
import time
import uuid
from validation_manifest import capture

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
REPORTS = REPO / 'reports' / 'final-validation'


def datasets(restore=False):
    source = REPO / 'PACT-Compute-data-preflight'
    rows = json.loads((source / 'download-manifest.json').read_text(encoding='utf-8-sig'))
    checks = []
    for row in rows:
        path = source / row['file']
        data = path.read_bytes() if path.is_file() else b''
        before = hashlib.sha256(data).hexdigest()
        repaired = False
        if before != row['sha256'] and restore:
            relative = path.relative_to(REPO).as_posix()
            approved = subprocess.check_output(['git', 'show', f'HEAD:{relative}'], cwd=REPO)
            # Never overwrite user changes, and never change the approved manifest.
            if hashlib.sha256(approved).hexdigest() != row['sha256']:
                raise RuntimeError(f'Git blob is not manifest-approved: {relative}')
            if data.replace(b'\r\n', b'\n') != approved.replace(b'\r\n', b'\n'):
                raise RuntimeError(f'Preserving non-line-ending local changes: {relative}')
            path.write_bytes(approved)
            data, repaired = approved, True
        digest = hashlib.sha256(data).hexdigest()
        checks.append({'file': row['file'], 'expected': row['sha256'], 'before': before,
                       'actual': digest, 'bytes': len(data), 'restored': repaired,
                       'match': digest == row['sha256']})
    REPORTS.mkdir(parents=True, exist_ok=True)
    name = 'dataset-restored.json' if restore else 'dataset-check.json'
    (REPORTS / name).write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
    print(f'Dataset integrity: {sum(c["match"] for c in checks)}/{len(checks)} match; evidence {name}', flush=True)
    return all(c['match'] for c in checks)


def main():
    global REPORTS
    parser = argparse.ArgumentParser()
    parser.add_argument('suite', choices=['baseline', 'final', 'frontend', 'research', 'datasets', 'contention'])
    parser.add_argument('--restore-datasets', action='store_true')
    parser.add_argument('--label', help='Retain a separate run without overwriting earlier evidence')
    parser.add_argument('--reports-dir', type=Path, default=REPORTS, help='Evidence destination; use a separate directory for RC checks')
    args = parser.parse_args()
    REPORTS = args.reports_dir.resolve()
    tested_source = capture()
    label = args.label or args.suite
    if not label.replace('-', '').replace('_', '').isalnum():
        parser.error('Use a simple alphanumeric run label')
    REPORTS.mkdir(parents=True, exist_ok=True)
    if args.suite == 'datasets':
        return 0 if datasets(args.restore_datasets) else 1
    env = os.environ.copy()
    state = ROOT / '.local' / 'validation' / label
    state.mkdir(parents=True, exist_ok=True)
    temporary = state / ('tmp-' + uuid.uuid4().hex[:10])
    temporary.mkdir()
    env.update(PYTHONPATH=str(ROOT / 'backend'), PYTHONUTF8='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PACT_STATE_DIR=str(state), PACT_DATABASE_URL='sqlite:///' + (temporary / 'isolated.db').as_posix(),
               PACT_SOURCE_DIR=str(REPO / 'PACT-Compute-data-preflight'), GROQ_API_KEY='', PACT_LLM_API_KEY='',
               PACT_ARTIFACT_BACKEND='local', PACT_DB_TLS='0')
    env.update(PACT_URL='http://127.0.0.1:8765', PACT_SECURE_COOKIE='0', PACT_RUNNER_GRID_ZONE='',
               PACT_SIGNING_SECRET=secrets.token_hex(32), PACT_ADMIN_PASSWORD=secrets.token_urlsafe(24),
               PACT_RUNNER_TOKEN=secrets.token_urlsafe(32))
    env.update(TMPDIR=str(temporary), TEMP=str(temporary), TMP=str(temporary))
    npm = 'npm.cmd' if os.name == 'nt' else 'npm'
    py = sys.executable
    if args.suite == 'research':
        commands = [(name, [py, '-m', 'pact.cli', *cmd], ROOT) for name, cmd in [
            ('import', ['import']), ('extraction', ['benchmark']), ('support', ['support-benchmark']),
            ('runtime', ['runtime-baselines']), ('scheduler', ['scheduler-baselines', '--seeds', '20', '--jobs', '90']),
            ('publication', ['publication-study', '--seeds', '20', '--jobs', '90'])]]
    elif args.suite == 'contention':
        env.update(PACT_CONTENTION_CASES='1000', PACT_CONTENTION_REPORT=str(REPORTS / 'contention-1000.json'))
        commands = [('capacity-1000', [py, '-m', 'pytest', 'tests/test_capacity_contention.py', '-q', '-ra', '-p', 'no:cacheprovider'], ROOT)]
    else:
        commands = [('backend', [py, '-m', 'pytest', '-q', '-ra', '-p', 'no:cacheprovider', '--junitxml=' + str(REPORTS / f'{label}-pytest.xml')], ROOT),
                    ('frontend-unit', [npm, 'test'], ROOT / 'frontend'),
                    ('frontend-build', [npm, 'run', 'build'], ROOT / 'frontend')]
        if args.suite == 'frontend':
            commands = commands[1:]
    results = []
    for name, cmd, cwd in commands:
        start = time.monotonic()
        log = REPORTS / f'{label}-{name}.log'
        print(f'Running {args.suite}/{name}', flush=True)
        # Node's esbuild-wasm shim can recurse in fs.writeSync when stderr is a
        # Windows regular file. Give children pipes, then persist exact bytes.
        process = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log.write_bytes(process.stdout)
        fatal_output = b"Unhandled 'error' event" in process.stdout or b'FATAL ERROR:' in process.stdout
        exit_code = process.returncode or int(fatal_output)
        results.append({'name': name, 'command': cmd, 'cwd': str(cwd), 'exit_code': exit_code,
                        'process_exit_code': process.returncode, 'fatal_output_detected': fatal_output,
                        'seconds': round(time.monotonic() - start, 3), 'log': log.name})
        report = {'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
                  'python': sys.version, 'suite': args.suite, 'results': results,
                  'source': tested_source, 'source_unchanged': tested_source == capture()}
        (REPORTS / f'{label}-summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(f'{name}: exit {exit_code}; {results[-1]["seconds"]}s', flush=True)
    return int(any(row['exit_code'] for row in results) or tested_source != capture())


if __name__ == '__main__':
    raise SystemExit(main())
