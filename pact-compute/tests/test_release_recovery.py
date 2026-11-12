"""Real SQLite schema transitions and matched backup restoration, never production."""
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

from pact.storage import StorageError, LocalStore

ROOT = Path(__file__).resolve().parents[1]


def migrate(path, state, *args):
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'backend'), 'PYTHONUTF8': '1',
           'PACT_DATABASE_URL': 'sqlite:///' + path.as_posix(), 'PACT_STATE_DIR': str(state),
           'PACT_DB_TLS': '0', 'GROQ_API_KEY': '', 'PACT_LLM_API_KEY': ''}
    result = subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_old_schema_upgrade_preserves_data_and_head_can_roll_forward(tmp_path):
    database = tmp_path / 'migrations.db'
    migrate(database, tmp_path / 'state', 'upgrade', '0002')
    with sqlite3.connect(database) as db:
        db.execute('INSERT INTO organizations (id, name) VALUES (?, ?)', ('retained-org', 'Retained original row'))
    migrate(database, tmp_path / 'state', 'upgrade', 'head')
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0007',)
        assert db.execute('SELECT name FROM organizations WHERE id=?', ('retained-org',)).fetchone() == ('Retained original row',)
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {'memberships', 'invitations', 'rate_hits', 'incident_records'} <= tables
        assert 'org_id' in {row[1] for row in db.execute('PRAGMA table_info(sessions)')}
        assert 'ix_jobs_org_created' in {row[1] for row in db.execute('PRAGMA index_list(jobs)')}
    migrate(database, tmp_path / 'state', 'downgrade', '0006')
    migrate(database, tmp_path / 'state', 'upgrade', 'head')
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT COUNT(*) FROM organizations').fetchone() == (1,)
    # Drift check against ORM metadata, not just the Alembic version string.
    migrate(database, tmp_path / 'state', 'check')


def test_matched_database_and_artifact_backup_survives_cold_restore(tmp_path):
    live = tmp_path / 'live'
    live.mkdir()
    payload = b'approved-output\x00retained-byte-for-byte'
    digest = hashlib.sha256(payload).hexdigest()
    LocalStore(live / 'artifacts').put(digest, payload)
    with sqlite3.connect(live / 'state.db') as db:
        db.execute('CREATE TABLE outputs (digest TEXT PRIMARY KEY, bytes INTEGER NOT NULL)')
        db.execute('INSERT INTO outputs VALUES (?, ?)', (digest, len(payload)))
    backup = tmp_path / 'backup'
    backup.mkdir()
    # Stop writes for this fixture. Copy object bytes before database metadata.
    shutil.copytree(live / 'artifacts', backup / 'artifacts')
    with sqlite3.connect(live / 'state.db') as source, sqlite3.connect(backup / 'state.db') as target:
        source.backup(target)
    restored = tmp_path / 'restored'
    shutil.copytree(backup, restored)
    # A new process reads the restored DB and store, without using live state.
    code = """
import hashlib, pathlib, sqlite3, sys
from pact.storage import LocalStore
root = pathlib.Path(sys.argv[1])
with sqlite3.connect(root / 'state.db') as db:
    rows = db.execute('SELECT digest, bytes FROM outputs').fetchall()
assert len(rows) == 1
for digest, size in rows:
    data = LocalStore(root / 'artifacts').get(digest)
    assert len(data) == size and hashlib.sha256(data).hexdigest() == digest
print('cold restore verified: 1 database reference, 1 matching object')
"""
    result = subprocess.run([sys.executable, '-c', code, str(restored)], capture_output=True, text=True,
                            env={**os.environ, 'PYTHONPATH': str(ROOT / 'backend')}, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    # A mismatched backup must fail verification, rather than silently serve bytes.
    store = LocalStore(restored / 'artifacts')
    path = next((restored / 'artifacts').rglob(digest))
    path.write_bytes(b'damaged restore')
    with pytest.raises(StorageError):
        store.get(digest)


def test_retry_does_not_report_success_over_a_corrupt_existing_object(tmp_path):
    payload = b'approved immutable output'
    digest = hashlib.sha256(payload).hexdigest()
    store = LocalStore(tmp_path / 'artifacts')
    store.put(digest, payload)
    store.path(digest).write_bytes(b'corrupted disk bytes')
    with pytest.raises(StorageError):
        store.put(digest, payload)


@pytest.mark.parametrize('origin,allowed', [
    ('http://127.0.0.1:8765', True), ('http://localhost:8766', True),
    ('https://pact.example:8765', False), ('http://localhost.evil:8765', False),
    ('http://localhost@evil:8765', False), ('http://localhost:8765/path', False),
    ('http://localhost:bad', False), ('http://localhost:8765?redirect=evil', False),
])
def test_demo_accounts_remain_restricted_to_local_origins(origin, allowed):
    from pact.demo import local_demo_origin
    assert local_demo_origin(origin) is allowed


def test_s3_retry_verifies_existing_bytes_instead_of_blessing_corruption():
    import boto3
    from moto import mock_aws
    from pact.storage import S3Store
    payload = b'known S3 output'
    digest = hashlib.sha256(payload).hexdigest()
    with mock_aws():
        client = boto3.client('s3', region_name='us-east-1', aws_access_key_id='testing', aws_secret_access_key='testing')
        client.create_bucket(Bucket='validation-artifacts')
        store = S3Store('validation-artifacts', client=client)
        store.put(digest, payload)
        client.put_object(Bucket=store.bucket, Key=store.key(digest), Body=b'corrupted object')
        with pytest.raises(StorageError):
            store.put(digest, payload)
