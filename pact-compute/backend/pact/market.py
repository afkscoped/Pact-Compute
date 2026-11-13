import json
import time
from collections import defaultdict
from types import SimpleNamespace
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from . import live, market_evidence, pagination
from .db import Attempt, CapacityOffer, Event, Job, MarketBooking, MarketQuote, Organization, Policy, Runner, record, scoped, sha
from .protocol import observe, presence_verdict

BUYERS = ('admin', 'consumer', 'submitter')
PRODUCERS = ('admin', 'operator', 'producer')
PARTICIPANTS = tuple(dict.fromkeys((*BUYERS, *PRODUCERS, 'reviewer', 'researcher')))
QUOTE_TTL = 90
START_TOLERANCE = 8


class OfferInput(BaseModel):
    runner_id: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=2, max_length=120)
    starts_at: float = Field(allow_inf_nan=False)
    ends_at: float = Field(allow_inf_nan=False)
    rate_cents: int = Field(ge=0, le=100_000)


class OfferChange(BaseModel):
    status: Literal['published', 'paused']


class QuoteInput(BaseModel):
    offer_id: str = Field(min_length=1, max_length=32)
    policy_id: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=2, max_length=120)
    sample_count: int = Field(default=4, ge=1, le=16)
    flexible: bool = False
    template: live.WorkloadTemplate = live.TEMPLATE


class ConfirmInput(BaseModel):
    images: list[live.ImageInput] = Field(default_factory=list, max_length=16)


def offer_view(db, offer, member, now, claims=None):
    runner = db.get(Runner, offer.runner_id)
    org = db.get(Organization, offer.org_id)
    available_at = max(now, offer.starts_at)
    if claims is None:
        claims = db.scalars(select(Job).where(Job.runner_id == runner.id, Job.status.in_(live.ACTIVE)))
    uncertain = False
    for claim in claims:
        available_at = max(available_at, claim.decision.get('reserved_until', now))
        uncertain = uncertain or claim.status == 'execution_unknown'
    available = (offer.status == 'published' and live.runner_online(runner, now)
                 and not uncertain and available_at < offer.ends_at)
    return {'id': offer.id, 'title': offer.title, 'device': runner.device, 'vram_mib': runner.vram_mib,
            'producer': org.name, 'zone': runner.zone, 'starts_at': offer.starts_at, 'ends_at': offer.ends_at,
            'rate_cents': offer.rate_cents, 'status': offer.status, 'version': offer.version,
            'available': available, 'available_at': available_at if available else None,
            'fresh_at': runner.last_seen, 'own': offer.org_id == member.org_id}


def offers_page(db, member, limit=100, cursor=None):
    now = time.time()
    stmt = select(CapacityOffer).where(or_(CapacityOffer.org_id == member.org_id,
                                         (CapacityOffer.status == 'published') & (CapacityOffer.ends_at > now)))
    rows, more = pagination.page(db, stmt, CapacityOffer.starts_at, CapacityOffer.id, False, limit, cursor)
    # Batch the per-row lookups: prime the identity map with one query per table, group active claims once.
    runner_ids = {row.runner_id for row in rows}
    keep = []  # the identity map holds weak references: keep primed rows alive until rendered
    if rows:
        keep.append(list(db.scalars(select(Runner).where(Runner.id.in_(runner_ids)))))
        keep.append(list(db.scalars(select(Organization).where(Organization.id.in_({row.org_id for row in rows})))))
    claims = defaultdict(list)
    if runner_ids:
        for claim in db.scalars(select(Job).where(Job.runner_id.in_(runner_ids), Job.status.in_(live.ACTIVE))):
            claims[claim.runner_id].append(claim)
    return [offer_view(db, item, member, now, claims[item.runner_id]) for item in rows], more


def offers(db, member):
    return offers_page(db, member)[0]


def publish(db, member, data):
    now = time.time()
    live.lock_parties(db, member.org_id)
    runner = scoped(db, Runner, member.org_id, data.runner_id)
    if not runner:
        raise live.LiveError('Runner not found in this producer organization.', 404)
    if not now + 60 <= data.ends_at <= now + 30 * 86400 or data.starts_at >= data.ends_at or data.starts_at < now - 86400:
        raise live.LiveError('Choose a valid availability window within the next 30 days.', 422)
    offer = CapacityOffer(org_id=member.org_id, **data.model_dump())
    db.add(offer)
    db.flush()
    record(db, member.org_id, 'market_offer', offer.id, 'OfferPublished', actor=member.id)
    return offer_view(db, offer, member, now)


def change_offer(db, member, offer_id, status):
    live.lock_parties(db, member.org_id)
    offer = scoped(db, CapacityOffer, member.org_id, offer_id)
    if not offer:
        raise live.LiveError('Offer not found.', 404)
    if offer.status != status:
        if status == 'published' and offer.ends_at <= time.time():
            raise live.LiveError('The availability window has ended. Publish a new offer.', 409)
        offer.status = status
        offer.version += 1
        record(db, member.org_id, 'market_offer', offer.id,
               'OfferPublished' if status == 'published' else 'OfferPaused', actor=member.id)
    return offer_view(db, offer, member, time.time())


def create_quote(db, member, data):
    now = time.time()
    offer = db.get(CapacityOffer, data.offer_id)
    if not offer or offer.status != 'published' or offer.ends_at <= now:
        raise live.LiveError('The offer is unavailable. Refresh the listing.', 409)
    policy = live.active_policy(db, member.org_id, data.policy_id)
    spec = live.JobInput(**data.model_dump(exclude={'offer_id'}))
    runtime = market_evidence.runtime_plan(db, member.org_id, offer.runner_id, spec, live.predicted_seconds(spec.sample_count))
    preview = live.placement(db, member.org_id, spec, policy, now, offer=offer, runtime=runtime['runtime_s'])
    selected = preview['selected']
    candidate = selected or min(preview['candidates'], key=lambda row: len(row['reasons']), default={'reasons': []})
    evidence = {'runtime': runtime, 'clauses': market_evidence.clause_evidence(policy, candidate, spec.flexible, now),
                'policy_title': policy.title, 'policy_sha256': policy.source_hash,
                'prices': market_evidence.price_history(db, offer), 'replay': None,
                'live_runtime_carbon_g': market_evidence.energy_plan(candidate, runtime['runtime_s']) if selected else None}
    evidence['price_cases'] = quote_price_cases(db, member, spec, policy, offer, now, runtime['runtime_s'], preview)
    signal = market_evidence.historical_signal(now)
    if signal:
        modeled_power = market_evidence.REPLAY_POWER_W
        replay = live.placement(db, member.org_id, spec, policy, now, offer=offer, runtime=runtime['runtime_s'],
                                carbon_replay=(signal['forecast'], modeled_power))
        evidence['replay'] = market_evidence.replay_comparison(replay, signal, now, modeled_power)
    if not selected:
        return {'id': None, 'offer_id': offer.id, 'policy_id': policy.id, 'candidates': preview['candidates'], 'evidence': evidence}
    # Issuing a quote never holds capacity. Confirmation serializes both organizations.
    excluded = {'images', 'template'} if spec.template == live.TEMPLATE else {'images'}
    quote = MarketQuote(org_id=member.org_id, offer_id=offer.id, consumer_id=member.id,
                        offer_version=offer.version, policy_id=policy.id, spec=spec.model_dump(exclude=excluded),
                        selection={**selected, 'runtime_plan': runtime, 'grid_replay': evidence['replay']},
                        issued_at=now, expires_at=min(now + QUOTE_TTL, offer.ends_at))
    db.add(quote)
    db.flush()
    record(db, member.org_id, 'market_quote', quote.id, 'QuoteIssued')
    return {'id': quote.id, 'offer_id': offer.id, 'offer_version': quote.offer_version, 'policy_id': quote.policy_id,
            'issued_at': quote.issued_at, 'expires_at': quote.expires_at, 'selected': selected,
            'candidates': preview['candidates'], 'evidence': evidence}


def quote_price_cases(db, member, spec, policy, offer, now, runtime, posted):
    cases = []
    for name, rate in (('Posted rate', offer.rate_cents), ('20% lower', round(offer.rate_cents * .8)),
                       ('20% higher', min(100_000, round(offer.rate_cents * 1.2)))):
        alternate = SimpleNamespace(runner_id=offer.runner_id, starts_at=offer.starts_at,
                                    ends_at=offer.ends_at, status=offer.status, rate_cents=rate)
        decision = posted if rate == offer.rate_cents else live.placement(
            db, member.org_id, spec, policy, now, offer=alternate, runtime=runtime)
        selected = decision['selected']
        reasons = list(dict.fromkeys(reason['message'] for row in decision['candidates'] for reason in row['reasons']))
        cases.append({'name': name, 'rate_cents': rate, 'eligible': selected is not None,
                      'estimated_charge_cents': selected['quote_cents'] if selected else None,
                      'maximum_charge_cents': selected['envelope_cents'] if selected else None,
                      'reason': reasons[0] if reasons and not selected else None})
    return cases


def booking_for(db, member, booking_id):
    booking = db.get(MarketBooking, booking_id)
    if not booking or not can_view(booking, member):
        raise live.LiveError('Booking not found.', 404)
    return booking


def can_view(booking, member):
    return booking.consumer_org_id == member.org_id or (
        booking.producer_org_id == member.org_id and member.role in PRODUCERS)


def confirm(db, member, quote_id, data):
    quote = scoped(db, MarketQuote, member.org_id, quote_id)
    if not quote or quote.consumer_id != member.id:
        raise live.LiveError('Quote not found.', 404)
    if data.images and len(data.images) != quote.spec['sample_count']:
        raise live.LiveError('The image count must match the quoted workload.', 422)
    spec = live.JobInput(**quote.spec, images=data.images)
    payload = live.prepared_images(spec)
    fingerprint = sha(json.dumps(quote.spec, sort_keys=True) + sha(payload))
    offer = db.get(CapacityOffer, quote.offer_id)
    live.lock_parties(db, member.org_id, offer.org_id)
    db.refresh(offer)
    booked = db.scalar(select(MarketBooking).where(MarketBooking.quote_id == quote.id))
    if booked:
        if db.get(Job, booked.job_id).spec['request_hash'] != fingerprint:
            raise live.LiveError('This quote already has a booking with different input images.', 409)
        return booking_view(db, booked, member)
    now = time.time()
    if now >= quote.expires_at or offer.version != quote.offer_version or offer.status != 'published':
        raise live.LiveError('The quote expired or the offer changed. Get a new quote.', 409)
    policy = live.active_policy(db, member.org_id, quote.policy_id)
    live.expire_leases(db, offer.org_id, now)
    preview = live.placement(db, member.org_id, spec, policy, now, offer=offer, runtime=quote.selection['runtime_s'])
    selected = preview['selected']
    locked = quote.selection
    if (not selected or selected['start'] > locked['start'] + START_TOLERANCE + max(0, now - quote.issued_at)
            or selected['rate_cents'] != locked['rate_cents'] or selected['envelope_cents'] > locked['envelope_cents']):
        raise live.LiveError('The quoted slot or terms changed. Refresh the quote to see available alternatives.', 409)
    # Match the consumer's accepted maximum while permitting a shorter final reservation.
    accepted = {'quote_id': quote.id, 'policy_id': policy.id, 'rate_cents': locked['rate_cents'],
                'offer_version': quote.offer_version, 'envelope_cents': locked['envelope_cents']}
    job = live.persist_job(db, member, spec, f'market-{quote.id}', payload, fingerprint, now, preview, accepted)
    booking = MarketBooking(quote_id=quote.id, offer_id=offer.id, consumer_org_id=member.org_id,
                            producer_org_id=offer.org_id, job_id=job.id, accepted_at=now)
    db.add(booking)
    db.flush()
    return booking_view(db, booking, member)


def trace_events(db, job, quote=None):
    events = []
    if quote:
        events.append({'kind': 'QuoteIssued', 'at': quote.issued_at, 'seq': f'quote:{quote.id}',
                       'details': {'quote_id': quote.id, 'expires_at': quote.expires_at, 'policy_id': quote.policy_id,
                                   'rate_cents': quote.selection['rate_cents'], 'offer_version': quote.offer_version,
                                   'envelope_cents': quote.selection['envelope_cents']}})
    stmt = select(Event).where(Event.entity_type == 'job', Event.entity_id == job.id, Event.org_id == job.org_id).order_by(Event.seq)
    events.extend({'kind': item.kind, 'at': item.at, 'seq': item.seq, 'details': item.details} for item in db.scalars(stmt))
    return events


def trace(db, job, quote=None):
    return observe(trace_events(db, job, quote), market=quote is not None)


def inspect_booking(db, job, quote):
    events = trace_events(db, job, quote)
    protocol = observe(events, market=True)
    # The alternative trace is only evaluated in memory. The persisted booking is the control.
    altered = [{**event, 'details': {**event['details'], 'rate_cents': quote.selection['rate_cents'] + 1}}
               if event['kind'] == 'MarketQuoteAccepted' else event for event in events]
    check = observe(altered, market=True)
    return {'protocol': protocol, 'protocol_comparison': {'observed': presence_verdict(events),
            'changed_rate': presence_verdict(altered), 'changed_rate_monitor': check}}


def booking_view(db, booking, member, detailed=False, attempt=False):
    job = db.get(Job, booking.job_id)
    quote = db.get(MarketQuote, booking.quote_id)
    offer = db.get(CapacityOffer, booking.offer_id)
    if attempt is False:  # not prefetched
        attempt = db.scalar(select(Attempt).where(Attempt.job_id == job.id).order_by(Attempt.ordinal.desc()).limit(1))
    result = (attempt.result or {}) if attempt else {}
    consumer = booking.consumer_org_id == member.org_id
    public_title = job.title if consumer else live.workload_label(job)
    return {'id': booking.id, 'quote_id': quote.id, 'offer': offer.title, 'title': public_title,
            'job_id': job.id if consumer else None, 'party': 'consumer' if consumer else 'producer',
            'status': job.status, 'accepted_at': booking.accepted_at, 'start_at': job.start_after, 'deadline_at': job.deadline_at,
            'rate_cents': quote.selection['rate_cents'], 'maximum_charge_cents': quote.selection['envelope_cents'],
            'usage_cents': result.get('charged_cents'), 'duration_s': result.get('duration_s'),
            'energy_kwh': result.get('gpu_energy_kwh'), 'artifact_sha256': result.get('sha256'),
            **(inspect_booking(db, job, quote) if detailed else {}),
            **({'runtime_plan': quote.selection.get('runtime_plan'),
                'grid_replay': quote.selection.get('grid_replay'),
                'policy_id': job.policy_id, 'policy_title': db.get(Policy, job.policy_id).title,
                'estimated_carbon_g': job.decision.get('dispatch_estimated_carbon_g', job.decision.get('estimated_carbon_g'))}
               if detailed and consumer else {})}


def bookings_page(db, member, limit=100, cursor=None):
    conditions = [MarketBooking.consumer_org_id == member.org_id]
    if member.role in PRODUCERS:
        conditions.append(MarketBooking.producer_org_id == member.org_id)
    rows, more = pagination.page(db, select(MarketBooking).where(or_(*conditions)), MarketBooking.accepted_at,
                                 MarketBooking.id, True, limit, cursor)
    if not rows:
        return [], more
    # Prime the identity map (one query per table) and fetch every latest attempt in one query.
    job_ids = [row.job_id for row in rows]
    keep = [list(db.scalars(select(Job).where(Job.id.in_(job_ids)))),  # weak identity map: hold until rendered
            list(db.scalars(select(MarketQuote).where(MarketQuote.id.in_([row.quote_id for row in rows])))),
            list(db.scalars(select(CapacityOffer).where(CapacityOffer.id.in_([row.offer_id for row in rows]))))]
    latest = {}
    for attempt in db.scalars(select(Attempt).where(Attempt.job_id.in_(job_ids)).order_by(Attempt.job_id, Attempt.ordinal)):
        latest[attempt.job_id] = attempt  # ascending ordinal: the last one wins
    return [booking_view(db, item, member, attempt=latest.get(item.job_id)) for item in rows], more


def bookings(db, member):
    return bookings_page(db, member)[0]
