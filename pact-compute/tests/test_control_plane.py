import base64
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

state = tempfile.TemporaryDirectory(prefix='pact-tests-')
os.environ['PACT_STATE_DIR'] = state.name
os.environ['PACT_DATABASE_URL'] = 'sqlite:///' + (Path(state.name) / 'test.db').as_posix()
os.environ['PACT_ADMIN_PASSWORD'] = 'test-admin-credentials'
os.environ['PACT_RUNNER_TOKEN'] = 'test-runner-token'
os.environ['GROQ_API_KEY'] = ''
os.environ['PACT_LLM_API_KEY'] = ''

from pact.api import app
from pact.db import Attempt, Member, Organization, engine, session
from pact.demo import provision_demo
from pact.live import MODEL
from pact.policy import EXAMPLE, compile_local
from pact.research import Scenario, experiment
from pact.security import password_digest, sign


AUTH = {'Authorization': 'Bearer test-runner-token'}


@pytest.fixture(scope='module')
def client():
    with TestClient(app) as test:
        result = test.post('/api/v1/session', json={'username': 'admin', 'password': 'test-admin-credentials'})
        assert result.status_code == 200, result.text
        yield test
    engine.dispose()


def approve(client, text=EXAMPLE, title='Verified test agreement'):
    draft = client.post('/api/v1/policies', json={'title': title, 'source': text}).json()
    assert not draft['issues'], draft
    approval = client.post('/api/v1/policies/' + draft['id'] + '/approve')
    assert approval.status_code == 200, approval.text
    return draft['id']


def runner_ready(client):
    result = client.post('/api/v1/runners/native-gpu/heartbeat', headers=AUTH,
                         json={'device': 'Test GPU inventory', 'vram_mib': 6144, 'ready': True})
    assert result.status_code == 200


def test_compile_source_and_strict_boundary():
    rules, issues = compile_local(EXAMPLE)
    assert not issues and len(rules) == 6
    assert EXAMPLE[rules[0].start:rules[0].end] == 'Jobs require at least 4 GiB VRAM'
    rules, issues = compile_local('Charge must be under 2.75 credits.\nJobs must finish by 17:00.')
    assert len(rules) == 1 and rules[0].value == 275 and rules[0].strict
    assert issues[0]['code'] == 'ambiguous_deadline'


def test_registration_isolates_workspaces_and_handles_duplicate_usernames(client):
    body = {'username': 'new-consumer', 'password': 'sample-registration-password',
            'organization': '  Shared label  ', 'role': 'consumer'}
    with TestClient(app) as consumer, TestClient(app) as producer:
        assert consumer.post('/api/v1/accounts', json={**body, 'role': 'admin'}).status_code == 422
        assert consumer.post('/api/v1/accounts', json={**body, 'organization': '   '}).status_code == 422
        assert consumer.post('/api/v1/accounts', headers={'Origin': 'https://foreign.example'}, json=body).status_code == 403
        result = consumer.post('/api/v1/accounts', json=body)
        assert result.status_code == 201
        assert 'HttpOnly' in result.headers['set-cookie']
        assert result.json()['organization'] == 'Shared label'
        assert consumer.get('/api/v1/session').json()['role'] == 'consumer'
        duplicate = producer.post('/api/v1/accounts', json={**body, 'role': 'producer'})
        assert duplicate.status_code == 409
        assert producer.get('/api/v1/session').status_code == 401
        assert producer.post('/api/v1/accounts', json={**body, 'username': 'new-producer', 'role': 'producer'}).status_code == 201
        assert producer.get('/api/v1/session').json()['role'] == 'producer'
        draft = consumer.post('/api/v1/policies', json={'title': 'Private agreement', 'source': EXAMPLE})
        assert draft.status_code == 201
        endpoint = '/api/v1/policies/' + draft.json()['id']
        assert producer.get(endpoint).status_code == 404
        assert consumer.post(endpoint + '/approve').status_code == 403
        assert consumer.delete('/api/v1/session').status_code == 200
        assert consumer.get('/api/v1/session').status_code == 401
        credentials = {'username': body['username'], 'password': body['password'], 'workspace': 'consumer'}
        assert consumer.post('/api/v1/session', json=credentials).status_code == 200

    with session() as db:
        assert len(list(db.scalars(select(Organization.id).where(Organization.name == 'Shared label')))) == 2
        member = db.scalar(select(Member).where(Member.username == body['username']))
        assert member.password != body['password']


def test_producer_self_service_runner_enrollment():
    body = {'username': 'enroll-producer', 'password': 'sample-registration-password',
            'organization': 'Enroll labs', 'role': 'producer'}
    with TestClient(app) as producer, TestClient(app) as consumer:
        assert producer.post('/api/v1/accounts', json=body).status_code == 201
        assert consumer.post('/api/v1/accounts', json={**body, 'username': 'enroll-consumer', 'role': 'consumer'}).status_code == 201
        assert consumer.post('/api/v1/runners', json={'name': 'Nope'}).status_code == 403
        assert producer.post('/api/v1/runners', json={'name': ' ', 'zone': 'gb'}).status_code == 422
        result = producer.post('/api/v1/runners', json={'name': 'Lab GPU', 'zone': 'GB', 'rate_cents': 300})
        assert result.status_code == 201, result.text
        runner = result.json()
        assert runner['token'] and runner['ready'] is False and runner['rate_cents'] == 300
        assert 'token' not in producer.get('/api/v1/runners').json()[0]
        assert [item['id'] for item in producer.get('/api/v1/runners').json()] == [runner['id']]
        assert consumer.get('/api/v1/runners').json() == []
        heartbeat = producer.post('/api/v1/runners/' + runner['id'] + '/heartbeat',
                                  headers={'Authorization': 'Bearer ' + runner['token']},
                                  json={'device': 'Enrolled GPU', 'vram_mib': 8192, 'ready': True})
        assert heartbeat.status_code == 200, heartbeat.text
        assert producer.get('/api/v1/runners').json()[0]['device'] == 'Enrolled GPU'


def test_invitations_membership_and_workspace_switch(monkeypatch):
    import pact.api
    monkeypatch.setattr(pact.api, 'limit_auth_attempts', lambda *args: None)
    pw = 'sample-registration-password'
    def signup(name, role, org):
        c = TestClient(app)
        c.__enter__()
        assert c.post('/api/v1/accounts', json={'username': name, 'password': pw, 'organization': org, 'role': role}).status_code == 201
        return c
    a, b = signup('inv-owner-a', 'consumer', 'Invite A'), signup('inv-owner-b', 'consumer', 'Invite B')
    draft = a.post('/api/v1/policies', json={'title': 'A agreement', 'source': EXAMPLE}).json()
    b_draft = b.post('/api/v1/policies', json={'title': 'B agreement', 'source': EXAMPLE}).json()
    assert a.post('/api/v1/policies/' + draft['id'] + '/approve').status_code == 403  # owner cannot self-approve
    assert a.post('/api/v1/invitations', json={'role': 'admin'}).status_code == 422
    assert a.post('/api/v1/invitations', json={'role': 'producer'}).status_code == 403
    invite = a.post('/api/v1/invitations', json={'role': 'reviewer'})
    assert invite.status_code == 201 and invite.json()['code']
    code = invite.json()['code']
    assert 'code' not in a.get('/api/v1/invitations').json()[0]
    assert b.get('/api/v1/invitations').json() == []
    assert b.delete('/api/v1/invitations/' + invite.json()['id']).status_code == 404
    with TestClient(app) as reviewer:
        assert reviewer.post('/api/v1/invitations/accept', json={'code': 'x' * 30, 'username': 'inv-reviewer', 'password': pw}).status_code == 404
        assert reviewer.post('/api/v1/invitations/accept', json={'code': code}).status_code == 422
        accepted = reviewer.post('/api/v1/invitations/accept', json={'code': code, 'username': 'inv-reviewer', 'password': pw})
        assert accepted.status_code == 201 and accepted.json()['role'] == 'reviewer' and accepted.json()['organization'] == 'Invite A'
        assert reviewer.post('/api/v1/policies/' + draft['id'] + '/approve').status_code == 200
        assert reviewer.post('/api/v1/policies/' + b_draft['id'] + '/approve').status_code == 404  # other tenant
        assert reviewer.post('/api/v1/invitations', json={'role': 'reviewer'}).status_code == 403
        with TestClient(app) as again:
            assert again.post('/api/v1/invitations/accept', json={'code': code, 'username': 'inv-reviewer-2', 'password': pw}).status_code == 404
    revoked = a.post('/api/v1/invitations', json={'role': 'reviewer'}).json()
    assert a.delete('/api/v1/invitations/' + revoked['id']).json()['status'] == 'revoked'
    with TestClient(app) as late:
        assert late.post('/api/v1/invitations/accept', json={'code': revoked['code'], 'username': 'inv-late', 'password': pw}).status_code == 404
    stale = a.post('/api/v1/invitations', json={'role': 'reviewer'}).json()
    with session(write=True) as db:
        from pact.db import Invitation
        db.get(Invitation, stale['id']).expires_at = 1.0
    with TestClient(app) as old:
        assert old.post('/api/v1/invitations/accept', json={'code': stale['code'], 'username': 'inv-old', 'password': pw}).status_code == 404
    # An existing person joins a second workspace and switches between them.
    extra = a.post('/api/v1/invitations', json={'role': 'consumer'}).json()
    assert b.get('/api/v1/session').json()['organization'] == 'Invite B'
    joined = b.post('/api/v1/invitations/accept', json={'code': extra['code']})
    assert joined.status_code == 201 and joined.json()['organization'] == 'Invite A'
    assert b.post('/api/v1/invitations/accept', json={'code': a.post('/api/v1/invitations', json={'role': 'consumer'}).json()['code']}).status_code == 409
    spaces = b.get('/api/v1/memberships').json()
    assert {item['organization'] for item in spaces} == {'Invite A', 'Invite B'} and sum(item['active'] for item in spaces) == 1
    assert b.get('/api/v1/session').json()['organization'] == 'Invite A'
    assert {item['id'] for item in b.get('/api/v1/policies').json()} == {draft['id']}
    home = next(item for item in spaces if item['home'])
    assert b.post('/api/v1/session/workspace', json={'org_id': home['org_id']}).status_code == 200
    assert {item['id'] for item in b.get('/api/v1/policies').json()} == {b_draft['id']}
    assert b.post('/api/v1/session/workspace', json={'org_id': 'f' * 24}).status_code == 403
    outsider = signup('inv-outsider', 'consumer', 'Invite C')
    assert outsider.post('/api/v1/session/workspace', json={'org_id': next(i for i in spaces if not i['home'])['org_id']}).status_code == 403


def test_shared_rate_limit_primitives():
    from pact import ratelimit
    ratelimit.reset('unit:')
    assert [ratelimit.hit('unit:a', 2, 60, now=100.0) is not None for _ in range(3)] == [True, True, False]
    assert ratelimit.hit('unit:a', 2, 60, now=161.0) is not None  # earlier hits expired
    with ThreadPoolExecutor(max_workers=8) as pool:  # atomic under concurrency: exactly `limit` winners
        winners = [r is not None for r in pool.map(lambda _: ratelimit.hit('unit:race', 3, 600), range(8))]
    assert sum(winners) == 3
    row = ratelimit.hit('unit:flight', 1, 600)
    assert row and ratelimit.hit('unit:flight', 1, 600) is None
    ratelimit.release(row)
    assert ratelimit.hit('unit:flight', 1, 600) is not None
    assert not ratelimit.blocked('unit:cool')
    ratelimit.mark('unit:cool', 600)
    assert ratelimit.blocked('unit:cool')
    ratelimit.reset('unit:')
    assert not ratelimit.blocked('unit:cool')


def test_bounded_retries_for_retriable_database_errors(client, monkeypatch):
    from sqlalchemy.exc import IntegrityError, OperationalError
    from pact import live, resilience

    monkeypatch.setattr(resilience, 'SLEEP', lambda _: None)
    locked = OperationalError('stmt', {}, Exception('database is locked'))
    serialization = OperationalError('stmt', {}, Exception({'S': 'ERROR', 'C': '40001', 'M': 'could not serialize access'}))
    assert resilience.retriable(locked) and resilience.retriable(serialization)
    assert not resilience.retriable(IntegrityError('stmt', {}, Exception('unique constraint')))
    assert not resilience.retriable(ValueError('x'))
    calls = []

    @resilience.retry_db
    def flaky(error, fail_times):
        calls.append(1)
        if len(calls) <= fail_times:
            raise error
        return 'ok'

    assert flaky(serialization, 2) == 'ok' and len(calls) == 3
    calls.clear()
    with pytest.raises(OperationalError):  # bounded: gives up after 3 attempts
        flaky(locked, 99)
    assert len(calls) == 3
    calls.clear()
    with pytest.raises(IntegrityError):  # not retriable: exactly one attempt
        flaky(IntegrityError('stmt', {}, Exception('unique constraint')), 99)
    assert len(calls) == 1

    # Through a real endpoint: first attempt hits a lock, the retry succeeds, one job exists.
    policy = approve(client, title='Retry agreement')
    runner_ready(client)
    original, state = live.submit_job, {'n': 0}

    def once_locked(*args, **kwargs):
        state['n'] += 1
        if state['n'] == 1:
            raise locked
        return original(*args, **kwargs)

    monkeypatch.setattr(live, 'submit_job', once_locked)
    body = {'title': 'Retried through lock', 'policy_id': policy, 'mode': 'shadow', 'sample_count': 2}
    first = client.post('/api/v1/jobs', json=body, headers={'Idempotency-Key': 'retry-lock-0001'})
    assert first.status_code == 201, first.text
    assert state['n'] == 2
    again = client.post('/api/v1/jobs', json=body, headers={'Idempotency-Key': 'retry-lock-0001'})
    assert again.json()['id'] == first.json()['id']


def test_outbox_horizon_replay_and_tenant_scope():
    import json as jsonlib
    from pact import outbox
    from pact.db import Event

    with session(write=True) as db:
        for org in ('outbox-a', 'outbox-b'):
            if not db.get(Organization, org):
                db.add(Organization(id=org, name=org))
        base = outbox.newest(db) + 100

        def add(offset, org='outbox-a', kind='Step'):
            db.add(Event(seq=base + offset, org_id=org, entity_type='job', entity_id='job-outbox', kind=kind, details={}))
        add(1, kind='One'); add(2, kind='Two'); add(4, kind='Four')  # seq base+3 is "in flight"
        add(5, org='outbox-b', kind='Foreign')
    gaps = {}
    with session() as db:
        assert outbox.horizon(db, base, gaps, now=0.0) == base + 2          # waits for the missing number
        assert outbox.horizon(db, base, gaps, now=1.0) == base + 2          # still within grace
    with session(write=True) as db:                                          # the slow transaction finally commits
        db.add(Event(seq=base + 3, org_id='outbox-a', entity_type='job', entity_id='job-outbox', kind='Three', details={}))
    with session() as db:
        assert outbox.horizon(db, base, gaps, now=1.5) == base + 5          # late commit is no longer skipped
        assert outbox.horizon(db, base + 5, {}, now=0.0) == base + 5
    # A rolled-back transaction leaves a permanent gap that is skipped only after the grace period.
    with session(write=True) as db:
        db.add(Event(seq=base + 8, org_id='outbox-a', entity_type='job', entity_id='job-outbox', kind='Eight', details={}))
    gaps = {}
    with session() as db:
        assert outbox.horizon(db, base + 5, gaps, now=10.0) == base + 5
        assert outbox.horizon(db, base + 5, gaps, now=10.0 + outbox.GAP_GRACE + 0.1) == base + 8

    def kinds(org, last):
        lines = outbox.entity_stream(org, 'job', 'job-outbox', last, window=0.05, pause=0.01)
        return [jsonlib.loads(line.split('data: ', 1)[1])['kind'] for line in lines if line.startswith('id:')]
    assert kinds('outbox-a', base) == ['One', 'Two', 'Three', 'Four', 'Eight']
    assert kinds('outbox-a', base + 3) == ['Four', 'Eight']                  # reconnect resumes after Last-Event-ID
    assert kinds('outbox-b', base) == ['Foreign']                            # other tenant sees only its own events
    assert kinds('outbox-a', base + 8) == []


def test_artifact_stores_local_s3_and_integrity(tmp_path, monkeypatch):
    import hashlib

    import boto3
    from moto import mock_aws
    from pact import storage

    data = b'{"embedding": [1, 0, 0]}'
    digest = hashlib.sha256(data).hexdigest()
    local = storage.LocalStore(tmp_path / 'artifacts')
    local.put(digest, data)
    local.put(digest, data)  # idempotent
    assert local.exists(digest) and local.get(digest) == data
    with pytest.raises(storage.StorageError):
        local.put(digest, b'tampered')  # bytes must hash to the claimed digest
    with pytest.raises(storage.StorageError):
        local.get('../../etc/passwd')  # digest is validated, no path traversal
    (tmp_path / 'artifacts' / digest).write_bytes(b'bit rot')
    with pytest.raises(storage.StorageError, match='does not match'):
        local.get(digest)
    assert not local.exists('0' * 64)
    with pytest.raises(storage.MissingArtifact):
        local.get('0' * 64)

    with mock_aws():
        client = boto3.client('s3', region_name='us-east-1')
        client.create_bucket(Bucket='pact-test')
        remote = storage.S3Store('pact-test', 'artifacts', client=client)
        assert not remote.exists(digest)
        with pytest.raises(storage.MissingArtifact):
            remote.get(digest)
        remote.put(digest, data)
        remote.put(digest, data)
        assert remote.exists(digest) and remote.get(digest) == data
        assert client.head_object(Bucket='pact-test', Key='artifacts/' + digest)['Metadata']['sha256'] == digest
        client.put_object(Bucket='pact-test', Key='artifacts/' + digest, Body=b'corrupted in the bucket')
        with pytest.raises(storage.StorageError, match='does not match'):
            remote.get(digest)

        # Environment selection
        monkeypatch.setenv('PACT_ARTIFACT_BACKEND', 's3')
        monkeypatch.setenv('PACT_S3_BUCKET', 'pact-test')
        monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
        built = storage.build_store()
        assert built.name == 's3' and built.prefix == 'artifacts/'
    monkeypatch.delenv('PACT_S3_BUCKET')
    with pytest.raises(storage.StorageError, match='PACT_S3_BUCKET'):
        storage.build_store()
    monkeypatch.setenv('PACT_ARTIFACT_BACKEND', 'floppy')
    with pytest.raises(storage.StorageError):
        storage.build_store()
    monkeypatch.setenv('PACT_ARTIFACT_BACKEND', 'local')
    assert storage.build_store().name == 'local'


def test_artifact_download_integrity_and_verify_command(client, capsys):
    from pact import storage
    from pact.cli import main
    import sys

    from pact.db import save_artifact
    from pact.security import ORG_ID
    with session(write=True) as db:
        stored = save_artifact(db, ORG_ID, b'{"integrity": "check"}', 'integrity.json', 'output')
        artifact_id, digest = stored.id, stored.digest
    good = client.get('/api/v1/artifacts/' + artifact_id)
    assert good.status_code == 200 and good.headers['x-content-sha256'] == digest
    path = storage.store().path(digest)
    original = path.read_bytes()
    path.write_bytes(b'tampered on disk')
    try:
        assert client.get('/api/v1/artifacts/' + artifact_id).status_code == 502
        monkey_argv = sys.argv
        sys.argv = ['pact', 'artifacts-verify']
        try:
            with pytest.raises(SystemExit) as failed:
                main()
        finally:
            sys.argv = monkey_argv
        assert failed.value.code == 1 and 'corrupt: 1' in capsys.readouterr().out
        path.unlink()
        assert client.get('/api/v1/artifacts/' + artifact_id).status_code == 410
    finally:
        path.write_bytes(original)
    sys.argv = ['pact', 'artifacts-verify']
    try:
        with pytest.raises(SystemExit) as passed:
            main()
    finally:
        sys.argv = monkey_argv
    assert passed.value.code == 0 and 'corrupt: 0' in capsys.readouterr().out


def test_invitation_accept_is_rate_limited():
    import pact.api
    from pact import ratelimit
    ratelimit.reset('register')
    with TestClient(app) as anonymous:
        codes = [anonymous.post('/api/v1/invitations/accept', json={'code': 'y' * 30, 'username': 'rl-user', 'password': 'sample-registration-password'}).status_code for _ in range(8)]
    ratelimit.reset('register')
    assert codes[:6] == [404] * 6 and codes[-1] == 429


def test_unresolved_approval_and_tenant_isolation(client):
    draft = client.post('/api/v1/policies', json={'title': 'Missing timezone', 'source': 'Jobs must finish by 17:00.'}).json()
    assert client.post('/api/v1/policies/' + draft['id'] + '/approve').status_code == 409
    with session(write=True) as db:
        db.add(Organization(id='second', name='Second organization'))
        db.flush()
        db.add(Member(org_id='second', username='reviewer2', password=password_digest('second-test-password'), role='reviewer'))
    other = TestClient(app)
    assert other.post('/api/v1/session', json={'username': 'reviewer2', 'password': 'second-test-password'}).status_code == 200
    assert other.get('/api/v1/policies/' + draft['id']).status_code == 404
    assert other.get('/api/v1/policies').json() == []
    assert client.post('/api/v1/policies', headers={'Origin': 'https://foreign.example'}, json={}).status_code == 403


def test_reservation_output_and_evidence(client):
    policy = approve(client)
    runner_ready(client)
    body = {'title': 'Job evidence', 'policy_id': policy, 'mode': 'live', 'sample_count': 2}
    request_key = {'Idempotency-Key': 'test-reservation-1'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post('/api/v1/jobs', json=body, headers=request_key), range(2)))
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
    first, second = [r.json() for r in responses]
    assert first['id'] == second['id'] and first['status'] == 'reserved'
    shadow = client.post('/api/v1/jobs', json={**body, 'mode': 'shadow'}, headers={'Idempotency-Key': 'test-shadow-1'}).json()
    assert shadow['status'] == 'recommended'
    assert client.post('/api/v1/runners/native-gpu/claim').status_code == 401
    lease = client.post('/api/v1/runners/native-gpu/claim', headers=AUTH).json()
    assert lease['job_id'] == first['id']
    assert client.post('/api/v1/runners/native-gpu/claim', headers=AUTH).json() is None
    endpoint = '/api/v1/runners/native-gpu/attempts/' + lease['attempt_id']
    inputs = client.get(endpoint + '/input', headers={**AUTH, 'Lease-Fence': lease['fence']}).json()
    assert len(inputs['images']) == 2 and base64.b64decode(inputs['images'][0]['png']).startswith(b'\x89PNG')
    started = client.post(endpoint + '/events', json={'fence': lease['fence'], 'state': 'started'}, headers=AUTH)
    assert started.status_code == 200, started.text
    rows = [{key: item[key] for key in ('row', 'name', 'sha256')} | {'embedding': [1.0] + [0.0] * 959} for item in inputs['images']]
    result = {'fence': lease['fence'], 'state': 'succeeded', 'duration_s': 5.0, 'device': 'Test GPU inventory',
              'gpu_energy_kwh': .0001, 'telemetry_coverage': .8, 'power_samples': 4,
              'artifact': {'model': MODEL, 'backend': 'cuda', 'items': rows}}
    ended = client.post(endpoint + '/events', json=result, headers=AUTH)
    assert ended.status_code == 200, ended.text
    assert client.post(endpoint + '/events', json=result, headers=AUTH).json()['duplicate']
    details = client.get('/api/v1/jobs/' + first['id']).json()
    assert details['status'] == 'succeeded'
    assert [finding['status'] for finding in details['findings']].count('pass') >= 4
    artifact = details['attempts'][0]['result']['artifact_id']
    assert client.get('/api/v1/artifacts/' + artifact).json()['items'][1]['row'] == 2
    manifest = client.get('/api/v1/jobs/' + first['id'] + '/evidence.json').json()
    assert sign(manifest['manifest']) == manifest['hmac_sha256']


def test_infeasible_memory_and_carbon(client):
    runner_ready(client)
    policy = approve(client, 'Jobs require at least 32 GiB VRAM.\nEstimated emissions must not exceed 1 g CO2.')
    preview = client.post('/api/v1/jobs/preview', json={'title': 'Infeasible job', 'policy_id': policy}).json()
    assert preview['selected'] is None
    assert {'vram', 'carbon_unknown'} <= {reason['code'] for reason in preview['candidates'][0]['reasons']}


def test_source_import_and_reproducible_experiment(client):
    result = client.post('/api/v1/datasets/import')
    assert result.status_code == 200, result.text
    card = result.json()
    assert (card['gpu_pods'], card['runtime_proxies'], card['carbon_intervals']) == (7064, 185, 1344)
    settings = Scenario(title='Deterministic sample', dataset_id=card['id'], seed=2026, jobs=30, seeds=1)
    first, _ = experiment(settings, [], lambda _: None)
    second, _ = experiment(settings, [], lambda _: None)
    assert first == second
    assert first['summary']['fcfs']['submitted'] == 30
    assert first['summary']['carbon_aware']['completed'] > 0
    assert len(first['first_episode']['audits']) == 3


def test_market_roles_last_slot_and_privacy(client):
    import json
    import time

    users = json.loads(provision_demo().read_bytes())
    producer, buyer, other = TestClient(app), TestClient(app), TestClient(app)
    for role, actor, username in [('producer', producer, 'demo-producer'), ('consumer', buyer, 'demo-consumer'),
                                  ('consumer', other, 'demo-consumer-2')]:
        response = actor.post('/api/v1/session', json={'username': username, 'password': users[username], 'workspace': role})
        assert response.status_code == 200, response.text
    runner_ready(client)
    now = time.time()
    listing = {'runner_id': 'native-gpu', 'title': 'Capacity test', 'starts_at': now - 10, 'ends_at': now + 200, 'rate_cents': 250}
    assert buyer.post('/api/v1/market/offers', json=listing).status_code == 403
    offer = producer.post('/api/v1/market/offers', json=listing).json()
    assert offer['available']
    assert offer['id'] in {item['id'] for item in buyer.get('/api/v1/market/offers').json()}
    quotes = []
    for actor in (buyer, other):
        policy = next(item for item in actor.get('/api/v1/policies').json() if item['status'] == 'approved')
        response = actor.post('/api/v1/market/quotes', json={'offer_id': offer['id'], 'policy_id': policy['id'],
                              'title': 'Private upload label', 'sample_count': 2})
        assert response.status_code == 200, response.text
        quoted = response.json()
        assert quoted['id']
        quotes.append('/api/v1/market/quotes/' + quoted['id'] + '/confirm')
    assert other.post(quotes[0], json={}).status_code == 404
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda row: row[0].post(row[1], json={}), zip((buyer, other), quotes)))
    assert sorted(r.status_code for r in results) == [201, 409], [r.text for r in results]
    winner_index = next(index for index, result in enumerate(results) if result.status_code == 201)
    winner, loser = (buyer, other) if winner_index == 0 else (other, buyer)
    booking = results[winner_index].json()
    assert winner.post(quotes[winner_index], json={}).json()['id'] == booking['id']
    shared = '/api/v1/market/bookings/' + booking['id']
    producer_data = producer.get(shared).json()
    assert producer_data['job_id'] is None and 'Private upload label' not in producer_data['title']
    assert producer_data['protocol']['verdict'] == 'incomplete'
    assert loser.get(shared).status_code == 404
    assert producer.get('/api/v1/jobs/' + booking['job_id']).status_code == 404
    assert winner.post('/api/v1/jobs/' + booking['job_id'] + '/cancel').status_code == 200
    receipt = producer.get(shared + '/receipt').json()
    assert receipt['manifest']['booking']['protocol']['verdict'] == 'pass'
    assert sign(receipt['manifest']) == receipt['hmac_sha256']
    guided = producer.post('/api/v1/explain/answer', json={'topic': 'booking', 'ref': booking['id']}).json()
    assert any(step['title'] == 'CapacityReleased' for step in guided['steps'])

    policy_id = winner.get('/api/v1/policies').json()[0]['id']
    request = {'offer_id': offer['id'], 'policy_id': policy_id, 'title': 'Lost runner scenario', 'sample_count': 2}
    new_quote = winner.post('/api/v1/market/quotes', json=request).json()
    reserved = winner.post('/api/v1/market/quotes/' + new_quote['id'] + '/confirm', json={}).json()
    lease = client.post('/api/v1/runners/native-gpu/claim', headers=AUTH).json()
    assert lease['job_id'] == reserved['job_id']
    with session(write=True) as db:
        db.get(Attempt, lease['attempt_id']).lease_until = time.time() - 1
    from pact.worker import reconcile

    reconcile()
    uncertain = producer.get('/api/v1/market/bookings/' + reserved['id']).json()
    assert uncertain['status'] == 'execution_unknown'
    blocked = winner.post('/api/v1/market/quotes', json=request).json()
    assert blocked['id'] is None and any(
        reason['code'] == 'execution_unknown' for option in blocked['candidates'] for reason in option['reasons'])
    assert client.post('/api/v1/runners/native-gpu/claim', headers=AUTH).json() is None
    reported = client.post('/api/v1/runners/native-gpu/attempts/' + lease['attempt_id'] + '/events',
                           json={'fence': lease['fence'], 'state': 'interrupted'}, headers=AUTH)
    assert reported.status_code == 200
    assert producer.get('/api/v1/market/bookings/' + reserved['id']).json()['protocol']['verdict'] == 'pass'


def test_fault_injection_key_reuse_quote_expiry_and_stale_fence(client):
    import json
    import time
    from pact.db import MarketQuote

    # Same idempotency key with a different submission is rejected, an identical retry returns the same job.
    policy = approve(client, title='Fault agreement')
    runner_ready(client)
    body = {'title': 'Retry me', 'policy_id': policy, 'mode': 'shadow', 'sample_count': 2}
    key = {'Idempotency-Key': 'fault-key-0001'}
    first = client.post('/api/v1/jobs', json=body, headers=key)
    assert first.status_code == 201, first.text
    assert client.post('/api/v1/jobs', json=body, headers=key).json()['id'] == first.json()['id']
    assert client.post('/api/v1/jobs', json={**body, 'sample_count': 3}, headers=key).status_code == 409
    assert client.post('/api/v1/jobs', json=body).status_code == 422  # key is mandatory

    users = json.loads(provision_demo().read_bytes())
    producer, buyer = TestClient(app), TestClient(app)
    for role, actor, name in [('producer', producer, 'demo-producer'), ('consumer', buyer, 'demo-consumer')]:
        assert actor.post('/api/v1/session', json={'username': name, 'password': users[name], 'workspace': role}).status_code == 200
    now = time.time()
    offer = producer.post('/api/v1/market/offers', json={'runner_id': 'native-gpu', 'title': 'Fault window',
                          'starts_at': now - 10, 'ends_at': now + 400, 'rate_cents': 250}).json()
    agreement = next(item for item in buyer.get('/api/v1/policies').json() if item['status'] == 'approved')['id']
    request = {'offer_id': offer['id'], 'policy_id': agreement, 'title': 'Fault run', 'sample_count': 2}
    stale = buyer.post('/api/v1/market/quotes', json=request).json()
    assert stale['id'], stale
    with session(write=True) as db:
        db.get(MarketQuote, stale['id']).expires_at = time.time() - 1
    expired = buyer.post('/api/v1/market/quotes/' + stale['id'] + '/confirm', json={})
    assert expired.status_code == 409 and 'expired' in expired.text

    fresh = buyer.post('/api/v1/market/quotes', json=request).json()
    booked = buyer.post('/api/v1/market/quotes/' + fresh['id'] + '/confirm', json={})
    assert booked.status_code == 201, booked.text
    lease = client.post('/api/v1/runners/native-gpu/claim', headers=AUTH).json()
    assert lease and lease['job_id'] == booked.json()['job_id']
    endpoint = '/api/v1/runners/native-gpu/attempts/' + lease['attempt_id']
    wrong = client.post(endpoint + '/events', json={'fence': 'stale-fence-value', 'state': 'started'}, headers=AUTH)
    assert wrong.status_code == 404
    assert client.get(endpoint + '/input', headers={**AUTH, 'Lease-Fence': 'stale-fence-value'}).status_code == 404
    other_runner = client.post('/api/v1/runners/other-runner/attempts/' + lease['attempt_id'] + '/events',
                               json={'fence': lease['fence'], 'state': 'started'}, headers=AUTH)
    assert other_runner.status_code in (401, 403, 404)
    assert client.post(endpoint + '/events', json={'fence': lease['fence'], 'state': 'interrupted'}, headers=AUTH).status_code == 200


def test_research_holdouts_and_groq_fallback(monkeypatch):
    from pact import model_gateway, pricing_model
    from pact.llm import suggest
    from pact.publication import protocol_benchmark

    results = protocol_benchmark()['comparison']
    assert results['temporal_monitor']['unsafe_accepts'] == 0
    assert results['presence_baseline']['unsafe_accepts'] > 0
    pricing = pricing_model.evaluate(seeds=6)
    assert pricing['training']['episodes'] > 0 and pricing['fsm']['covered'] > 0
    assert pricing['splits']['fsm_fit_seeds'][1] < pricing['splits']['heldout_seeds'][0]

    class Throttled:
        status_code = 429
        headers = {'Retry-After': '40'}

    calls = []
    monkeypatch.setattr(model_gateway, 'LLM_KEY', 'test-key')
    monkeypatch.setattr(model_gateway, 'LLM_MODEL', 'test-model')
    from pact import ratelimit
    ratelimit.reset('llm')
    monkeypatch.setattr(model_gateway.httpx, 'post', lambda *a, **kw: (calls.append(kw), Throttled())[1])
    rules, issues, method = suggest(EXAMPLE)
    assert len(rules) == 6 and not issues
    assert method == 'deterministic-fallback/provider_rate_limited'
    assert suggest(EXAMPLE)[2] == 'deterministic-fallback/provider_budget'
    assert len(calls) == 1
