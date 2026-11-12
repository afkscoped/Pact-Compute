"""Linux smoke against the sanitized source archive, without claiming an OCI build."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import secrets
import subprocess
import sys
import tarfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT.parent / 'reports/release-candidate'


def main():
    assert sys.platform == 'linux', 'This check requires the existing Linux runtime'
    context = ROOT / '.local/release-candidate/context.tar'
    run = ROOT / '.local' / ('rc-linux-smoke-' + uuid.uuid4().hex[:8])
    source, state = run / 'source', run / 'state'
    source.mkdir(parents=True)
    state.mkdir()
    with tarfile.open(context) as archive:
        for item in archive:
            path = PurePosixPath(item.name)
            assert item.isfile() and not path.is_absolute() and '..' not in path.parts
        archive.extractall(source, filter='data')
    project = source / 'pact-compute'
    env = {**os.environ, 'PYTHONPATH': str(project / 'backend'), 'PACT_STATE_DIR': str(state),
           'PACT_SOURCE_DIR': str(source / 'PACT-Compute-data-preflight'),
           'PACT_DATABASE_URL': 'sqlite:///' + (state / 'smoke.db').as_posix(),
           'PACT_DB_TLS': '0', 'PACT_URL': 'http://127.0.0.1:18767', 'PACT_ARTIFACT_BACKEND': 'local',
           'GROQ_API_KEY': '', 'PACT_LLM_API_KEY': ''}
    env.update(PACT_SIGNING_SECRET=secrets.token_hex(32), PACT_ADMIN_PASSWORD=secrets.token_urlsafe(24),
               PACT_RUNNER_TOKEN=secrets.token_urlsafe(32), PACT_RUNNER_GRID_ZONE='')
    commands = [([sys.executable, '-m', 'pip', 'check'], project),
                (['sh', '-n', str(source / 'deploy/entrypoint.sh')], project),
                ([sys.executable, '-m', 'alembic', 'upgrade', 'head'], project),
                ([sys.executable, '-m', 'pact.cli', 'init'], project),
                ([sys.executable, '-m', 'pact.cli', 'import'], project)]
    checks = []
    with (REPORTS / 'linux-smoke.log').open('w', encoding='utf-8') as log:
        for command, directory in commands:
            result = subprocess.run(command, cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT)
            checks.append({'command': command[1:] if command[0] == sys.executable else command, 'exit_code': result.returncode})
            if result.returncode:
                break
        if all(not row['exit_code'] for row in checks):
            code = '''
import json
from fastapi.testclient import TestClient
from pact.api import app
from pact.config import STATE
from pact.storage import store
from pact.db import sha
with TestClient(app) as client:
    assert client.get('/api/health').json()['database'] == 'sqlite'
    assert client.get('/api/v1/jobs').status_code == 401
    password = json.loads((STATE / 'local-credentials.json').read_bytes())['admin_password']
    assert client.post('/api/v1/session', json={'username': 'admin', 'password': password}).status_code == 200
    assert client.get('/api/v1/config').status_code == 200
    assert client.get('/api/v1/jobs').status_code == 200
payload = b'Linux packaging smoke fixture'
store().put(sha(payload), payload)
assert store().get(sha(payload)) == payload
print('Linux API authentication, health and artifact hash checks passed')
import subprocess, sys, threading
from pact.service import supervise
for status in (0, 7):
    assert supervise({'worker': [sys.executable, '-c', f'raise SystemExit({status})'],
                      'api': [sys.executable, '-c', 'import time; time.sleep(60)']}, poll=.02) == 1
stop = threading.Event()
timer = threading.Timer(.2, stop.set)
timer.start()
try:
    assert supervise({'api': [sys.executable, '-c', 'import time; time.sleep(60)']}, stop, poll=.02) == 0
finally:
    timer.join()
print('Linux child exit and requested-shutdown supervision checks passed')
'''
            result = subprocess.run([sys.executable, '-c', code], cwd=project, env=env, stdout=log, stderr=subprocess.STDOUT)
            checks.append({'command': 'isolated API/auth/storage and process supervision smoke', 'exit_code': result.returncode})
    report = {'platform': platform.platform(), 'python': platform.python_version(),
              'archive_sha256': hashlib.sha256(context.read_bytes()).hexdigest(), 'checks': checks,
              'status': 'PASS' if all(not row['exit_code'] for row in checks) else 'FAIL',
              'scope': 'Linux imports/migrations/API/storage, entrypoint syntax and subprocess supervision. No Docker daemon, OCI build or hosted deployment verified.'}
    (REPORTS / 'linux-smoke.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Linux package smoke:', report['status'])
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
