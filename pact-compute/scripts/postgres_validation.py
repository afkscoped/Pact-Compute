"""Supervise an official portable PostgreSQL server used only by local tests."""
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import uuid
from validation_manifest import capture

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT.parent / 'reports' / 'final-validation'


def main():
    tested_source = capture()
    binaries = ROOT / '.local' / 'postgres-runtime' / 'pgsql' / 'bin'
    run = ROOT / '.local' / 'validation' / ('postgres-' + uuid.uuid4().hex[:10])
    run.mkdir(parents=True)
    flags = {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    with (REPORTS / 'postgres-bootstrap.log').open('w', encoding='utf-8') as log:
        def command(name, *args):
            subprocess.run([str(binaries / (name + '.exe')), *args], stdout=log, stderr=subprocess.STDOUT,
                           check=True, **flags)
        command('initdb', '-D', str(run / 'data'), '-U', 'pact_validation', '--encoding=UTF8', '--no-locale', '--auth=trust')
        command('pg_ctl', '-D', str(run / 'data'), '-l', str(run / 'server.log'),
                '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start')
        try:
            database = 'pact_validation_' + uuid.uuid4().hex[:12]
            command('createdb', '-h', '127.0.0.1', '-p', str(port), '-U', 'pact_validation', database)
            url = f'postgresql+pg8000://pact_validation@127.0.0.1:{port}/{database}'
            env = {**os.environ, 'PACT_TEST_POSTGRES_URL': url, 'PACT_DATABASE_URL': url,
                   'PACT_DB_TLS': '0', 'PACT_STATE_DIR': str(run / 'state'), 'PYTHONUTF8': '1',
                   'PYTHONPATH': str(ROOT / 'backend'), 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
                   'GROQ_API_KEY': '', 'PACT_LLM_API_KEY': ''}
            for target in ('0002', 'head'):
                subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', target], env=env, cwd=ROOT,
                               stdout=log, stderr=subprocess.STDOUT, check=True)
            with (REPORTS / 'postgres-tests.log').open('w', encoding='utf-8') as output:
                result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/postgres', '-q', '-ra', '-p', 'no:cacheprovider',
                                         '--basetemp=' + str(run / 'pytest-temp'),
                                         '--junitxml=' + str(REPORTS / 'postgres-pytest.xml')], cwd=ROOT, env=env,
                                        stdout=output, stderr=subprocess.STDOUT)
            restore_status = 'NOT RUN: integration tests failed'
            if result.returncode == 0:
                # No writers remain. Copy state (objects and signing material)
                # before the DB snapshot so every reference has matching bytes.
                shutil.copytree(run / 'state', run / 'restored-state')
                command('pg_dump', '-h', '127.0.0.1', '-p', str(port), '-U', 'pact_validation',
                        '-Fc', '-f', str(run / 'snapshot.dump'), database)
                restored_db = database + '_restored'
                command('createdb', '-h', '127.0.0.1', '-p', str(port), '-U', 'pact_validation', restored_db)
                command('pg_restore', '-h', '127.0.0.1', '-p', str(port), '-U', 'pact_validation',
                        '-d', restored_db, '--no-owner', str(run / 'snapshot.dump'))
                restored_env = {**env, 'PACT_DATABASE_URL': url.rsplit('/', 1)[0] + '/' + restored_db,
                                'PACT_STATE_DIR': str(run / 'restored-state')}
                with (REPORTS / 'postgres-restore.log').open('w', encoding='utf-8') as restore_log:
                    for args in (['artifacts-verify'], ['verify', str(run / 'restored-state' / 'restore-evidence.json')]):
                        subprocess.run([sys.executable, '-m', 'pact.cli', *args], cwd=ROOT, env=restored_env,
                                       stdout=restore_log, stderr=subprocess.STDOUT, check=True)
                restore_status = 'PASS: pg_dump/pg_restore, matching artifact bytes and original signature verified in cold subprocesses'
            (REPORTS / 'postgres-summary.json').write_text(json.dumps({'exit_code': result.returncode,
                'engine': 'PostgreSQL portable 18.7', 'host': 'loopback disposable database',
                'migrations': '0002 then head', 'restore': restore_status,
                'source': tested_source, 'source_unchanged': tested_source == capture(),
                'command': 'python scripts/postgres_validation.py'}, indent=2) + '\n', encoding='utf-8')
            print(f'PostgreSQL test exit {result.returncode}')
            return result.returncode or int(tested_source != capture())
        finally:
            command('pg_ctl', '-D', str(run / 'data'), '-m', 'fast', '-w', 'stop')


if __name__ == '__main__':
    raise SystemExit(main())
