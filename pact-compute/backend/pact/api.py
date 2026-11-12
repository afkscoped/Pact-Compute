import json
import secrets
import threading
import time
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Cookie, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError

from . import datasets, live, market, ratelimit
from .resilience import retry_db
from .access import User, entity, require
from .audit import compliance
from .config import COOKIE_SECURE, FRONTEND, LLM_KEY, LLM_MODEL, SESSION_SECONDS, URL
from .db import Artifact, Attempt, Base, Event, FindingReview, Job, Login, MarketBooking, MarketQuote, Member, Organization, Policy, ResearchRun, Runner
from .db import artifact_path, engine, record, scoped, session, sha, sqlite, uid
from .policy import EXAMPLE, PolicyText, Revision, compile_local, parse_local, verify
from .research import Scenario
from .security import COOKIE, bootstrap, password_digest, password_ok, sign
from .market_api import router as market_router
from .explain import router as explain_router
from .membership import router as membership_router


@asynccontextmanager
async def startup(_app):
    if sqlite:
        Base.metadata.create_all(engine)
    bootstrap()
    yield


app = FastAPI(title='PACT-Compute', version='0.1.0', lifespan=startup, docs_url='/api/docs', openapi_url='/api/openapi.json')


@app.exception_handler(live.LiveError)
def live_error(_request, error):
    return JSONResponse({'detail': str(error)}, status_code=error.status)


@app.middleware('http')
async def browser_guard(request: Request, call_next):
    if request.url.path.startswith('/api/') and request.method in {'POST', 'PATCH', 'PUT', 'DELETE'}:
        size = request.headers.get('content-length')
        if size and (not size.isdecimal() or int(size) > 24_000_000):
            return JSONResponse({'detail': 'Request exceeds the upload limit.'}, status_code=413)
        origin = request.headers.get('origin')
        allow = {URL}
        if URL == 'http://127.0.0.1:8765':
            allow.add('http://localhost:8765')
        if (origin and origin not in allow) or request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'Cross-site write denied.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)
    workspace: Literal['producer', 'consumer', 'operations'] | None = None


class Registration(BaseModel):
    username: str = Field(pattern=r'^[a-z][a-z0-9._-]{1,63}$')
    password: str = Field(min_length=12, max_length=200)
    organization: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    role: Literal['producer', 'consumer']


class ReviewInput(BaseModel):
    finding_id: str = Field(min_length=1, max_length=80)
    disposition: Literal['confirmed', 'dismissed', 'needs_evidence']
    note: str = Field(min_length=5, max_length=1200)


class RunnerEnrollment(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    zone: str | None = Field(default=None, pattern=r'^[A-Z0-9_-]{2,20}$')
    rate_cents: int = Field(default=250, ge=0, le=100000)


class DispatchToggle(BaseModel):
    paused: bool


class ReconcileInput(BaseModel):
    note: str = Field(min_length=12, max_length=500)


login_attempts = 'login'
registration_attempts = 'register'
DUMMY = password_digest(secrets.token_hex(16))


Auth = Annotated[str | None, Header()]


def user_view(db, member):
    return {'id': member.id, 'username': member.username, 'role': member.role,
            'organization': db.get(Organization, member.org_id).name}


@app.get('/api/health')
def health():
    with session() as db:
        db.execute(select(Organization.id).limit(1))
    return {'status': 'ok', 'database': 'sqlite' if sqlite else 'postgresql'}


def limit_auth_attempts(request, bucket, limit, detail):
    # Shared across API replicas (database-backed sliding window per client address).
    ip = request.client.host if request.client else 'local'
    if ratelimit.hit(f'{bucket}:{ip}', limit, 60) is None:
        raise HTTPException(429, detail)


def create_session(db, member):
    token = secrets.token_urlsafe(32)
    db.add(Login(digest=sha(token), member_id=member.id, expires=time.time() + SESSION_SECONDS))
    return token


def set_session_cookie(response, token):
    response.set_cookie(COOKIE, token, httponly=True, secure=COOKIE_SECURE, samesite='strict', max_age=SESSION_SECONDS)


@app.post('/api/v1/accounts', status_code=201)
def register(body: Registration, request: Request, response: Response):
    limit_auth_attempts(request, registration_attempts, 6, 'Too many account creation attempts. Try again in a minute.')
    digest = password_digest(body.password)
    try:
        with session(write=True) as db:
            org = Organization(id=uid(), name=body.organization)
            db.add(org)
            db.flush()
            member = Member(org_id=org.id, username=body.username, password=digest, role=body.role)
            db.add(member)
            db.flush()
            token = create_session(db, member)
            result = user_view(db, member)
    except IntegrityError as error:
        with session() as db:
            if db.scalar(select(Member.id).where(Member.username == body.username)):
                raise HTTPException(409, 'This username is already taken.') from error
        raise
    set_session_cookie(response, token)
    return result


@app.post('/api/v1/session')
def login(body: Credentials, request: Request, response: Response):
    limit_auth_attempts(request, login_attempts, 12, 'Too many sign-in attempts. Try again in a minute.')
    with session(write=True) as db:
        member = db.scalar(select(Member).where(Member.username == body.username))
        if not password_ok(body.password, member.password if member else DUMMY) or not member:
            raise HTTPException(401, 'Incorrect username or password.')
        permitted = {'producer': ('producer',), 'consumer': ('consumer', 'submitter'),
                     'operations': ('admin', 'operator', 'reviewer', 'researcher')}
        if body.workspace and member.role not in permitted[body.workspace]:
            raise HTTPException(403, 'This account is assigned to a different workspace.')
        token = create_session(db, member)
        result = user_view(db, member)
    set_session_cookie(response, token)
    return result


@app.get('/api/v1/session')
def whoami(member: User):
    with session() as db:
        return user_view(db, member)


@app.delete('/api/v1/session')
def logout(response: Response, raw: Annotated[str | None, Cookie(alias=COOKIE)] = None):
    if raw:
        with session(write=True) as db:
            existing = db.get(Login, sha(raw))
            if existing:
                db.delete(existing)
    response.delete_cookie(COOKIE)
    return {'status': 'signed_out'}


def policy_view(policy, detail=False):
    return {'id': policy.id, 'title': policy.title, 'status': policy.status, 'created_at': policy.created_at,
            'approved_at': policy.approved_at, 'method': policy.method, 'parent_id': policy.parent_id,
            'rule_count': len(policy.rules), 'issue_count': len(policy.issues),
            **({'source': policy.source, 'source_hash': policy.source_hash, 'rules': policy.rules,
                'issues': policy.issues, 'approved_by': policy.approved_by} if detail else {})}


@app.get('/api/v1/config')
def capabilities(_member: User):
    return {'llm_available': bool(LLM_KEY and LLM_MODEL), 'example_contract': EXAMPLE,
            'database': 'SQLite' if sqlite else 'PostgreSQL', 'model': live.MODEL}


@app.get('/api/v1/policies')
def policies(member: User):
    with session() as db:
        return [policy_view(p) for p in db.scalars(select(Policy).where(Policy.org_id == member.org_id)
                                                  .order_by(desc(Policy.created_at)).limit(100))]


@app.post('/api/v1/policies', status_code=201)
def create_policy(body: PolicyText, member: User):
    require(member, 'admin', 'reviewer', 'submitter', 'consumer')
    rules, issues = compile_local(body.source)
    method = 'deterministic-v1'
    if body.method == 'llm':
        from .llm import suggest
        rules, issues, method = suggest(body.source)
    with session(write=True) as db:
        policy = Policy(org_id=member.org_id, title=body.title, source=body.source, source_hash=sha(body.source),
                        rules=[r.model_dump() for r in rules], issues=issues, method=method)
        db.add(policy)
        db.flush()
        record(db, member.org_id, 'policy', policy.id, 'PolicyExtracted', actor=member.id, method=method,
               source_hash=policy.source_hash, issues=len(issues))
        return policy_view(policy, True)


@app.get('/api/v1/policies/{policy_id}')
def policy_detail(policy_id: str, member: User):
    with session() as db:
        return policy_view(entity(db, Policy, member, policy_id), True)


@app.post('/api/v1/policies/{policy_id}/revisions', status_code=201)
def revision(policy_id: str, body: Revision, member: User):
    require(member, 'admin', 'reviewer')
    with session(write=True) as db:
        parent = entity(db, Policy, member, policy_id)
        _, extraction = parse_local(parent.source)
        unresolved = []
        accepted = {}
        for finding in extraction:
            explanation = body.resolutions.get(finding['id'], '').strip()
            if 5 <= len(explanation) <= 500:
                accepted[finding['id']] = explanation
            else:
                unresolved.append(finding)
        issues = unresolved + verify(parent.source, body.rules)
        policy = Policy(org_id=member.org_id, title=parent.title, source=parent.source, source_hash=parent.source_hash,
                        parent_id=parent.id, rules=[r.model_dump() for r in body.rules], issues=issues, method='reviewed-v1')
        db.add(policy)
        db.flush()
        record(db, member.org_id, 'policy', policy.id, 'PolicyRevised', parent_id=parent.id, actor=member.id,
               dispositions=accepted, issues=len(issues))
        return policy_view(policy, True)


@app.post('/api/v1/policies/{policy_id}/approve')
def approve(policy_id: str, member: User):
    require(member, 'admin', 'reviewer')
    with session(write=True) as db:
        policy = scoped(db, Policy, member.org_id, policy_id, lock=True)
        if not policy:
            raise HTTPException(404, 'Policy not found.')
        if policy.issues or not policy.rules:
            raise HTTPException(409, 'Resolve all contract findings before approval.')
        if policy.status == 'draft':
            policy.approved_at = time.time()
            policy.approved_by = member.id
            policy.status = 'approved'
            record(db, member.org_id, 'policy', policy.id, 'PolicyApproved', actor=member.id,
                   source_hash=policy.source_hash, rule_count=len(policy.rules))
        return policy_view(policy, True)


def runner_view(runner):
    now = time.time()
    return {'id': runner.id, 'name': runner.name, 'device': runner.device, 'vram_mib': runner.vram_mib,
            'zone': runner.zone, 'rate_cents': runner.rate_cents, 'last_seen': runner.last_seen, 'ready': runner.ready,
            'online': live.runner_online(runner, now), 'paused': runner.dispatch_paused}


@app.get('/api/v1/runners')
def runners(member: User):
    with session() as db:
        return [runner_view(runner) for runner in db.scalars(select(Runner).where(Runner.org_id == member.org_id))]


@app.post('/api/v1/runners', status_code=201)
def enroll_runner(body: RunnerEnrollment, member: User):
    require(member, 'admin', 'operator', 'producer')
    runner_id = 'rn-' + secrets.token_hex(8)
    token = sign({'purpose': 'runner-enrollment-v1', 'runner': runner_id})
    with session(write=True) as db:
        runner = Runner(id=runner_id, org_id=member.org_id, name=body.name, token_digest=sha(token),
                        zone=body.zone, rate_cents=body.rate_cents)
        db.add(runner)
        db.flush()
        record(db, member.org_id, 'runner', runner.id, 'RunnerEnrolled', actor=member.id)
        return {**runner_view(runner), 'token': token}


@app.patch('/api/v1/runners/{runner_id}/dispatch')
def pause(runner_id: str, body: DispatchToggle, member: User):
    require(member, 'admin', 'operator', 'producer')
    with session(write=True) as db:
        live.organization_lock(db, member.org_id)
        runner = entity(db, Runner, member, runner_id)
        runner.dispatch_paused = body.paused
        record(db, member.org_id, 'runner', runner.id, 'DispatchPaused' if body.paused else 'DispatchResumed', actor=member.id)
        record(db, member.org_id, 'market_capacity', runner.id, 'AvailabilityChanged')
        return runner_view(runner)


def event_view(event):
    return {'seq': event.seq, 'kind': event.kind, 'at': event.at, 'details': event.details}


def event_rows(db, org, entity_type, entity_id, since=0):
    return list(db.scalars(select(Event).where(Event.org_id == org, Event.entity_type == entity_type,
                                             Event.entity_id == entity_id, Event.seq > since).order_by(Event.seq).limit(1000)))


def job_view(job, detailed=False):
    return {'id': job.id, 'title': job.title, 'policy_id': job.policy_id, 'status': job.status,
            'mode': job.mode, 'created_at': job.created_at, 'start_after': job.start_after,
            'deadline_at': job.deadline_at, 'runner_id': job.runner_id, 'cancel_requested': job.cancel_requested,
            'sample_count': job.spec['sample_count'], 'flexible': job.spec['flexible'],
            **({'decision': job.decision, 'input_sha256': job.spec.get('input_sha256')} if detailed else {})}


def review_views(db, org, kind, item_id):
    stmt = select(FindingReview).where(FindingReview.org_id == org, FindingReview.entity_type == kind,
                                       FindingReview.entity_id == item_id).order_by(FindingReview.at)
    return [{'id': row.id, 'finding_id': row.finding_id, 'disposition': row.disposition, 'note': row.note, 'at': row.at}
            for row in db.scalars(stmt)]


def job_detail_view(db, job):
    policy = db.get(Policy, job.policy_id)
    events = event_rows(db, job.org_id, 'job', job.id)
    attempts = db.scalars(select(Attempt).where(Attempt.job_id == job.id).order_by(Attempt.ordinal)).all()
    booking = db.scalar(select(MarketBooking).where(MarketBooking.job_id == job.id))
    quote = db.get(MarketQuote, booking.quote_id) if booking else None
    return {**job_view(job, True), 'policy': policy_view(policy, True),
            'events': [event_view(row) for row in events],
            'attempts': [{'id': a.id, 'status': a.status, 'started_at': a.started_at,
                          'finished_at': a.finished_at, 'result': a.result} for a in attempts],
            'findings': compliance(job, policy, events, attempts), 'reviews': review_views(db, job.org_id, 'job', job.id),
            'protocol': market.trace(db, job, quote)}


@app.get('/api/v1/jobs')
def jobs(member: User):
    with session() as db:
        return [job_view(job) for job in db.scalars(select(Job).where(Job.org_id == member.org_id)
                                                   .order_by(desc(Job.created_at)).limit(100))]


@app.post('/api/v1/jobs/preview')
def preview_job(body: live.JobInput, member: User):
    with session() as db:
        policy = live.active_policy(db, member.org_id, body.policy_id)
        return live.placement(db, member.org_id, body, policy, time.time())


@app.post('/api/v1/jobs', status_code=201)
@retry_db
def submit_job(body: live.JobInput, member: User, idempotency_key: Annotated[str, Header(min_length=8, max_length=120)]):
    require(member, 'admin', 'operator', 'submitter')
    payload = live.prepared_images(body)
    with session(write=True) as db:
        return job_view(live.submit_job(db, member, body, idempotency_key, payload), True)


@app.get('/api/v1/jobs/{job_id}')
def job_detail(job_id: str, member: User):
    with session() as db:
        return job_detail_view(db, entity(db, Job, member, job_id))


@app.post('/api/v1/jobs/{job_id}/cancel')
@retry_db
def cancel(job_id: str, member: User):
    require(member, 'admin', 'operator', 'submitter', 'consumer')
    with session(write=True) as db:
        job = entity(db, Job, member, job_id)
        live.lock_job_parties(db, job)
        if member.role in ('submitter', 'consumer') and job.submitted_by != member.id:
            raise HTTPException(403, 'Only the submitter or an operator may cancel this job.')
        if job.status in live.TERMINAL:
            raise HTTPException(409, 'This job has already reached a final state.')
        if not job.cancel_requested:
            job.cancel_requested = True
            if job.status == 'reserved':
                job.status = 'cancelled'
            record(db, job.org_id, 'job', job.id, 'CancellationRequested', actor=member.id)
            if job.status == 'cancelled':
                record(db, job.org_id, 'job', job.id, 'ReservationCancelled')
                record(db, job.org_id, 'job', job.id, 'CapacityReleased', runner_id=job.runner_id)
        return job_view(job)


@app.post('/api/v1/jobs/{job_id}/reconcile')
def reconcile(job_id: str, body: ReconcileInput, member: User):
    require(member, 'admin', 'operator')
    with session(write=True) as db:
        job = entity(db, Job, member, job_id)
        live.lock_job_parties(db, job)
        if job.status != 'execution_unknown' or time.time() < job.decision.get('reserved_until', 0):
            raise HTTPException(409, 'The attempt is not eligible for operator reconciliation.')
        attempt = db.scalar(select(Attempt).where(Attempt.job_id == job.id, Attempt.status == 'execution_unknown'))
        if not attempt:
            raise HTTPException(409, 'The uncertain attempt is unavailable.')
        attempt.status = job.status = 'failed'
        attempt.finished_at = time.time()
        attempt.result = {'message': 'Operator confirmed the original process stopped.', 'charged_cents': None}
        record(db, job.org_id, 'job', job.id, 'ExecutionReconciled', actor=member.id, attempt_id=attempt.id, note=body.note)
        record(db, job.org_id, 'job', job.id, 'CapacityReleased', runner_id=job.runner_id)
        return job_view(job)


@app.post('/api/v1/runners/{runner_id}/heartbeat')
@retry_db
def heartbeat(runner_id: str, body: live.Heartbeat, authorization: Auth = None):
    with session(write=True) as db:
        return live.heartbeat(db, live.runner_identity(db, runner_id, authorization), body)


@app.post('/api/v1/runners/{runner_id}/claim')
@retry_db
def claim(runner_id: str, authorization: Auth = None):
    with session(write=True) as db:
        return live.claim(db, live.runner_identity(db, runner_id, authorization))


@app.get('/api/v1/runners/{runner_id}/attempts/{attempt_id}/input')
def input_manifest(runner_id: str, attempt_id: str, lease_fence: Annotated[str, Header()], authorization: Auth = None):
    with session() as db:
        runner = live.runner_identity(db, runner_id, authorization)
        attempt, job = live.attempt_for_runner(db, runner, attempt_id, lease_fence)
        if attempt.status not in ('dispatched', 'running') or attempt.lease_until < time.time():
            raise HTTPException(409, 'The execution lease is no longer valid.')
        artifact = db.get(Artifact, job.spec['input_id'])
        return FileResponse(artifact_path(artifact.digest), media_type='application/json')


@app.post('/api/v1/runners/{runner_id}/attempts/{attempt_id}/events')
@retry_db
def attempt_events(runner_id: str, attempt_id: str, body: live.RunnerUpdate, authorization: Auth = None):
    with session(write=True) as db:
        return live.runner_update(db, live.runner_identity(db, runner_id, authorization), attempt_id, body)


@app.get('/api/v1/artifacts/{artifact_id}')
def artifact(artifact_id: str, member: User):
    with session() as db:
        file = entity(db, Artifact, member, artifact_id)
        if not artifact_path(file.digest).is_file():
            raise HTTPException(410, 'Artifact bytes are unavailable.')
        return FileResponse(artifact_path(file.digest), filename=file.filename, media_type='application/json',
                            headers={'X-Content-SHA256': file.digest})


@app.get('/api/v1/datasets')
def dataset_list(_member: User):
    return datasets.available()


@app.post('/api/v1/datasets/import')
def dataset_import(member: User):
    require(member, 'admin', 'operator')
    try:
        return datasets.import_sources()
    except (ValueError, OSError, KeyError) as exc:
        raise HTTPException(422, f'Import failed: {exc}') from exc


def run_view(run, detail=False):
    return {'id': run.id, 'title': run.config['scenario']['title'], 'created_at': run.created_at,
            'finished_at': run.finished_at, 'status': run.status, 'progress': run.progress,
            'jobs': run.config['scenario']['jobs'], 'seeds': run.config['scenario']['seeds'],
            **({'config': run.config, 'result': run.result, 'error': run.error, 'artifact_id': run.artifact_id} if detail else {})}


@app.get('/api/v1/runs')
def runs(member: User):
    with session() as db:
        return [run_view(run) for run in db.scalars(select(ResearchRun).where(ResearchRun.org_id == member.org_id)
                                                   .order_by(desc(ResearchRun.created_at)).limit(100))]


@app.post('/api/v1/runs', status_code=202)
def start_run(body: Scenario, member: User):
    require(member, 'admin', 'operator', 'researcher')
    if not any(card['id'] == body.dataset_id for card in datasets.available()):
        raise HTTPException(422, 'Import and select an available dataset snapshot.')
    with session(write=True) as db:
        live.organization_lock(db, member.org_id)
        queued = db.scalars(select(ResearchRun.id).where(ResearchRun.org_id == member.org_id,
                                                       ResearchRun.status.in_(['queued', 'running'])).limit(4)).all()
        if len(queued) >= 4:
            raise HTTPException(409, 'The workspace already has four queued or active research runs.')
        policy = live.active_policy(db, member.org_id, body.policy_id) if body.policy_id else None
        run = ResearchRun(org_id=member.org_id, created_by=member.id, status='queued',
                          config={'scenario': body.model_dump(), 'rules': policy.rules if policy else [],
                                  'policy_hash': policy.source_hash if policy else None})
        db.add(run)
        db.flush()
        record(db, run.org_id, 'run', run.id, 'ExperimentQueued', seed=body.seed, dataset=body.dataset_id)
        return run_view(run)


@app.get('/api/v1/runs/{run_id}')
def run_detail(run_id: str, member: User):
    with session() as db:
        run = entity(db, ResearchRun, member, run_id)
        return {**run_view(run, True), 'events': [event_view(event) for event in event_rows(db, run.org_id, 'run', run.id)],
                'reviews': review_views(db, run.org_id, 'run', run.id)}


@app.get('/api/v1/runs/{run_id}/metrics.csv')
def metrics_csv(run_id: str, member: User):
    import csv
    import io

    with session() as db:
        run = entity(db, ResearchRun, member, run_id)
        if not run.result:
            raise HTTPException(409, 'The experiment has no completed results.')
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['run_id', 'arm', 'metric', 'mean'])
        for arm, metrics in run.result['summary'].items():
            writer.writerows((run_id, arm, metric, value) for metric, value in metrics.items())
        return Response(output.getvalue(), media_type='text/csv',
                        headers={'Content-Disposition': f'attachment; filename="metrics-{run_id}.csv"'})


@app.post('/api/v1/{kind}/{object_id}/reviews', status_code=201)
def review(kind: Literal['jobs', 'runs'], object_id: str, body: ReviewInput, member: User):
    require(member, 'admin', 'reviewer')
    with session(write=True) as db:
        if kind == 'jobs':
            obj = entity(db, Job, member, object_id)
            known = {f['id'] for f in job_detail_view(db, obj)['findings']}
            entity_type = 'job'
        else:
            obj = entity(db, ResearchRun, member, object_id)
            known = {f['provider'] for f in (obj.result or {}).get('first_episode', {}).get('audits', [])}
            entity_type = 'run'
        if body.finding_id not in known:
            raise HTTPException(404, 'Finding not found.')
        row = FindingReview(org_id=member.org_id, member_id=member.id, entity_type=entity_type,
                            entity_id=object_id, finding_id=body.finding_id, disposition=body.disposition, note=body.note)
        db.add(row)
        db.flush()
        record(db, member.org_id, entity_type, object_id, 'FindingReviewed', review_id=row.id, finding=body.finding_id,
               disposition=body.disposition, actor=member.id)
        return {'id': row.id}


@app.get('/api/v1/jobs/{job_id}/evidence.json')
def job_export(job_id: str, member: User):
    with session() as db:
        job = entity(db, Job, member, job_id)
        result = job_detail_view(db, job)
        # The full contract is tenant-private. The export is available only to authenticated members.
        manifest = {'schema': 'pact-job-evidence-1', 'job': result}
        return JSONResponse({'manifest': manifest, 'hmac_sha256': sign(manifest)},
                            headers={'Content-Disposition': f'attachment; filename="evidence-{job_id}.json"'})


@app.get('/api/v1/{kind}/{object_id}/events')
def event_stream(kind: Literal['jobs', 'runs'], object_id: str, member: User, last_event_id: Annotated[str | None, Header()] = None):
    model, entity_type = (Job, 'job') if kind == 'jobs' else (ResearchRun, 'run')
    with session() as db:
        entity(db, model, member, object_id)
    cursor = int(last_event_id) if last_event_id and last_event_id.isdecimal() else 0

    def messages():
        nonlocal cursor
        until = time.monotonic() + 22
        while time.monotonic() < until:
            with session() as db:
                batch = [event_view(row) for row in event_rows(db, member.org_id, entity_type, object_id, cursor)]
            if batch:
                for item in batch:
                    cursor = item['seq']
                    yield f'id: {cursor}\ndata: {json.dumps(item)}\n\n'
            else:
                yield ': keepalive\n\n'
            time.sleep(1)

    return StreamingResponse(messages(), media_type='text/event-stream', headers={'X-Accel-Buffering': 'no'})


app.include_router(market_router)
app.include_router(explain_router)
app.include_router(membership_router)

if (FRONTEND / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=FRONTEND / 'assets'), name='web-assets')


@app.get('/{path:path}', include_in_schema=False)
def frontend(path: str):
    if path.startswith('api/') or path.startswith('assets/'):
        raise HTTPException(404, 'Endpoint not found.')
    if not (FRONTEND / 'index.html').is_file():
        return Response('Build the React console with npm run build in frontend.', status_code=503, media_type='text/plain')
    return FileResponse(FRONTEND / 'index.html')
