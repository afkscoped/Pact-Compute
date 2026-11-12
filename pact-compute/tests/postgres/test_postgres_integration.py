"""Opt-in tests restricted to a locally created disposable database."""
from concurrent.futures import ThreadPoolExecutor
import os
import json
import threading
import time

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url

URL = os.getenv('PACT_TEST_POSTGRES_URL')
pytestmark = pytest.mark.skipif(not URL, reason='Run scripts/postgres_validation.py for a disposable local PostgreSQL server')
# Optional tests must not import application configuration before the ordinary
# suite establishes its isolated fixtures during collection.
if URL:
    from pact import db, outbox, ratelimit


@pytest.fixture
def postgres(monkeypatch):
    url = make_url(URL)
    assert url.host == '127.0.0.1' and url.database.startswith('pact_validation_'), 'Refusing a non-disposable/non-local database'
    engine = create_engine(url, pool_pre_ping=True)
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setattr(db, 'sqlite', False)
    monkeypatch.setattr(ratelimit, 'sqlite', False)
    yield engine
    engine.dispose()


def test_migrations_constraints_and_indexes(postgres):
    with postgres.connect() as connection:
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0007'
    inventory = inspect(postgres)
    assert {'memberships', 'invitations', 'rate_hits', 'incident_records'} <= set(inventory.get_table_names())
    assert 'ix_jobs_org_created' in {index['name'] for index in inventory.get_indexes('jobs')}
    assert any(constraint['column_names'] == ['quote_id'] for constraint in inventory.get_unique_constraints('market_bookings'))


def test_shared_rate_limit_is_atomic_between_connections(postgres):
    def hit(_):
        return ratelimit.hit('release-validation-pg', 1, 60)
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(hit, range(8)))
    assert sum(value is not None for value in values) == 1
    ratelimit.reset('release-validation-pg')


def test_committed_event_order_under_slow_writer(postgres):
    with db.session(write=True) as session:
        session.add(db.Organization(id='event-order', name='Event order fixture'))
    entered, release, second_done = threading.Event(), threading.Event(), threading.Event()
    def first():
        with db.session(write=True) as session:
            db.record(session, 'event-order', 'job', 'slow-job', 'First')
            session.flush()
            entered.set()
            assert release.wait(15)
    def second():
        assert entered.wait(5)
        with db.session(write=True) as session:
            db.record(session, 'event-order', 'job', 'slow-job', 'Second')
        second_done.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(first), pool.submit(second)
        try:
            assert entered.wait(5)
            # A later sequence must not become visible while its predecessor is
            # still uncommitted, even beyond the old finite gap grace.
            assert not second_done.wait(outbox.GAP_GRACE + .2)
            with db.session() as session:
                assert list(session.scalars(select(db.Event).where(db.Event.entity_id == 'slow-job'))) == []
        finally:
            release.set()
        a.result(timeout=15)
        b.result(timeout=15)
    with db.session() as session:
        assert list(session.scalars(select(db.Event.kind).where(db.Event.entity_id == 'slow-job').order_by(db.Event.seq))) == ['First', 'Second']


def test_prepare_matched_artifact_and_signed_evidence_for_restore(postgres):
    from pact.config import STATE
    from pact.security import sign
    with db.session(write=True) as session:
        session.add(db.Organization(id='restore-fixture', name='Disposable restore fixture'))
        session.flush()
        artifact = db.save_artifact(session, 'restore-fixture', b'known restore output', 'output.json', 'test-output')
        manifest = {'digest': artifact.digest, 'size': artifact.size}
    envelope = {'manifest': manifest, 'hmac_sha256': sign(manifest)}
    (STATE / 'restore-evidence.json').write_text(json.dumps(envelope), encoding='utf-8')


def test_marketplace_final_slot_races_on_postgres(postgres, tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / 'test_capacity_contention.py'
    spec = importlib.util.spec_from_file_location('postgres_contention_fixture', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv('PACT_CONTENTION_POSTGRES_URL', URL)
    monkeypatch.setenv('PACT_CONTENTION_CASES', '25')
    monkeypatch.setenv('PACT_CONTENTION_REPORT', str(Path(__file__).resolve().parents[3] / 'reports' / 'final-validation' / 'contention-postgres.json'))
    module.test_repeated_final_slot_races_create_exactly_one_booking(tmp_path, monkeypatch)
