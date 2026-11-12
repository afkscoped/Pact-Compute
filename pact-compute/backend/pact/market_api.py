import asyncio
import json
import time
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, or_, select

from . import market, outbox, pagination
from .resilience import retry_db
from .access import User, require
from .db import Event, MarketBooking, session
from .security import sign

router = APIRouter(prefix='/api/v1/market', tags=['exchange'])


@router.get('/offers')
def offer_list(member: User, response: Response, limit: pagination.Limit = 100, cursor: pagination.Cursor = None):
    require(member, *market.PARTICIPANTS)
    with session() as db:
        rows, more = market.offers_page(db, member, limit, cursor)
        pagination.set_next(response, more)
        return rows


@router.post('/offers', status_code=201)
@retry_db
def publish(data: market.OfferInput, member: User):
    require(member, *market.PRODUCERS)
    with session(write=True) as db:
        return market.publish(db, member, data)


@router.patch('/offers/{offer_id}')
def offer_status(offer_id: str, data: market.OfferChange, member: User):
    require(member, *market.PRODUCERS)
    with session(write=True) as db:
        return market.change_offer(db, member, offer_id, data.status)


@router.post('/quotes')
@retry_db
def quote(data: market.QuoteInput, member: User):
    require(member, *market.BUYERS)
    with session(write=True) as db:
        return market.create_quote(db, member, data)


@router.post('/quotes/{quote_id}/confirm', status_code=201)
@retry_db
def confirm(quote_id: str, data: market.ConfirmInput, member: User):
    require(member, *market.BUYERS)
    with session(write=True) as db:
        return market.confirm(db, member, quote_id, data)


@router.get('/bookings')
def booking_list(member: User, response: Response, limit: pagination.Limit = 100, cursor: pagination.Cursor = None):
    require(member, *market.PARTICIPANTS)
    with session() as db:
        rows, more = market.bookings_page(db, member, limit, cursor)
        pagination.set_next(response, more)
        return rows


@router.get('/bookings/{booking_id}')
def booking_details(booking_id: str, member: User):
    with session() as db:
        return market.booking_view(db, market.booking_for(db, member, booking_id), member, detailed=True)


@router.get('/bookings/{booking_id}/receipt')
def receipt(booking_id: str, member: User):
    with session() as db:
        view = market.booking_view(db, market.booking_for(db, member, booking_id), member, detailed=True)
    shared = {key: view[key] for key in ('id', 'quote_id', 'offer', 'status', 'accepted_at', 'start_at',
              'deadline_at', 'rate_cents', 'maximum_charge_cents', 'usage_cents', 'duration_s',
              'energy_kwh', 'artifact_sha256', 'protocol')}
    manifest = {'schema': 'pact-market-receipt-1', 'booking': shared, 'charge_unit': 'internal compute credits',
                'settlement': 'usage_recorded' if view['usage_cents'] is not None else 'pending_usage'}
    return JSONResponse({'manifest': manifest, 'hmac_sha256': sign(manifest)},
                        headers={'Content-Disposition': f'attachment; filename="booking-{booking_id}.json"'})


@router.get('/events')
def events(request: Request, member: User, last_event_id: Annotated[str | None, Header()] = None):
    require(member, *market.PARTICIPANTS)
    with session() as db:
        newest = db.scalar(select(func.max(Event.seq))) or 0
    start = min(int(last_event_id), newest) if last_event_id and last_event_id.isdecimal() and len(last_event_id) < 18 else newest
    owned = [MarketBooking.consumer_org_id == member.org_id]
    if member.role in market.PRODUCERS:
        owned.append(MarketBooking.producer_org_id == member.org_id)
    visible_jobs = select(MarketBooking.job_id).where(or_(*owned))

    def notices_since(cursor, gaps):
        with session() as db:
            safe = outbox.horizon(db, cursor, gaps)
            if safe <= cursor:
                return cursor, []
            stmt = select(Event.seq, Event.kind).where(
                Event.seq > cursor, Event.seq <= safe,
                or_(Event.entity_type.in_(['market_offer', 'market_capacity']),
                    (Event.entity_type == 'job') & Event.entity_id.in_(visible_jobs)),
            ).order_by(Event.seq).limit(100)
            rows = db.execute(stmt).all()
            return (rows[-1][0] if len(rows) == 100 else safe), rows

    async def stream():
        cursor, gaps = start, {}
        yield 'event: snapshot\ndata: {}\n\n'
        stop = time.monotonic() + 24
        while time.monotonic() < stop and not await request.is_disconnected():
            cursor, notices = await run_in_threadpool(notices_since, cursor, gaps)
            for seq, kind in notices:
                # The stream only invalidates projections. Scoped endpoints return the authorized payload.
                yield f'id: {seq}\nevent: update\ndata: {json.dumps({"kind": kind})}\n\n'
            if not notices:
                yield ': keepalive\n\n'
                await asyncio.sleep(0.9)

    return StreamingResponse(stream(), media_type='text/event-stream', headers={'X-Accel-Buffering': 'no'})
