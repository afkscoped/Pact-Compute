import base64
import binascii
import hmac
import io
import json
import math
import re
import secrets
import time
from typing import Literal

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import select

from . import storage
from .carbon import estimate, forecast_snapshot, power_bound
from .db import Artifact, Attempt, Job, Organization, Policy, Runner, record, save_artifact, scoped, sha
from .policy import deadline, exceeds, values

ACTIVE = ('reserved', 'dispatched', 'running', 'execution_unknown')
TERMINAL = ('succeeded', 'failed', 'cancelled', 'expired', 'rejected', 'recommended')
LEASE_SECONDS = 35
RUNNER_TTL = 25
MODEL = 'MobileNetV3-Large IMAGENET1K_V2'
TEMPLATE = 'image-embeddings-v1'


class LiveError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class ImageInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=1_400_000)


class JobInput(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    policy_id: str = Field(min_length=1, max_length=32)
    mode: Literal['live', 'shadow'] = 'live'
    flexible: bool = False
    sample_count: int = Field(default=4, ge=1, le=16)
    images: list[ImageInput] = Field(default_factory=list, max_length=16)


class Heartbeat(BaseModel):
    device: str = Field(min_length=1, max_length=200)
    vram_mib: int = Field(ge=0, le=2_000_000)
    ready: bool
    attempt_id: str | None = None
    fence: str | None = None


class RunnerUpdate(BaseModel):
    fence: str = Field(min_length=1, max_length=64)
    state: Literal['started', 'succeeded', 'failed', 'cancelled', 'expired', 'interrupted']
    duration_s: float | None = Field(default=None, ge=0, le=86400, allow_inf_nan=False)
    device: str | None = Field(default=None, max_length=200)
    gpu_energy_kwh: float | None = Field(default=None, ge=0, le=10, allow_inf_nan=False)
    power_samples: int = Field(default=0, ge=0, le=100_000)
    telemetry_coverage: float = Field(default=0, ge=0, le=1, allow_inf_nan=False)
    artifact: dict | None = None
    message: str | None = Field(default=None, max_length=500)


def organization_lock(db, org):
    # Serialize scheduling writes while allowing foreign keys to reference this organization.
    return db.scalar(select(Organization).where(Organization.id == org).with_for_update(key_share=True))


def lock_parties(db, *organizations):
    for org in sorted(set(organizations)):
        organization_lock(db, org)


def lock_job_parties(db, job):
    runner = db.get(Runner, job.runner_id) if job.runner_id else None
    lock_parties(db, job.org_id, runner.org_id if runner else job.org_id)
    db.refresh(job)


def active_policy(db, org, policy_id):
    policy = scoped(db, Policy, org, policy_id)
    if not policy:
        raise LiveError('Policy not found.', 404)
    if policy.status != 'approved':
        raise LiveError('Choose an approved policy version.', 409)
    return policy


def reason(code, message, rule=None):
    return {'code': code, 'message': message, 'rule': rule}


def predicted_seconds(count):
    return 38 + count * 3


def quote(rate, duration_s):
    return math.ceil(rate * duration_s / 3600)


def runner_online(runner, now):
    return runner.ready and now - runner.last_seen <= RUNNER_TTL and not runner.dispatch_paused


def expire_leases(db, runner_org, now):
    # The runner organization lock protects both its internal jobs and its marketplace jobs.
    runners = select(Runner.id).where(Runner.org_id == runner_org)
    active = db.execute(select(Attempt, Job).join(Job, Job.id == Attempt.job_id)
                        .where(Attempt.runner_id.in_(runners), Attempt.status.in_(['dispatched', 'running']),
                               Attempt.lease_until < now))
    for attempt, job in active:
        attempt.status = 'execution_unknown'
        job.status = 'execution_unknown'
        record(db, job.org_id, 'job', job.id, 'ExecutionUncertain', attempt_id=attempt.id,
               reason='Runner acknowledgement expired. The GPU remains reserved.')
    expired = db.scalars(select(Job).where(Job.runner_id.in_(runners), Job.status == 'reserved', Job.deadline_at <= now))
    for job in expired:
        job.status = 'expired'
        record(db, job.org_id, 'job', job.id, 'ReservationExpired', reason='The job deadline elapsed before dispatch.')
        record(db, job.org_id, 'job', job.id, 'CapacityReleased', runner_id=job.runner_id)


def placement(db, org, spec: JobInput, policy: Policy, now, *, offer=None):
    rules = policy.rules
    limits = values(rules)
    estimated_s = predicted_seconds(len(spec.images) or spec.sample_count)
    reservation_s = estimated_s + 45
    due = deadline(rules, now)
    budget = limits.get('max_charge_cents', 1000)
    candidates = []
    runners = [db.get(Runner, offer.runner_id)] if offer else db.scalars(
        select(Runner).where(Runner.org_id == org).order_by(Runner.id)).all()
    for runner in runners:
        base_reasons = []
        if not runner_online(runner, now):
            base_reasons.append(reason('runner_offline', 'This runner is paused, offline, or CUDA is unavailable.'))
        if limits.get('gpu_count', 1) != 1:
            base_reasons.append(reason('gpu_count', 'The native runner offers one exclusive GPU.', 'gpu_count'))
        if runner.vram_mib < limits.get('min_vram_mib', 0):
            base_reasons.append(reason('vram', f'{runner.vram_mib} MiB available in inventory.', 'min_vram_mib'))
        if limits.get('gpu_model', '').lower() not in runner.device.lower():
            base_reasons.append(reason('gpu_model', f'Runner device is {runner.device}.', 'gpu_model'))
        if limits.get('grid_zone', runner.zone) != runner.zone:
            base_reasons.append(reason('grid_zone', 'The runner grid zone does not match the contract.', 'grid_zone'))
        rate = offer.rate_cents if offer else runner.rate_cents
        if exceeds(rules, 'max_rate_cents', rate):
            base_reasons.append(reason('rate', 'The configured rate exceeds the approved limit.', 'max_rate_cents'))
        queue = db.scalars(select(Job).where(Job.runner_id == runner.id, Job.status.in_(ACTIVE))).all()
        next_slot = max(now, offer.starts_at) if offer else now
        if offer and offer.status != 'published':
            base_reasons.append(reason('offer_paused', 'The producer has paused this offer.'))
        for queued in queue:
            if queued.status == 'execution_unknown':
                base_reasons.append(reason('execution_unknown', 'An existing attempt requires reconciliation.'))
            next_slot = max(next_slot, queued.decision.get('reserved_until', now))
        if spec.flexible:
            max_delay = limits.get('max_deferral_seconds', 0)
            latest = now + max_delay if 'max_deferral_seconds' in limits else next_slot
        else:
            latest = next_slot
        spendable = budget - int(any(rule['kind'] == 'max_charge_cents' and rule['strict'] for rule in rules))
        if rate > 0:
            allowed_s = min(reservation_s, spendable * 3600 // rate)
        else:
            allowed_s = reservation_s
        if spendable < 0 or allowed_s < estimated_s:
            base_reasons.append(reason('budget', 'The cost envelope is too small for the predicted runtime.', 'max_charge_cents'))
        forecast = forecast_snapshot(runner.zone, now)
        bound = power_bound()
        starts = [next_slot]
        if spec.flexible and limits.get('prefer_low_carbon') and forecast and bound:
            starts += [x['start'] for x in forecast['intervals'] if next_slot < x['start'] <= latest][:16]
        for start in starts:
            reasons = list(base_reasons)
            reserved_until = min(start + allowed_s + 10, due, offer.ends_at if offer else due)
            if start > latest or start + estimated_s + 10 > due:
                reasons.append(reason('time_window', 'This reservation cannot meet the deferral or completion window.',
                                      'max_deferral_seconds' if start > latest else ('deadline_utc' if 'deadline_utc' in limits else 'deadline_seconds')))
            if offer and start + estimated_s + 10 > offer.ends_at:
                reasons.append(reason('offer_window', 'The available window is too short for this workload.'))
            carbon = estimate(forecast, start, reserved_until, bound) if bound else None
            if 'carbon_limit_g' in limits:
                if carbon is None:
                    reasons.append(reason('carbon_unknown', 'A current grid forecast and verified power envelope are required.', 'carbon_limit_g'))
                elif exceeds(rules, 'carbon_limit_g', math.ceil(carbon)):
                    reasons.append(reason('carbon_limit', 'Estimated emissions exceed the approved cap.', 'carbon_limit_g'))
            candidates.append({
                'runner_id': runner.id, 'runner_name': runner.name, 'device': runner.device, 'vram_mib': runner.vram_mib,
                'zone': runner.zone, 'gpu_count': 1, 'start': start, 'reserved_until': reserved_until, 'runtime_s': estimated_s,
                'max_runtime_s': max(0, min(allowed_s, math.floor(reserved_until - start))),
                'rate_cents': rate, 'quote_cents': quote(rate, estimated_s),
                'envelope_cents': quote(rate, max(0, min(allowed_s, math.floor(reserved_until - start)))),
                'estimated_carbon_g': round(carbon, 4) if carbon is not None else None,
                'forecast_source': forecast['source'] if forecast else None,
                'forecast_retrieved_at': forecast['retrieved_at'] if forecast else None,
                'forecast_intervals': [x for x in forecast['intervals'] if x['start'] < reserved_until and x['end'] > start] if forecast else [],
                'power_bound_w': bound, 'latest_start': latest if start > next_slot or latest > next_slot else None, 'reasons': reasons,
            })
    feasible = [c for c in candidates if not c['reasons']]
    if limits.get('prefer_low_carbon') and feasible and all(c['estimated_carbon_g'] is not None for c in feasible):
        feasible.sort(key=lambda c: (c['estimated_carbon_g'], c['start'], c['quote_cents']))
    else:
        feasible.sort(key=lambda c: (c['start'], c['quote_cents'], c['runner_id']))
    return {'policy_id': policy.id, 'deadline_at': due, 'selected': feasible[0] if feasible else None,
            'candidates': candidates, 'charge_unit': 'compute credits', 'template': TEMPLATE}


def prepared_images(spec: JobInput):
    images = []
    if not spec.images:
        for index in range(spec.sample_count):
            canvas = Image.new('RGB', (256, 256), ((index * 41) % 256, 64, 110))
            draw = ImageDraw.Draw(canvas)
            draw.ellipse((25 + index, 34, 226, 220), fill=(222, (index * 31) % 256, 52))
            draw.rectangle((12, 180 - index, 241, 204), fill=(25, 185, 127))
            images.append((f'sample-{index + 1:02d}.png', canvas))
    else:
        for upload in spec.images:
            try:
                raw = base64.b64decode(upload.content, validate=True)
                with Image.open(io.BytesIO(raw), formats=['PNG', 'JPEG', 'WEBP']) as image:
                    if image.width * image.height > 4_000_000:
                        raise LiveError(f'{upload.name} exceeds four megapixels.')
                    normalized = ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'), (256, 256))
                name = re.sub(r'[^A-Za-z0-9._-]', '_', upload.name)[:100]
                images.append((name, normalized))
            except (UnidentifiedImageError, Image.DecompressionBombError, OSError, binascii.Error, ValueError) as exc:
                raise LiveError(f'{upload.name} is not a supported PNG, JPEG or WebP.') from exc
    records = []
    for index, (name, image) in enumerate(images, start=1):
        output = io.BytesIO()
        image.save(output, format='PNG')
        content = output.getvalue()
        records.append({'row': index, 'name': name, 'sha256': sha(content), 'png': base64.b64encode(content).decode()})
    return json.dumps({'template': TEMPLATE, 'images': records}, separators=(',', ':')).encode()


def submit_job(db, member, spec, request_key, payload):
    now = time.time()
    organization_lock(db, member.org_id)
    existing = db.scalar(select(Job).where(Job.org_id == member.org_id, Job.request_key == request_key))
    fingerprint = sha(json.dumps(spec.model_dump(exclude={'images'}), sort_keys=True) + sha(payload))
    if existing:
        if existing.spec.get('request_hash') != fingerprint:
            raise LiveError('This idempotency key was used for a different submission.', 409)
        return existing
    expire_leases(db, member.org_id, now)
    policy = active_policy(db, member.org_id, spec.policy_id)
    preview = placement(db, member.org_id, spec, policy, now)
    return persist_job(db, member, spec, request_key, payload, fingerprint, now, preview)


def persist_job(db, member, spec, request_key, payload, fingerprint, now, preview, accepted=None):
    selected = preview['selected']
    job = Job(org_id=member.org_id, policy_id=spec.policy_id, submitted_by=member.id, request_key=request_key,
              runner_id=selected['runner_id'] if selected else None, title=spec.title, mode=spec.mode,
              status=('recommended' if spec.mode == 'shadow' else 'reserved') if selected else 'rejected',
              spec={'template': TEMPLATE, 'sample_count': len(spec.images) or spec.sample_count, 'flexible': spec.flexible,
                    'request_hash': fingerprint}, decision={'candidates': preview['candidates'], **(selected or {})},
              created_at=now, start_after=selected['start'] if selected else None, deadline_at=preview['deadline_at'])
    db.add(job)
    db.flush()
    if job.status == 'reserved':
        artifact = save_artifact(db, job.org_id, payload, 'input-manifest.json', 'input', job.id)
        job.spec = {**job.spec, 'input_id': artifact.id, 'input_sha256': artifact.digest}
    record(db, job.org_id, 'job', job.id, 'JobSubmitted', policy_id=spec.policy_id, mode=job.mode, template=TEMPLATE)
    if accepted:
        record(db, job.org_id, 'job', job.id, 'MarketQuoteAccepted', **accepted)
    record(db, job.org_id, 'job', job.id,
           {'reserved': 'CapacityReserved', 'recommended': 'ShadowRecommendation', 'rejected': 'AdmissionRejected'}[job.status],
           runner_id=job.runner_id, candidate_count=len(preview['candidates']), envelope_cents=job.decision.get('envelope_cents'))
    return job


def runner_identity(db, runner_id, authorization):
    runner = db.get(Runner, runner_id)
    raw = authorization.removeprefix('Bearer ') if authorization and authorization.startswith('Bearer ') else ''
    if not runner or not raw or not hmac.compare_digest(runner.token_digest, sha(raw)):
        raise LiveError('Runner authentication failed.', 401)
    return runner


def heartbeat(db, runner, update):
    organization_lock(db, runner.org_id)
    db.refresh(runner)
    now = time.time()
    previous_online = runner_online(runner, now)
    changed = (runner.device, runner.vram_mib) != (update.device, update.vram_mib)
    runner.device = update.device
    runner.vram_mib = update.vram_mib
    runner.ready = update.ready
    runner.last_seen = now
    if changed or previous_online != runner_online(runner, now):
        record(db, runner.org_id, 'market_capacity', runner.id, 'AvailabilityChanged')
    result = {'cancel_requested': False, 'pause': runner.dispatch_paused}
    if update.attempt_id:
        attempt = db.get(Attempt, update.attempt_id)
        if attempt and attempt.runner_id == runner.id and hmac.compare_digest(attempt.fence, update.fence or ''):
            job = db.get(Job, attempt.job_id)
            result['cancel_requested'] = job.cancel_requested
            if attempt.status in ('dispatched', 'running'):
                attempt.lease_until = now + LEASE_SECONDS
    return result


def claim(db, runner):
    organization_lock(db, runner.org_id)
    db.refresh(runner)
    now = time.time()
    expire_leases(db, runner.org_id, now)
    if not runner_online(runner, now) or db.scalar(select(Attempt.id).where(
            Attempt.runner_id == runner.id, Attempt.status.in_(['dispatched', 'running', 'execution_unknown'])).limit(1)):
        return None
    queued = db.scalars(select(Job).where(Job.runner_id == runner.id, Job.status == 'reserved', Job.start_after <= now)
                        .order_by(Job.start_after, Job.created_at, Job.id)).all()
    for job in queued:
        approved = db.get(Policy, job.policy_id)
        limits = values(approved.rules)
        decision = job.decision
        end = min(job.deadline_at, decision['reserved_until'])
        max_runtime = min(decision['max_runtime_s'], math.floor(end - now))
        snapshot = forecast_snapshot(runner.zone, now)
        bound = decision.get('power_bound_w')
        carbon_g = estimate(snapshot, now, now + max_runtime, bound) if bound else None
        grid_changed = 'grid_zone' in limits and limits['grid_zone'] != runner.zone
        invalid_carbon = 'carbon_limit_g' in limits and (
            carbon_g is None or exceeds(approved.rules, 'carbon_limit_g', math.ceil(carbon_g)))
        max_delay = limits.get('max_deferral_seconds', 0)
        late = job.spec['flexible'] and max_delay > 0 and now > job.created_at + max_delay
        valid = (approved.status == 'approved' and runner.vram_mib >= limits.get('min_vram_mib', 0)
                 and limits.get('gpu_model', '').lower() in runner.device.lower() and not grid_changed
                 and not invalid_carbon and not late and max_runtime >= decision['runtime_s'])
        if not valid:
            job.status = 'expired'
            record(db, job.org_id, 'job', job.id, 'DispatchRecheckFailed', deadline_at=job.deadline_at,
                   carbon_unknown=carbon_g is None, carbon_rejected=invalid_carbon, deferral_expired=late)
            record(db, job.org_id, 'job', job.id, 'CapacityReleased', runner_id=job.runner_id)
            continue
        attempt = Attempt(job_id=job.id, runner_id=runner.id, ordinal=1, fence=secrets.token_urlsafe(24),
                          status='dispatched', lease_until=now + LEASE_SECONDS)
        db.add(attempt)
        db.flush()
        job.status = 'dispatched'
        job.decision = {**decision, 'dispatch_estimated_carbon_g': round(carbon_g, 4) if carbon_g is not None else None,
                        'dispatch_forecast_retrieved_at': snapshot['retrieved_at'] if snapshot else None}
        record(db, job.org_id, 'job', job.id, 'JobDispatched', attempt_id=attempt.id, policy_id=job.policy_id,
               runner_id=runner.id, device=runner.device, vram_mib=runner.vram_mib, zone=runner.zone,
               max_runtime_s=max_runtime, estimated_carbon_g=job.decision['dispatch_estimated_carbon_g'],
               forecast_retrieved_at=job.decision['dispatch_forecast_retrieved_at'])
        return {'attempt_id': attempt.id, 'job_id': job.id, 'fence': attempt.fence, 'input_id': job.spec['input_id'],
                'input_sha256': job.spec['input_sha256'], 'template': TEMPLATE, 'max_runtime_s': max_runtime,
                'reserved_until': end}
    return None


def attempt_for_runner(db, runner, attempt_id, fence):
    attempt = db.get(Attempt, attempt_id)
    if not attempt or attempt.runner_id != runner.id or not hmac.compare_digest(attempt.fence, fence):
        raise LiveError('Attempt or lease not found.', 404)
    return attempt, db.get(Job, attempt.job_id)


def output_bytes(artifact, payload, device):
    source = json.loads(payload)
    items = artifact.get('items') if artifact else None
    if not isinstance(items, list) or len(items) != len(source['images']):
        raise LiveError('The output manifest must contain one row per input.')
    if artifact.get('model') != MODEL or not device or artifact.get('backend') != 'cuda':
        raise LiveError('The output must record the approved CUDA model and device.')
    for item, expected in zip(items, source['images'], strict=True):
        if not isinstance(item, dict) or any(item.get(k) != expected[k] for k in ('row', 'name', 'sha256')):
            raise LiveError('Output rows do not match the input manifest.')
        vector = item.get('embedding')
        if not isinstance(vector, list) or len(vector) != 960 or any(type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 1.01 for v in vector):
            raise LiveError('Output embeddings must contain 960 finite normalized values.')
        norm = math.sqrt(sum(v * v for v in vector))
        if not 0.99 <= norm <= 1.01:
            raise LiveError('Output embeddings must have unit norm.')
    return json.dumps(artifact, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()


def runner_update(db, runner, attempt_id, update):
    organization_lock(db, runner.org_id)
    attempt, job = attempt_for_runner(db, runner, attempt_id, update.fence)
    now = time.time()
    if attempt.status in TERMINAL:
        return {'status': attempt.status, 'duplicate': True}
    if update.state == 'started':
        if job.cancel_requested:
            raise LiveError('The operator cancelled this job.', 409)
        if now >= job.decision['reserved_until'] or attempt.status not in ('dispatched', 'running'):
            raise LiveError('This attempt is outside its dispatch window.', 409)
        if attempt.started_at is None:
            attempt.started_at = now
            attempt.status = job.status = 'running'
            record(db, job.org_id, 'job', job.id, 'JobStarted', attempt_id=attempt.id)
        attempt.lease_until = now + LEASE_SECONDS
        return {'status': 'running'}
    if update.state == 'succeeded' and attempt.started_at is None:
        raise LiveError('A successful attempt requires a recorded start.', 409)
    final = 'failed' if update.state == 'interrupted' else update.state
    result = update.model_dump(exclude={'fence', 'artifact', 'state'})
    if final == 'succeeded':
        input_artifact = db.get(Artifact, job.spec['input_id'])
        content = output_bytes(update.artifact, storage.store().get(input_artifact.digest), update.device)
        artifact = save_artifact(db, job.org_id, content, 'image-embeddings.json', 'output', job.id)
        result.update(artifact_id=artifact.id, sha256=artifact.digest, model=MODEL, rows=job.spec['sample_count'])
        inference = update.artifact.get('inference_seconds')
        if type(inference) in (int, float) and 0 <= inference <= 86400:
            result['inference_seconds'] = inference
    duration = update.duration_s if update.duration_s is not None else max(0, now - (attempt.started_at or now))
    result['charged_cents'] = quote(job.decision['rate_cents'], duration)
    result['charge_unit'] = 'internal compute credits'
    attempt.finished_at = now
    attempt.status = job.status = final
    attempt.result = result
    record(db, job.org_id, 'job', job.id, 'JobFinished', attempt_id=attempt.id, status=final, **result)
    record(db, job.org_id, 'job', job.id, 'CapacityReleased', runner_id=job.runner_id)
    return {'status': final}
