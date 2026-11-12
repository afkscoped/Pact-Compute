"""Deterministic worker, journal and interrupted-publication failure injection."""
import json
import time

import httpx
import pytest
from sqlalchemy import create_engine, event, func, select

from pact import db, runner, storage, worker


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///' + (tmp_path / 'recovery.db').as_posix())
    event.listen(engine, 'connect', db.configure_sqlite)
    db.Base.metadata.create_all(engine)
    monkeypatch.setattr(db, 'engine', engine)
    monkeypatch.setattr(storage, '_store', storage.LocalStore(tmp_path / 'objects'))
    with db.session(write=True) as session:
        session.add(db.Organization(id='failure-fixture', name='Failure fixture'))
        session.flush()
        member = db.Member(org_id='failure-fixture', username='failure-fixture', role='researcher', password='unused-fixture')
        session.add(member)
        session.flush()
        run = db.ResearchRun(org_id=member.org_id, created_by=member.id,
              config={'scenario': {'title': 'Controlled failure', 'dataset_id': '0' * 64}, 'rules': []},
              status='queued', progress=0)
        session.add(run)
    yield run
    engine.dispose()


def test_failed_research_persists_a_safe_error_and_no_completed_artifact(isolated, monkeypatch):
    def fail(*args):
        raise RuntimeError('controlled internal provider detail')
    monkeypatch.setattr(worker, 'experiment', fail)
    lease = worker.claim()
    worker.process(lease)
    with db.session() as session:
        run = session.get(db.ResearchRun, isolated.id)
        assert run.status == 'failed' and run.finished_at is not None and run.artifact_id is None
        assert run.error == 'Research worker failed. See the operator log.'
        kinds = list(session.scalars(select(db.Event.kind).where(db.Event.entity_id == run.id)))
        assert kinds == ['ExperimentStarted', 'ExperimentFailed']


def test_expired_worker_lease_is_reclaimed_and_old_worker_cannot_publish(isolated, monkeypatch):
    old = worker.claim()
    with db.session(write=True) as session:
        session.get(db.ResearchRun, isolated.id).lease_until = time.time() - 1
    fresh = worker.claim()
    assert fresh.id == old.id and fresh.worker != old.worker
    monkeypatch.setattr(worker, 'experiment', lambda *args: ({'summary': {}}, {'fixture': True}))
    monkeypatch.setattr(worker, 'sign', lambda value: 'controlled-fixture-signature')
    worker.process(old)
    with db.session() as session:
        run = session.get(db.ResearchRun, old.id)
        assert run.status == 'running' and run.worker == fresh.worker and run.artifact_id is None
        assert session.scalar(select(func.count()).select_from(db.Artifact)) == 0


def test_runner_keeps_journal_across_lost_response_then_retries_once(tmp_path, monkeypatch):
    path = tmp_path / 'journal.json'
    monkeypatch.setattr(runner, 'JOURNAL', path)
    claim = {'attempt_id': 'fixture-attempt', 'fence': 'fixture-fence', 'reserved_until': 0}
    runner.save_journal(claim, {'state': 'cancelled', 'message': 'Controlled cancellation'})
    calls = []
    def transport(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            raise httpx.ReadTimeout('Controlled lost response', request=request)
        return httpx.Response(200, json={'status': 'cancelled', 'duplicate': True})
    with httpx.Client(base_url='http://local.invalid', transport=httpx.MockTransport(transport)) as client:
        with pytest.raises(httpx.ReadTimeout):
            runner.flush_journal(client)
        assert path.is_file()
        assert runner.flush_journal(client)
        assert not path.exists()
    assert calls[0] == calls[1]


def test_restarted_runner_waits_for_original_window_before_reporting_interrupted(tmp_path, monkeypatch):
    path = tmp_path / 'journal.json'
    monkeypatch.setattr(runner, 'JOURNAL', path)
    clock = [10.0]
    monkeypatch.setattr(runner.time, 'time', lambda: clock[0])
    runner.save_journal({'attempt_id': 'fixture-attempt', 'fence': 'fixture-fence', 'reserved_until': 20.0})
    sent = []
    monkeypatch.setattr(runner, 'send_event', lambda client, claim, **result: sent.append(result))
    assert not runner.flush_journal(None) and path.exists() and not sent
    clock[0] = 23.0
    assert runner.flush_journal(None) and not path.exists()
    assert sent[0]['state'] == 'interrupted'


def test_interrupted_upload_does_not_commit_metadata_and_retry_recovers(isolated, monkeypatch):
    original = storage.store()
    class Interrupted:
        def put(self, digest, payload):
            original.put(digest, payload)  # object accepted, response interrupted
            raise storage.StorageError('Controlled interrupted upload')
    monkeypatch.setattr(storage, '_store', Interrupted())
    with pytest.raises(storage.StorageError):
        with db.session(write=True) as session:
            db.save_artifact(session, 'failure-fixture', b'controlled payload', 'output.json', 'fixture')
    with db.session() as session:
        assert session.scalar(select(func.count()).select_from(db.Artifact)) == 0
    monkeypatch.setattr(storage, '_store', original)
    with db.session(write=True) as session:
        artifact = db.save_artifact(session, 'failure-fixture', b'controlled payload', 'output.json', 'fixture')
    assert original.get(artifact.digest) == b'controlled payload'
