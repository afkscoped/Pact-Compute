import json
import time
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from . import live
from .db import Attempt, CapacityOffer, Event, Job, MarketBooking, MarketQuote, Organization, Runner, record, scoped, sha
from .protocol import observe

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


class ConfirmInput(BaseModel):
    images: list[live.ImageInput] = Field(default_factory=list, max_length=16)


def offer_view(db, offer, member, now):
    runner = db.get(Runner, offer.runner_id)
    org = db.get(Organization, offer.org_id)
    available_at = max(now, offer.starts_at)
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


def offers(db, member):
    now = time.time()
    stmt = select(CapacityOffer).where(or_(CapacityOffer.org_id == member.org_id,
                                         (CapacityOffer.status == 'published') & (CapacityOffer.ends_at > now)))
    return [offer_view(db, item, member, now) for item in db.scalars(
        stmt.order_by(CapacityOffer.starts_at, CapacityOffer.id).limit(100))]


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
    preview = live.placement(db, member.org_id, spec, policy, now, offer=offer)
    selected = preview['selected']
    if not selected:
        return {'id': None, 'offer_id': offer.id, 'policy_id': policy.id, 'candidates': preview['candidates']}
    # Issuing a quote never holds capacity. Confirmation serializes both organizations.
    quote = MarketQuote(org_id=member.org_id, offer_id=offer.id, consumer_id=member.id,
                        offer_version=offer.version, policy_id=policy.id, spec=spec.model_dump(exclude={'images'}),
                        selection=selected, issued_at=now, expires_at=min(now + QUOTE_TTL, offer.ends_at))
    db.add(quote)
    db.flush()
    record(db, member.org_id, 'market_quote', quote.id, 'QuoteIssued')
    return {'id': quote.id, 'offer_id': offer.id, 'offer_version': quote.offer_version, 'policy_id': quote.policy_id,
            'issued_at': quote.issued_at, 'expires_at': quote.expires_at, 'selected': selected,
            'candidates': preview['candidates']}


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
    preview = live.placement(db, member.org_id, spec, policy, now, offer=offer)
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


def trace(db, job, quote=None):
    events = []
    if quote:
        events.append({'kind': 'QuoteIssued', 'at': quote.issued_at, 'seq': f'quote:{quote.id}',
                       'details': {'quote_id': quote.id, 'expires_at': quote.expires_at, 'policy_id': quote.policy_id,
                                   'rate_cents': quote.selection['rate_cents'], 'offer_version': quote.offer_version,
                                   'envelope_cents': quote.selection['envelope_cents']}})
    stmt = select(Event).where(Event.entity_type == 'job', Event.entity_id == job.id, Event.org_id == job.org_id).order_by(Event.seq)
    events.extend({'kind': item.kind, 'at': item.at, 'seq': item.seq, 'details': item.details} for item in db.scalars(stmt))
    return observe(events, market=quote is not None)


def booking_view(db, booking, member, detailed=False):
    job = db.get(Job, booking.job_id)
    quote = db.get(MarketQuote, booking.quote_id)
    offer = db.get(CapacityOffer, booking.offer_id)
    attempt = db.scalar(select(Attempt).where(Attempt.job_id == job.id).order_by(Attempt.ordinal.desc()).limit(1))
    result = (attempt.result or {}) if attempt else {}
    consumer = booking.consumer_org_id == member.org_id
    public_title = job.title if consumer else f'Image embedding batch ({job.spec["sample_count"]} images)'
    return {'id': booking.id, 'quote_id': quote.id, 'offer': offer.title, 'title': public_title,
            'job_id': job.id if consumer else None, 'party': 'consumer' if consumer else 'producer',
            'status': job.status, 'accepted_at': booking.accepted_at, 'start_at': job.start_after, 'deadline_at': job.deadline_at,
            'rate_cents': quote.selection['rate_cents'], 'maximum_charge_cents': quote.selection['envelope_cents'],
            'usage_cents': result.get('charged_cents'), 'duration_s': result.get('duration_s'),
            'energy_kwh': result.get('gpu_energy_kwh'), 'artifact_sha256': result.get('sha256'),
            **({'protocol': trace(db, job, quote)} if detailed else {})}


def bookings(db, member):
    conditions = [MarketBooking.consumer_org_id == member.org_id]
    if member.role in PRODUCERS:
        conditions.append(MarketBooking.producer_org_id == member.org_id)
    rows = db.scalars(select(MarketBooking).where(or_(*conditions)).order_by(MarketBooking.accepted_at.desc()).limit(100))
    return [booking_view(db, item, member) for item in rows]
