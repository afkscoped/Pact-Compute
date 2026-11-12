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
    monkeypatch.setattr(model_gateway, '_retry_at', 0)
    monkeypatch.setattr(model_gateway.httpx, 'post', lambda *a, **kw: (calls.append(kw), Throttled())[1])
    rules, issues, method = suggest(EXAMPLE)
    assert len(rules) == 6 and not issues
    assert method == 'deterministic-fallback/provider_rate_limited'
    assert suggest(EXAMPLE)[2] == 'deterministic-fallback/provider_budget'
    assert len(calls) == 1
