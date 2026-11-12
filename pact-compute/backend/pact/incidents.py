"""Operator incident queue.

Incidents are derived from existing state (runner heartbeats, attempts, job events), so nothing is duplicated and nothing can
drift. Ownership and resolution are stored in `incident_records`. Reconciliation reuses `live.reconcile_attempt`.

Scope: an operator sees incidents for their own organization's jobs and for jobs that ran on their own runners. For another
organization's job only structured facts are shown (event kinds and sequence numbers, never titles or payloads)."""
import time
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import or_, select

from . import live, market
from .access import User, require
from .db import Attempt, Event, IncidentRecord, Job, MarketBooking, Runner, record, scoped, session, sha

router = APIRouter(prefix='/api/v1', tags=['incidents'])
OPERATORS = ('admin', 'operator')
KINDS = ('stale_runner', 'uncertain_attempt', 'failed_output', 'adjustment_request')
LIMIT = 100
TITLES = {'stale_runner': 'Runner stopped reporting', 'uncertain_attempt': 'Execution is uncertain',
          'failed_output': 'Output was rejected', 'adjustment_request': 'Charge adjustment requested'}


class Resolution(BaseModel):
    resolution: Annotated[str, StringConstraints(strip_whitespace=True, min_length=12, max_length=500)]
    action: Literal['none', 'reconcile'] = 'none'
    outcome: Literal['accepted', 'declined'] | None = None


class AdjustmentRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=12, max_length=500)]
    requested_cents: int | None = Field(default=None, ge=0, le=1_000_000)


def incident_id(org, kind, subject, episode):
    return 'inc-' + sha(f'{org}|{kind}|{subject}|{episode}')[:24]


def evidence_for(events, kinds, own):
    rows = [e for e in events if e.kind in kinds]
    return [{'type': 'event', 'seq': e.seq, 'kind': e.kind, **({'at': e.at} if own else {})} for e in rows[-3:]]


def public_label(job):
    return f'Image embedding batch ({job.spec["sample_count"]} images)'


def derive(db, member, now):
    """Currently active incidents for this organization, before ownership overlays."""
    org = member.org_id
    out = []
    for runner in db.scalars(select(Runner).where(Runner.org_id == org).order_by(Runner.id)):
        if runner.last_seen > 0 and not runner.dispatch_paused and now - runner.last_seen > live.RUNNER_TTL:
            out.append({'id': incident_id(org, 'stale_runner', runner.id, int(runner.last_seen)), 'kind': 'stale_runner',
                        'subject': {'type': 'runner', 'id': runner.id, 'label': runner.name}, 'opened_at': runner.last_seen + live.RUNNER_TTL,
                        'summary': f'No heartbeat for {int(now - runner.last_seen)} seconds.', 'evidence': [{'type': 'link', 'href': '/capacity', 'label': 'Compute capacity'}],
                        'jobs': [], 'details': {'last_seen': runner.last_seen}})
    jobs = db.execute(select(Job, Runner).join(Runner, Runner.id == Job.runner_id)
                      .where(or_(Job.org_id == org, Runner.org_id == org), Job.status.in_(['execution_unknown', 'failed']))
                      .order_by(Job.created_at.desc()).limit(LIMIT * 2)).all()
    events = {}
    if jobs:
        for e in db.scalars(select(Event).where(Event.entity_type == 'job', Event.entity_id.in_([j.id for j, _ in jobs]),
                                                Event.kind.in_(['ExecutionUncertain', 'JobFinished', 'ExecutionReconciled'])).order_by(Event.seq)):
            events.setdefault(e.entity_id, []).append(e)
    bookings = {}
    if jobs:
        bookings = {b.job_id: b.id for b in db.scalars(select(MarketBooking).where(MarketBooking.job_id.in_([j.id for j, _ in jobs])))}
    for job, runner in jobs:
        own = job.org_id == org
        label = job.title if own else public_label(job)
        href = ('/jobs/' + job.id) if own else ('/bookings/' + bookings[job.id] if job.id in bookings else None)
        links = [{'type': 'link', 'href': href, 'label': 'Open the ' + ('job' if own else 'booking')}] if href else []
        attempt = db.scalar(select(Attempt).where(Attempt.job_id == job.id).order_by(Attempt.ordinal.desc()).limit(1))
        if not attempt:
            continue
        subject = {'type': 'job', 'id': job.id if own else (bookings.get(job.id) or job.id), 'label': label}
        if job.status == 'execution_unknown' and attempt.status == 'execution_unknown':
            seen = events.get(job.id, [])
            out.append({'id': incident_id(org, 'uncertain_attempt', job.id, attempt.id), 'kind': 'uncertain_attempt', 'subject': subject,
                        'opened_at': next((e.at for e in reversed(seen) if e.kind == 'ExecutionUncertain'), now),
                        'summary': 'The runner stopped acknowledging the attempt. Capacity stays held until the original process is confirmed stopped.',
                        'evidence': evidence_for(seen, ('ExecutionUncertain',), own) + links, 'jobs': [job.id],
                        'details': {'attempt_id': attempt.id, 'reserved_until': job.decision.get('reserved_until'), 'own_job': own}})
        elif job.status == 'failed' and attempt.status == 'failed' and (attempt.result or {}).get('message') == live.OUTPUT_REJECTED:
            seen = events.get(job.id, [])
            out.append({'id': incident_id(org, 'failed_output', job.id, attempt.id), 'kind': 'failed_output', 'subject': subject,
                        'opened_at': attempt.finished_at or job.created_at, 'summary': 'The runner finished but the control plane rejected the output manifest.',
                        'evidence': evidence_for(seen, ('JobFinished',), own) + links, 'jobs': [job.id],
                        'details': {'attempt_id': attempt.id, 'own_job': own}})
    return out


def adjustment_items(db, member):
    out = []
    for row in db.scalars(select(IncidentRecord).where(IncidentRecord.org_id == member.org_id, IncidentRecord.kind == 'adjustment_request')
                          .order_by(IncidentRecord.created_at.desc()).limit(LIMIT)):
        out.append({'id': row.id, 'kind': 'adjustment_request', 'subject': {'type': 'booking', 'id': row.subject_id, 'label': 'Booking ' + row.subject_id[:8]},
                    'opened_at': row.created_at, 'summary': 'A buyer asked for a charge adjustment: ' + row.details.get('reason', ''),
                    'evidence': [{'type': 'link', 'href': '/bookings/' + row.subject_id, 'label': 'Open the booking and receipt'}],
                    'jobs': [], 'details': {'requested_cents': row.details.get('requested_cents')}})
    return out


def actions_for(item, now):
    kind, details = item['kind'], item['details']
    if kind == 'stale_runner':
        return [{'id': 'pause_dispatch', 'label': 'Pause dispatch to this runner', 'api': f"PATCH /api/v1/runners/{item['subject']['id']}/dispatch"},
                {'id': 'note', 'label': 'Record that you checked the host'}]
    if kind == 'uncertain_attempt':
        eligible = details['own_job'] and now >= (details.get('reserved_until') or 0)
        if eligible:
            return [{'id': 'reconcile', 'label': 'Confirm the original process stopped and release capacity', 'executes': True}]
        why = 'This job belongs to another organization; only its owner can reconcile it.' if not details['own_job'] else 'Wait until the reserved window has elapsed.'
        return [{'id': 'wait', 'label': why}]
    if kind == 'failed_output':
        return [{'id': 'note', 'label': 'Record the cause and how it was handled'}]
    return [{'id': 'accepted', 'label': 'Accept the adjustment request (records the decision; no ledger entry is made)'},
            {'id': 'declined', 'label': 'Decline the adjustment request'}]


def view(item, record_row, names, now):
    status = record_row.status if record_row else 'open'
    public = {k: v for k, v in item['details'].items() if k in ('reserved_until', 'own_job', 'last_seen', 'requested_cents')}
    return {**{k: v for k, v in item.items() if k not in ('jobs', 'details')}, 'details': public, 'title': TITLES[item['kind']], 'status': status, 'owner': names.get(record_row.owner_id) if record_row else None,
            'resolution': record_row.resolution if record_row else None, 'outcome': record_row.outcome if record_row else None,
            'resolved_at': record_row.resolved_at if record_row else None,
            'permitted_actions': [] if status == 'resolved' else actions_for(item, now)}


def names_for(db, rows):
    from .db import Member
    ids = {i for row in rows for i in (row.owner_id, row.resolved_by) if i}
    return {m.id: m.username for m in db.scalars(select(Member).where(Member.id.in_(ids)))} if ids else {}


def current(db, member, now):
    items = derive(db, member, now) + adjustment_items(db, member)
    rows = {r.id: r for r in db.scalars(select(IncidentRecord).where(IncidentRecord.org_id == member.org_id)
                                        .order_by(IncidentRecord.created_at.desc()).limit(LIMIT * 3))}
    return items, rows


@router.get('/incidents')
def incidents(member: User, status: Annotated[Literal['active', 'resolved', 'all'], Query()] = 'active'):
    require(member, *OPERATORS)
    now = time.time()
    with session() as db:
        items, rows = current(db, member, now)
        names = names_for(db, rows.values())
        shown = [view(item, rows.get(item['id']), names, now) for item in items]
        live_ids = {item['id'] for item in items}
        history = [{'id': r.id, 'kind': r.kind, 'title': TITLES.get(r.kind, r.kind), 'status': 'resolved', 'owner': names.get(r.owner_id),
                    'subject': {'type': r.subject_type, 'id': r.subject_id, 'label': r.subject_type + ' ' + r.subject_id[:8]},
                    'opened_at': r.created_at, 'summary': 'Resolved earlier.', 'evidence': [], 'jobs': [], 'details': {},
                    'resolution': r.resolution, 'outcome': r.outcome, 'resolved_at': r.resolved_at, 'permitted_actions': []}
                   for r in rows.values() if r.status == 'resolved' and r.id not in live_ids]
        everything = shown + history
        if status == 'active':
            everything = [row for row in everything if row['status'] != 'resolved']
        elif status == 'resolved':
            everything = [row for row in everything if row['status'] == 'resolved']
        everything.sort(key=lambda row: -row['opened_at'])
        return everything[:LIMIT]


def find(db, member, incident, now):
    items, rows = current(db, member, now)
    item = next((i for i in items if i['id'] == incident), None)
    if not item:
        if rows.get(incident) and rows[incident].status == 'resolved':   # the cause is gone, the record remains
            raise HTTPException(409, 'This incident was already resolved.')
        raise HTTPException(404, 'Record not found.')
    return item, rows.get(incident)


@router.post('/incidents/{incident}/claim')
def claim(incident: str, member: User):
    require(member, *OPERATORS)
    now = time.time()
    with session(write=True) as db:
        item, row = find(db, member, incident, now)
        if row and row.status == 'resolved':
            raise HTTPException(409, 'This incident was already resolved.')
        if row and row.owner_id and row.owner_id != member.id:
            raise HTTPException(409, 'Another operator owns this incident.')
        if not row:
            row = IncidentRecord(id=incident, org_id=member.org_id, kind=item['kind'], subject_type=item['subject']['type'],
                                 subject_id=item['subject']['id'], status='claimed', owner_id=member.id, details={}, created_at=now)
            db.add(row)
        row.status, row.owner_id = 'claimed', member.id
        record(db, member.org_id, 'incident', incident, 'IncidentClaimed', actor=member.id, incident_kind=item['kind'])
        return view(item, row, {member.id: member.username}, now)


@router.post('/incidents/{incident}/resolve')
def resolve(incident: str, body: Resolution, member: User):
    require(member, *OPERATORS)
    now = time.time()
    with session(write=True) as db:
        item, row = find(db, member, incident, now)
        if row and row.status == 'resolved':
            raise HTTPException(409, 'This incident was already resolved.')
        if row and row.owner_id and row.owner_id != member.id:
            raise HTTPException(409, 'Another operator owns this incident.')
        allowed = {a['id'] for a in actions_for(item, now)}
        kind = item['kind']
        if kind == 'uncertain_attempt':
            if body.action != 'reconcile' or 'reconcile' not in allowed:
                raise HTTPException(409, 'An uncertain attempt is resolved by confirming the process stopped. ' + actions_for(item, now)[0]['label'])
            job = scoped(db, Job, member.org_id, item['jobs'][0], lock=True)
            if not job:
                raise HTTPException(404, 'Record not found.')
            live.lock_job_parties(db, job)
            live.reconcile_attempt(db, member, job, body.resolution)
        elif body.action != 'none':
            raise HTTPException(422, 'This incident has no executable action.')
        if kind == 'adjustment_request':
            if not body.outcome:
                raise HTTPException(422, 'Record whether the adjustment was accepted or declined.')
        elif body.outcome:
            raise HTTPException(422, 'Only adjustment requests have an accept or decline outcome.')
        if not row:
            row = IncidentRecord(id=incident, org_id=member.org_id, kind=kind, subject_type=item['subject']['type'],
                                 subject_id=item['subject']['id'], status='claimed', details={}, created_at=now)
            db.add(row)
        row.status, row.owner_id = 'resolved', row.owner_id or member.id
        row.resolution, row.outcome, row.resolved_by, row.resolved_at = body.resolution, body.outcome, member.id, now
        record(db, member.org_id, 'incident', incident, 'IncidentResolved', actor=member.id, incident_kind=kind, action=body.action,
               outcome=body.outcome, resolution=body.resolution)
        return view(item, row, {member.id: member.username}, now)


@router.post('/market/bookings/{booking_id}/adjustments', status_code=201)
def request_adjustment(booking_id: str, body: AdjustmentRequest, member: User):
    require(member, *market.BUYERS)
    with session(write=True) as db:
        booking = db.get(MarketBooking, booking_id)
        if not booking or booking.consumer_org_id != member.org_id:
            raise HTTPException(404, 'Booking not found.')
        job = db.get(Job, booking.job_id)
        if job.status not in live.TERMINAL:
            raise HTTPException(409, 'An adjustment can be requested once the booking has reached a final state.')
        open_ones = db.scalars(select(IncidentRecord).where(IncidentRecord.kind == 'adjustment_request', IncidentRecord.subject_id == booking.id,
                                                            IncidentRecord.status != 'resolved')).all()
        if any(r.details.get('requester') == member.org_id for r in open_ones):
            raise HTTPException(409, 'An adjustment request for this booking is already open.')
        row = IncidentRecord(id='adj-' + sha(f'{booking.id}|{time.time()}|{member.id}')[:24], org_id=booking.producer_org_id, kind='adjustment_request',
                             subject_type='booking', subject_id=booking.id, status='open',
                             details={'reason': body.reason, 'requested_cents': body.requested_cents, 'requester': member.org_id})
        db.add(row)
        record(db, member.org_id, 'job', job.id, 'AdjustmentRequested', actor=member.id, request_id=row.id, requested_cents=body.requested_cents)
        return {'id': row.id, 'status': 'open', 'booking_id': booking.id}
