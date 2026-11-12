"""Run the real local browser/GPU suite with isolated state and supervised children.

Uses a separate loopback port. Never attaches
to an existing listener. No credentials or tokens are included in report output.
"""
import json
import hashlib
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from validation_manifest import capture

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT.parent / 'reports' / 'final-validation'
STATE = ROOT / '.local' / 'validation' / 'browser'


def main():
    tested_source = capture()
    STATE.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    # Fail before bootstrapping if the required local port is occupied.
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 8766))
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONPATH=str(ROOT / 'backend'), PACT_STATE_DIR=str(STATE),
               PACT_DATABASE_URL='sqlite:///' + (STATE / 'browser.db').as_posix(), PACT_DB_TLS='0',
               PACT_URL='http://127.0.0.1:8766', PACT_TEST_URL='http://127.0.0.1:8766',
               PACT_GPU_PYTHON=str(ROOT / '.gpu-venv' / 'Scripts' / 'python.exe'), PACT_GPU_ENGINE='driver',
               PACT_TEST_VRAM_GIB='3',
               GROQ_API_KEY='', PACT_LLM_API_KEY='', PACT_ARTIFACT_BACKEND='local', PACT_SECURE_COOKIE='0')
    for name in ('PACT_RUNNER_TOKEN', 'PACT_ADMIN_PASSWORD', 'PACT_SIGNING_SECRET', 'PACT_RUNNER_ID'):
        env.pop(name, None)
    weights = STATE / 'torch' / 'hub' / 'checkpoints' / 'mobilenet_v3_large-5c1a4163.pth'
    if not weights.is_file():
        raise RuntimeError('Prepare the approved GPU weights in validation/browser before running this suite')
    env['PACT_MODEL_WEIGHTS_SHA256'] = hashlib.sha256(weights.read_bytes()).hexdigest()
    for command in ('init', 'import', 'market-demo'):
        process = subprocess.run([sys.executable, '-m', 'pact.cli', command], cwd=ROOT, env=env,
                                 capture_output=True, text=True)
        if process.returncode:
            raise RuntimeError(f'Local bootstrap {command} failed; no services launched')
    source = ROOT / '.local' / 'validation' / 'research' / 'evaluations'
    if source.exists():
        shutil.copytree(source, STATE / 'evaluations', dirs_exist_ok=True)
    children, streams = [], []
    try:
        for name, command in [('api', ['uvicorn', 'pact.api:app', '--host', '127.0.0.1', '--port', '8766']),
                              ('worker', ['pact.worker']), ('runner', ['pact.runner'])]:
            stream = (STATE / f'{name}.log').open('w', encoding='utf-8')
            streams.append(stream)
            children.append(subprocess.Popen([sys.executable, '-m', *command], cwd=ROOT, env=env,
                            stdout=stream, stderr=subprocess.STDOUT,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)))
        for attempt in range(60):
            try:
                with urlopen(env['PACT_URL'] + '/api/health', timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError('Isolated local API did not become healthy')
        log = REPORTS / 'browser-e2e.log'
        npm = 'npm.cmd' if os.name == 'nt' else 'npm'
        began = time.monotonic()
        with log.open('w', encoding='utf-8') as output:
            result = subprocess.run([npm, 'run', 'test:e2e', '--', '--reporter=json'], cwd=ROOT / 'frontend',
                                    env=env, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode == 0:
            from runtime_recovery import exercise
            exercise(ROOT, STATE, REPORTS, env, children, streams)
            with (REPORTS / 'performance-http.log').open('w', encoding='utf-8') as output:
                subprocess.run([sys.executable, 'scripts/http_performance.py'], cwd=ROOT, env=env,
                               stdout=output, stderr=subprocess.STDOUT, check=True)
        (REPORTS / 'browser-summary.json').write_text(json.dumps({'exit_code': result.returncode,
            'seconds': time.monotonic() - began, 'command': 'python scripts/browser_validation.py',
            'state': str(STATE), 'log': log.name, 'source': tested_source,
            'source_unchanged': tested_source == capture()}, indent=2) + '\n', encoding='utf-8')
        print(f'Browser suite exit {result.returncode}; evidence {log.name}')
        return result.returncode or int(tested_source != capture())
    finally:
        for process in reversed(children):
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for stream in streams:
            stream.close()


if __name__ == '__main__':
    raise SystemExit(main())
