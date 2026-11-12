"""Accessibility-only RC checks on a fresh, non-executing local fixture server."""
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import uuid

from validation_manifest import capture

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT.parent / 'reports/release-candidate'


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    state = ROOT / '.local' / ('rc-browser-' + uuid.uuid4().hex[:8])
    state.mkdir(parents=True)
    before = capture()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 18766))
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONPATH': str(ROOT / 'backend'),
           'PACT_STATE_DIR': str(state), 'PACT_RC_STATE_DIR': str(state),
           'PACT_DATABASE_URL': 'sqlite:///' + (state / 'rc.db').as_posix(),
           'PACT_URL': 'http://127.0.0.1:18766', 'PACT_DB_TLS': '0', 'PACT_SECURE_COOKIE': '0',
           'PACT_ARTIFACT_BACKEND': 'local', 'GROQ_API_KEY': '', 'PACT_LLM_API_KEY': ''}
    # Explicit values also prevent dotenv from filling these from a private file.
    env.update(PACT_SIGNING_SECRET=secrets.token_hex(32), PACT_RUNNER_TOKEN=secrets.token_urlsafe(32),
               PACT_ADMIN_PASSWORD=secrets.token_urlsafe(24), PACT_RUNNER_ID='rc-no-runner', PACT_RUNNER_GRID_ZONE='')
    # Seed isolated role accounts only. No credentials are printed or reported.
    seed = '''
import json, secrets
from pact.db import Base, Member, Organization, engine, session
from pact.security import bootstrap, password_digest
from pact.config import STATE
Base.metadata.create_all(engine)
bootstrap()
roles = {}
with session(write=True) as db:
    for role in ('consumer', 'producer', 'reviewer', 'researcher', 'operator'):
        password = secrets.token_urlsafe(24)
        org = 'rc-' + role
        db.add(Organization(id=org, name='Release candidate ' + role))
        db.flush()
        db.add(Member(org_id=org, username=org, password=password_digest(password), role=role))
        roles[role] = {'username': org, 'password': password}
(STATE / 'rc-roles.json').write_text(json.dumps(roles), encoding='utf-8')
'''
    subprocess.run([sys.executable, '-c', seed], cwd=ROOT, env=env, check=True, capture_output=True)
    # Reuse frozen research artifacts for chart accessibility; do not rerun the study.
    study = ROOT / '.local/validation/research/evaluations'
    if study.exists():
        shutil.copytree(study, state / 'evaluations')
    process, result = None, 1
    try:
        with (state / 'api.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'pact.api:app', '--host', '127.0.0.1', '--port', '18766'],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for _ in range(60):
                try:
                    with urlopen(env['PACT_URL'] + '/api/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(.25)
            else:
                raise RuntimeError('RC API did not become healthy')
            with (REPORTS / 'accessibility-browser.log').open('w', encoding='utf-8') as output:
                command = ['npm.cmd' if os.name == 'nt' else 'npm', 'exec', 'playwright', 'test', '--', '--config=playwright.rc.config.ts', '--reporter=json']
                result = subprocess.run(command, cwd=ROOT / 'frontend', env=env, stdout=output, stderr=subprocess.STDOUT).returncode
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        report = {'exit_code': result, 'source': before, 'source_unchanged': before == capture(),
                  'scope': 'Accessibility on isolated role fixtures; no GPU, production or research rerun'}
        (REPORTS / 'accessibility-summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return result or int(before != capture())


if __name__ == '__main__':
    raise SystemExit(main())
