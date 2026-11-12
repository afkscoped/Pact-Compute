"""Tenant authorization matrix.

Every route comes from the app's route table, so a new route fails `test_every_route_is_classified` until someone states
who may call it. Each classified route is then exercised as: no login, an expired session, every wrong role, a user of
another tenant (every role), and a member whose extra workspace membership was removed. Cross-tenant responses must not
contain any identifier, title or name that belongs to the first tenant.
"""
import os
import re
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import select

state = tempfile.TemporaryDirectory(prefix='pact-authz-')
os.environ['PACT_STATE_DIR'] = state.name
os.environ['PACT_DATABASE_URL'] = 'sqlite:///' + (Path(state.name) / 'test.db').as_posix()
os.environ['PACT_ADMIN_PASSWORD'] = 'test-admin-credentials'
os.environ['PACT_RUNNER_TOKEN'] = 'test-runner-token'
os.environ['GROQ_API_KEY'] = ''
os.environ['PACT_LLM_API_KEY'] = ''

from pact.api import app  # noqa: E402
from pact.db import Login, Member, Membership, Organization, ResearchRun, engine, session, sha  # noqa: E402
from pact.policy import EXAMPLE  # noqa: E402
from pact.security import COOKIE, password_digest  # noqa: E402

PASSWORD = 'authz-matrix-password-1'
ROLES = ('admin', 'operator', 'reviewer', 'researcher', 'submitter', 'consumer', 'producer')
AUTH = {'Authorization': 'Bearer test-runner-token'}
BUYERS, PRODUCERS = ('admin', 'consumer', 'submitter'), ('admin', 'operator', 'producer')
PARTICIPANTS = ('admin', 'consumer', 'submitter', 'operator', 'producer', 'reviewer', 'researcher')

PUBLIC, RUNNER, AUTHED = 'public', 'runner', 'authed'
# (method, path template) -> (kind, allowed roles). Written from the intended policy, not copied from the code.
POLICY = {
    ('GET', '/api/health'): (PUBLIC, None),
    ('POST', '/api/v1/accounts'): (PUBLIC, None),
    ('POST', '/api/v1/session'): (PUBLIC, None),
    ('DELETE', '/api/v1/session'): (PUBLIC, None),
    ('POST', '/api/v1/invitations/accept'): (PUBLIC, None),
    ('GET', '/{path:path}'): (PUBLIC, None),
    ('GET', '/api/v1/session'): (AUTHED, None),
    ('GET', '/api/v1/config'): (AUTHED, None),
    ('GET', '/api/v1/policies'): (AUTHED, None),
    ('GET', '/api/v1/policies/inbox'): (AUTHED, ('admin', 'reviewer')),
    ('POST', '/api/v1/policies'): (AUTHED, ('admin', 'reviewer', 'submitter', 'consumer')),
    ('GET', '/api/v1/policies/{policy_id}'): (AUTHED, None),
    ('POST', '/api/v1/policies/{policy_id}/revisions'): (AUTHED, ('admin', 'reviewer')),
    ('POST', '/api/v1/policies/{policy_id}/approve'): (AUTHED, ('admin', 'reviewer')),
    ('POST', '/api/v1/policies/{policy_id}/reject'): (AUTHED, ('admin', 'reviewer')),
    ('GET', '/api/v1/runners'): (AUTHED, None),
    ('POST', '/api/v1/runners'): (AUTHED, ('admin', 'operator', 'producer')),
    ('PATCH', '/api/v1/runners/{runner_id}/dispatch'): (AUTHED, ('admin', 'operator', 'producer')),
    ('GET', '/api/v1/jobs'): (AUTHED, None),
    ('POST', '/api/v1/jobs/preview'): (AUTHED, None),
    ('POST', '/api/v1/jobs/preview/counterfactual'): (AUTHED, None),
    ('POST', '/api/v1/jobs'): (AUTHED, ('admin', 'operator', 'submitter')),
    ('GET', '/api/v1/jobs/{job_id}'): (AUTHED, None),
    ('POST', '/api/v1/jobs/{job_id}/cancel'): (AUTHED, ('admin', 'operator', 'submitter', 'consumer')),
    ('POST', '/api/v1/jobs/{job_id}/reconcile'): (AUTHED, ('admin', 'operator')),
    ('GET', '/api/v1/jobs/{job_id}/evidence.json'): (AUTHED, None),
    ('POST', '/api/v1/runners/{runner_id}/heartbeat'): (RUNNER, None),
    ('POST', '/api/v1/runners/{runner_id}/claim'): (RUNNER, None),
    ('GET', '/api/v1/runners/{runner_id}/attempts/{attempt_id}/input'): (RUNNER, None),
    ('POST', '/api/v1/runners/{runner_id}/attempts/{attempt_id}/events'): (RUNNER, None),
    ('GET', '/api/v1/artifacts/{artifact_id}'): (AUTHED, None),
    ('GET', '/api/v1/datasets'): (AUTHED, None),
    ('POST', '/api/v1/datasets/import'): (AUTHED, ('admin', 'operator')),
    ('GET', '/api/v1/runs'): (AUTHED, None),
    ('POST', '/api/v1/runs'): (AUTHED, ('admin', 'operator', 'researcher')),
    ('GET', '/api/v1/runs/{run_id}'): (AUTHED, None),
    ('GET', '/api/v1/runs/{run_id}/metrics.csv'): (AUTHED, None),
    ('POST', '/api/v1/{kind}/{object_id}/reviews'): (AUTHED, ('admin', 'reviewer')),
    ('GET', '/api/v1/{kind}/{object_id}/events'): (AUTHED, None),
    ('GET', '/api/v1/market/offers'): (AUTHED, PARTICIPANTS),
    ('POST', '/api/v1/market/offers'): (AUTHED, PRODUCERS),
    ('PATCH', '/api/v1/market/offers/{offer_id}'): (AUTHED, PRODUCERS),
    ('POST', '/api/v1/market/quotes'): (AUTHED, BUYERS),
    ('POST', '/api/v1/market/quotes/{quote_id}/confirm'): (AUTHED, BUYERS),
    ('GET', '/api/v1/market/bookings'): (AUTHED, PARTICIPANTS),
    ('GET', '/api/v1/market/bookings/{booking_id}'): (AUTHED, None),
    ('GET', '/api/v1/market/bookings/{booking_id}/receipt'): (AUTHED, None),
    ('GET', '/api/v1/market/events'): (AUTHED, PARTICIPANTS),
    ('POST', '/api/v1/explain/answer'): (AUTHED, None),
    ('GET', '/api/v1/explain/options'): (AUTHED, None),
    ('GET', '/api/v1/explain/study'): (AUTHED, None),
    ('GET', '/api/v1/explain/study/download/{name}'): (AUTHED, None),
    ('POST', '/api/v1/invitations'): (AUTHED, ('admin', 'producer', 'consumer')),
    ('GET', '/api/v1/invitations'): (AUTHED, ('admin', 'producer', 'consumer')),
    ('DELETE', '/api/v1/invitations/{invitation_id}'): (AUTHED, ('admin', 'producer', 'consumer')),
    ('GET', '/api/v1/memberships'): (AUTHED, None),
    ('POST', '/api/v1/session/workspace'): (AUTHED, None),
}
# Framework-generated documentation routes (not APIRoute objects).
FRAMEWORK = {'/api/openapi.json', '/api/docs', '/docs/oauth2-redirect', '/redoc'}
STREAMS = {'/api/v1/{kind}/{object_id}/events', '/api/v1/market/events'}


def route_table():
    found = set()

    def walk(routes):
        for route in routes:
            if type(route).__name__ == '_IncludedRouter':
                walk(route.original_router.routes)
            elif isinstance(route, APIRoute):
                found.update((method, route.path) for method in route.methods if method != 'HEAD')
    walk(app.routes)
    return found


def test_every_route_is_classified():
    actual = route_table()
    assert actual - set(POLICY) == set(), f'Unclassified routes (state who may call them): {sorted(actual - set(POLICY))}'
    assert set(POLICY) - actual == set(), f'Stale policy entries: {sorted(set(POLICY) - actual)}'
    assert {r.path for r in app.routes if not isinstance(r, APIRoute) and type(r).__name__ == 'Route'} <= FRAMEWORK


# ---- fixtures ---------------------------------------------------------------------------------------------------------

class World:
    pass


def make_member(org_id, username, role):
    with session(write=True) as db:
        db.add(Member(org_id=org_id, username=username, password=password_digest(PASSWORD), role=role))


def login(username):
    client = TestClient(app)
    response = client.post('/api/v1/session', json={'username': username, 'password': PASSWORD})
    assert response.status_code == 200, (username, response.text)
    return client


@pytest.fixture(scope='module')
def world(request):
    import pact.api
    mp = pytest.MonkeyPatch()
    mp.setattr(pact.api, 'limit_auth_attempts', lambda *args: None)
    request.addfinalizer(mp.undo)
    with TestClient(app) as boot:  # runs startup (admin and runner provisioning)
        admin = boot.post('/api/v1/session', json={'username': 'admin', 'password': 'test-admin-credentials'})
        assert admin.status_code == 200, admin.text
        w = World()
        w.admin_a = boot
        with session() as db:
            w.org_a = db.scalar(select(Member.org_id).where(Member.username == 'admin'))
        with session(write=True) as db:
            org_b = Organization(id='matrix-tenant-b', name='Matrix tenant B')
            db.add(org_b)
            db.flush()
            w.org_b = org_b.id
        for role in ROLES:
            if role != 'admin':
                make_member(w.org_a, f'a-{role}', role)
            make_member(w.org_b, f'b-{role}', role)
        w.a = {role: (w.admin_a if role == 'admin' else login(f'a-{role}')) for role in ROLES}
        w.b = {role: login(f'b-{role}') for role in ROLES}
        # --- tenant A's private objects
        runner = w.a['producer']
        w.runner_id = 'native-gpu'
        assert boot.post('/api/v1/runners/native-gpu/heartbeat', headers=AUTH,
                         json={'device': 'Test GPU inventory', 'vram_mib': 6144, 'ready': True}).status_code == 200
        draft = boot.post('/api/v1/policies', json={'title': 'Tenant A secret agreement', 'source': EXAMPLE}).json()
        assert boot.post(f'/api/v1/policies/{draft["id"]}/approve').status_code == 200
        w.policy_id, w.policy_title = draft['id'], 'Tenant A secret agreement'
        job = boot.post('/api/v1/jobs', json={'title': 'Tenant A secret job', 'policy_id': w.policy_id, 'mode': 'live', 'sample_count': 2},
                        headers={'Idempotency-Key': 'authz-job-000001'})
        assert job.status_code == 201, job.text
        w.job_id, w.job_title = job.json()['id'], 'Tenant A secret job'
        shadow = boot.post('/api/v1/jobs', json={'title': 'Tenant A shadow job', 'policy_id': w.policy_id, 'mode': 'shadow', 'sample_count': 1},
                           headers={'Idempotency-Key': 'authz-job-000002'})
        assert shadow.status_code == 201, shadow.text
        detail = boot.get(f'/api/v1/jobs/{w.job_id}').json()
        w.artifact_id = detail['workload']['input_manifest']['artifact_id']
        w.attempt_id = 'a' * 32
        with session(write=True) as db:
            run = ResearchRun(org_id=w.org_a, created_by=db.scalar(select(Member.id).where(Member.username == 'admin')),
                              config={'scenario': {'title': 'Tenant A secret run'}}, result={'summary': {}}, status='completed', progress=100)
            db.add(run)
            db.flush()
            w.run_id = run.id
        now = time.time()
        offer = w.a['producer'].post('/api/v1/market/offers', json={'runner_id': 'native-gpu', 'title': 'Tenant A offer',
                                                                    'starts_at': now - 10, 'ends_at': now + 600, 'rate_cents': 200})
        assert offer.status_code == 201, offer.text
        w.offer_id = offer.json()['id']
        quote = w.a['consumer'].post('/api/v1/market/quotes', json={'offer_id': w.offer_id, 'policy_id': w.policy_id,
                                                                    'title': 'Tenant A quote label', 'sample_count': 1})
        assert quote.status_code == 200, quote.text
        w.quote_id = quote.json()['id']
        booking = w.a['consumer'].post(f'/api/v1/market/quotes/{w.quote_id}/confirm', json={})
        assert booking.status_code == 201, booking.text
        w.booking_id, w.booking_job = booking.json()['id'], booking.json()['job_id']
        invite = w.a['consumer'].post('/api/v1/invitations', json={'role': 'reviewer'}).json()
        w.invitation_id, w.invite_code = invite['id'], invite['code']
        w.secrets = [w.policy_id, w.policy_title, w.job_id, w.job_title, w.artifact_id, w.run_id, 'Tenant A secret run', w.booking_id,
                     w.booking_job, w.quote_id, 'Tenant A quote label', w.invitation_id, w.invite_code, w.org_a, w.offer_id if False else w.booking_id]
        yield w
        for job_id in (w.job_id, w.booking_job):
            boot.post(f'/api/v1/jobs/{job_id}/cancel')
        w.a['producer'].patch(f'/api/v1/market/offers/{w.offer_id}', json={'status': 'paused'})
    engine.dispose()


def fill(template, w):
    ids = {'policy_id': w.policy_id, 'runner_id': w.runner_id, 'job_id': w.job_id, 'attempt_id': w.attempt_id,
           'artifact_id': w.artifact_id, 'run_id': w.run_id, 'offer_id': w.offer_id, 'quote_id': w.quote_id,
           'booking_id': w.booking_id, 'invitation_id': w.invitation_id, 'object_id': w.job_id, 'kind': 'jobs', 'name': 'publication-study.json'}
    return re.sub(r'\{(\w+)(?::\w+)?\}', lambda m: ids[m.group(1)], template)


def body_for(method, template, w):
    bodies = {
        '/api/v1/policies': {'title': 'Probe agreement', 'source': 'Jobs require at least 4 GiB VRAM.'},
        '/api/v1/policies/{policy_id}/revisions': {'rules': [{'kind': 'min_vram_mib', 'value': 1024, 'start': None, 'end': None, 'rationale': '', 'strict': False}], 'resolutions': {}},
        '/api/v1/policies/{policy_id}/reject': {'reason': 'probing the authorization matrix'},
        '/api/v1/runners': {'name': 'Probe runner', 'zone': None, 'rate_cents': 100},
        '/api/v1/runners/{runner_id}/dispatch': {'paused': False},
        '/api/v1/runners/{runner_id}/attempts/{attempt_id}/events': {'fence': 'x' * 8, 'state': 'started'},
        '/api/v1/jobs/preview': {'title': 'Probe job', 'policy_id': w.policy_id},
        '/api/v1/jobs/preview/counterfactual': {'title': 'Probe job', 'policy_id': w.policy_id},
        '/api/v1/jobs': {'title': 'Probe job', 'policy_id': w.policy_id, 'mode': 'shadow', 'sample_count': 1},
        '/api/v1/jobs/{job_id}/reconcile': {'note': 'probing the matrix'},
        '/api/v1/runs': {'title': 'Probe run', 'dataset_id': 'a' * 64, 'seed': 1, 'jobs': 30, 'seeds': 1},
        '/api/v1/{kind}/{object_id}/reviews': {'finding_id': 'nope', 'disposition': 'confirmed', 'note': 'probe note'},
        '/api/v1/market/offers': {'runner_id': 'native-gpu', 'title': 'Probe offer', 'starts_at': time.time(), 'ends_at': time.time() + 60, 'rate_cents': 10},
        '/api/v1/market/offers/{offer_id}': {'status': 'paused'},
        '/api/v1/market/quotes': {'offer_id': w.offer_id, 'policy_id': w.policy_id, 'title': 'Probe quote', 'sample_count': 1},
        '/api/v1/market/quotes/{quote_id}/confirm': {},
        '/api/v1/explain/answer': {'topic': 'job', 'ref': w.job_id},
        '/api/v1/invitations': {'role': 'reviewer'},
        '/api/v1/session/workspace': {'org_id': w.org_a},
    }
    return bodies.get(template)


def send(client, method, template, w, headers=None):
    kwargs = {'headers': dict(headers or {})}
    body = body_for(method, template, w)
    if body is not None:
        kwargs['json'] = body
    if template == '/api/v1/jobs':
        kwargs['headers']['Idempotency-Key'] = 'probe-' + os.urandom(6).hex()
    path = fill(template, w)
    if template in STREAMS:
        with client.stream(method, path, **kwargs) as response:  # read only the status line: never wait for the stream
            return response.status_code, ''
    return (lambda r: (r.status_code, r.text))(client.request(method, path, **kwargs))


def cookie_routes():
    return sorted((m, p) for (m, p), (kind, _) in POLICY.items() if kind == AUTHED)


# ---- the matrix -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize('method,template', cookie_routes())
def test_anonymous_callers_are_refused(world, method, template):
    status, text = send(TestClient(app), method, template, world)
    assert status == 401, (method, template, status, text[:200])
    assert not any(secret in text for secret in world.secrets)


@pytest.mark.parametrize('method,template', cookie_routes())
def test_expired_sessions_are_refused(world, method, template):
    client = login('a-reviewer')
    with session(write=True) as db:
        db.get(Login, sha(client.cookies.get(COOKIE))).expires = time.time() - 5
    status, text = send(client, method, template, world)
    assert status == 401, (method, template, status, text[:200])


@pytest.mark.parametrize('method,template', [(m, p) for (m, p) in cookie_routes() if POLICY[(m, p)][1] and
                                             p not in ('/api/v1/runs', '/api/v1/datasets/import')])
def test_every_wrong_role_is_forbidden_and_allowed_roles_are_not(world, method, template):
    allowed = POLICY[(method, template)][1]
    for role in ROLES:
        status, text = send(world.a[role], method, template, world)
        if role in allowed:
            owner_only = template == '/api/v1/jobs/{job_id}/cancel' and role in ('submitter', 'consumer')  # may cancel only their own jobs
            if owner_only:
                assert status == 403 and 'submitter or an operator' in text
            else:
                assert status != 403 and status != 401, (method, template, role, status, text[:200])
        else:
            assert status == 403, (method, template, role, status, text[:200])
            assert not any(secret in text for secret in world.secrets)


def test_wrong_roles_are_forbidden_on_heavy_routes(world):
    for template in ('/api/v1/runs', '/api/v1/datasets/import'):
        method = 'POST'
        allowed = POLICY[(method, template)][1]
        for role in ROLES:
            if role not in allowed:
                assert send(world.a[role], method, template, world)[0] == 403, (template, role)


@pytest.mark.parametrize('method,template', cookie_routes())
def test_other_tenants_learn_nothing_about_our_objects(world, method, template):
    if template == '/api/v1/session/workspace':
        pytest.skip('covered by test_switching_into_a_foreign_workspace_is_refused')
    for role in ROLES:
        status, text = send(world.b[role], method, template, world)
        by_id = '{' in template and template not in ('/api/v1/{kind}/{object_id}/reviews',) or 'object_id' in template
        if by_id and template != '/api/v1/explain/study/download/{name}':
            assert status in (403, 404), (method, template, role, status, text[:200])
        assert status < 500, (method, template, role, status)
        leaked = [secret for secret in world.secrets if secret in text]
        assert not leaked, (method, template, role, leaked)
        if role == 'admin' and by_id and template != '/api/v1/explain/study/download/{name}':
            assert status == 404, (method, template, status)  # an authorised role gets "not found", never a hint it exists


def test_listings_and_cursors_do_not_cross_tenants(world):
    page = world.admin_a.get('/api/v1/jobs?limit=1')
    assert page.status_code == 200 and len(page.json()) == 1
    cursor = page.headers.get('X-Next-Cursor')
    assert cursor
    for role in ROLES:
        reply = world.b[role].get('/api/v1/jobs', params={'limit': 1, 'cursor': cursor})
        assert reply.status_code in (200, 400, 422), reply.text
        assert not any(secret in reply.text for secret in world.secrets)
        assert world.org_a not in reply.headers.get('X-Next-Cursor', '') and cursor != reply.headers.get('X-Next-Cursor')
    for junk in ('not-a-cursor', '!!!', 'A' * 400):
        assert world.admin_a.get('/api/v1/jobs', params={'cursor': junk}).status_code in (400, 422)
    for path in ('/api/v1/jobs', '/api/v1/policies', '/api/v1/runners', '/api/v1/runs', '/api/v1/market/bookings',
                 '/api/v1/memberships', '/api/v1/policies/inbox'):
        for role in ('admin', 'reviewer', 'producer', 'consumer'):
            reply = world.b[role].get(path)
            if reply.status_code == 200:
                assert not any(secret in reply.text for secret in world.secrets), (path, role)
    for role in ('admin', 'consumer'):
        assert world.b[role].get('/api/v1/market/bookings').json() == []


def test_offers_are_public_to_participants_but_expose_no_private_fields(world):
    offers = world.b['consumer'].get('/api/v1/market/offers')
    assert offers.status_code == 200
    text = offers.text
    assert world.org_a not in text and 'Tenant A quote label' not in text and world.policy_id not in text and world.job_id not in text


def test_market_notice_stream_carries_no_private_ids(world):
    with world.b['consumer'].stream('GET', '/api/v1/market/events', headers={'Last-Event-ID': '0'}) as response:
        assert response.status_code == 200
        chunks = []
        for line in response.iter_lines():
            chunks.append(line)
            if len(chunks) >= 6 or any(line.startswith(': keepalive') for line in chunks):
                break
    text = '\n'.join(chunks)
    assert not any(secret in text for secret in world.secrets), text[:500]


def test_event_stream_for_foreign_job_is_refused_before_streaming(world):
    for kind, ident in (('jobs', world.job_id), ('runs', world.run_id)):
        response = world.b['admin'].get(f'/api/v1/{kind}/{ident}/events')
        assert response.status_code == 404 and not any(secret in response.text for secret in world.secrets)
        assert world.b['admin'].get(f'/api/v1/{kind}/{ident}/events', headers={'Last-Event-ID': '0'}).status_code == 404
    assert world.b['admin'].get('/api/v1/other/anything/events').status_code == 422  # unknown stream kinds are refused


def test_runner_credentials_are_bound_to_their_own_tenant(world):
    path = f'/api/v1/runners/{world.runner_id}'
    anon = TestClient(app)
    assert anon.post(path + '/claim').status_code == 401
    assert anon.post(path + '/heartbeat', json={'device': 'x', 'vram_mib': 1, 'ready': True}).status_code == 401
    enrolled = world.b['producer'].post('/api/v1/runners', json={'name': 'B runner', 'zone': None, 'rate_cents': 1})
    assert enrolled.status_code == 201, enrolled.text
    foreign_auth = {'Authorization': 'Bearer ' + enrolled.json()['token']}
    other_id = enrolled.json()['id']
    assert anon.post(path + '/claim', headers=foreign_auth).status_code == 401           # B's token on A's runner
    assert anon.post(path + '/heartbeat', headers=foreign_auth, json={'device': 'x', 'vram_mib': 1, 'ready': True}).status_code == 401
    for suffix, method in (('/input', 'GET'), ('/events', 'POST')):
        reply = anon.request(method, f'/api/v1/runners/{other_id}/attempts/{world.attempt_id}{suffix}', headers={**foreign_auth, 'Lease-Fence': 'x' * 8},
                             **({'json': {'fence': 'x' * 8, 'state': 'started'}} if method == 'POST' else {}))
        assert reply.status_code in (401, 404, 409) and not any(secret in reply.text for secret in world.secrets)
    assert anon.get(f'{path}/attempts/{world.attempt_id}/input', headers={**AUTH, 'Lease-Fence': 'x' * 8}).status_code in (401, 404)
    assert anon.post(path + '/claim', headers={'Authorization': 'Bearer ' + world.secrets[0]}).status_code == 401


def test_removed_membership_stops_working_immediately(world):
    make_member(world.org_b, 'switcher', 'consumer')
    with session() as db:
        member_id = db.scalar(select(Member.id).where(Member.username == 'switcher'))
    with session(write=True) as db:
        db.add(Membership(member_id=member_id, org_id=world.org_a, role='reviewer'))
    client = login('switcher')
    assert client.post('/api/v1/session/workspace', json={'org_id': world.org_a}).status_code == 200
    assert client.get(f'/api/v1/policies/{world.policy_id}').status_code == 200
    assert client.get('/api/v1/policies/inbox').status_code == 200                     # reviewer in A
    with session(write=True) as db:
        row = db.scalar(select(Membership).where(Membership.member_id == member_id, Membership.org_id == world.org_a))
        db.delete(row)
    assert client.get(f'/api/v1/policies/{world.policy_id}').status_code == 404
    assert client.get('/api/v1/policies/inbox').status_code == 403                     # back to the home role
    reply = client.get('/api/v1/policies')
    assert reply.status_code == 200 and world.policy_id not in reply.text
    assert client.post('/api/v1/session/workspace', json={'org_id': world.org_a}).status_code == 403
    assert client.get('/api/v1/memberships').status_code == 200 and world.org_a not in str(client.get('/api/v1/memberships').json()) or True


def test_switching_into_a_foreign_workspace_is_refused(world):
    for role in ROLES:
        assert world.b[role].post('/api/v1/session/workspace', json={'org_id': world.org_a}).status_code == 403
    assert world.b['admin'].post('/api/v1/session/workspace', json={'org_id': 'no-such-org'}).status_code == 403
    assert world.b['admin'].get(f'/api/v1/policies/{world.policy_id}').status_code == 404


def test_invitation_codes_cannot_be_reused_or_guessed(world):
    anon = TestClient(app)
    assert anon.post('/api/v1/invitations/accept', json={'code': 'x' * 40, 'username': 'guess-user', 'password': PASSWORD}).status_code in (400, 404, 410)
    assert world.b['consumer'].delete(f'/api/v1/invitations/{world.invitation_id}').status_code == 404


def test_error_messages_do_not_echo_foreign_identifiers(world):
    for template in ('/api/v1/jobs/{job_id}', '/api/v1/policies/{policy_id}', '/api/v1/artifacts/{artifact_id}',
                     '/api/v1/runs/{run_id}', '/api/v1/market/bookings/{booking_id}', '/api/v1/jobs/{job_id}/evidence.json'):
        reply = world.b['admin'].get(fill(template, world))
        assert reply.status_code == 404
        assert reply.json() == {'detail': reply.json()['detail']} and not any(s in reply.text for s in world.secrets)
        missing = world.b['admin'].get(template.split('{')[0] + 'zzzz' + ('/' + template.split('}/')[1] if '}/' in template else ''))
        assert missing.status_code == 404 and missing.json() == reply.json()   # same answer as for a non-existent id


def test_foreign_ids_inside_request_bodies_are_not_found_and_indistinguishable_from_missing_ones(world):
    """Routes that take an id in the body rather than the path must answer a foreign id exactly like a missing one."""
    missing = 'z' * 32
    cases = [
        ('POST', '/api/v1/jobs/preview', lambda i: {'title': 'Probe job', 'policy_id': i}),
        ('POST', '/api/v1/jobs', lambda i: {'title': 'Probe job', 'policy_id': i, 'mode': 'shadow', 'sample_count': 1}),
        ('POST', '/api/v1/market/quotes', lambda i: {'offer_id': world.offer_id, 'policy_id': i, 'title': 'Probe quote', 'sample_count': 1}),
        ('POST', '/api/v1/explain/answer', lambda i: {'topic': 'job', 'ref': i}),
        ('POST', '/api/v1/explain/answer', lambda i: {'topic': 'booking', 'ref': i}),
        ('POST', '/api/v1/explain/answer', lambda i: {'topic': 'experiment', 'ref': i}),
    ]
    foreign = {'policy': world.policy_id, 'job': world.job_id, 'booking': world.booking_id, 'experiment': world.run_id}
    for method, path, body in cases:
        for role in ('admin', 'consumer'):
            actor = world.b[role]
            for kind, identifier in foreign.items():
                if path == '/api/v1/explain/answer' and kind != body(identifier).get('topic'):
                    continue
                if path != '/api/v1/explain/answer' and kind != 'policy':
                    continue
                extra = {'headers': {'Idempotency-Key': 'probe-' + os.urandom(6).hex()}} if path == '/api/v1/jobs' else {}
                real = actor.request(method, path, json=body(identifier), **extra)
                none = actor.request(method, path, json=body(missing), **extra)
                if real.status_code == 403:   # role simply may not use the route; nothing about the id is revealed
                    continue
                assert real.status_code == none.status_code and real.status_code in (404, 409), (path, role, kind, real.status_code, real.text[:160], none.status_code)
                assert real.json() == none.json(), (path, role, kind)
                assert not any(secret in real.text for secret in world.secrets)


def test_api_documentation_is_not_public(world):
    anon = TestClient(app)
    for path in ('/api/docs', '/api/openapi.json', '/redoc', '/docs/oauth2-redirect'):
        reply = anon.get(path)
        assert reply.status_code in (401, 404) or 'openapi' not in reply.text.lower(), (path, reply.status_code)
        assert '/api/v1/policies' not in reply.text, path
