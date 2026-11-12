"""Event delivery on top of the transactional outbox (the `events` table).

Business changes and their events commit in ONE transaction (`record()` runs inside the caller's
session), so an event exists if and only if its change committed. Sequence numbers, however, are
allocated before commit: a slower transaction can commit seq 41 after seq 42 is already visible.
A reader that simply advanced its cursor to 42 would never see 41.

`horizon()` returns the highest sequence that is safe to deliver: every number up to it is either
visible or a gap older than `GAP_GRACE` seconds (a rolled-back transaction leaves a permanent gap).
Readers deliver only up to the horizon, so late commits are delivered in order, and a reconnecting
client resumes from its `Last-Event-ID`.
"""
import json
import time

from sqlalchemy import select

from .db import Event, session

GAP_GRACE = 3.0
MAX_SCAN = 2000
MAX_GAP = 5000


def horizon(db, cursor: int, gaps: dict, now: float | None = None, grace: float = GAP_GRACE) -> int:
    """Highest seq > cursor that can be delivered without risking a skipped late commit."""
    now = time.monotonic() if now is None else now
    seqs = list(db.scalars(select(Event.seq).where(Event.seq > cursor).order_by(Event.seq).limit(MAX_SCAN)))
    expected, safe = cursor + 1, cursor
    for seq in seqs:
        if expected < seq:
            missing = range(expected, seq) if seq - expected <= MAX_GAP else range(seq - MAX_GAP, seq)
            # Start every missing number's grace clock together, so a multi-number gap waits once.
            stamps = [gaps.setdefault(number, now) for number in missing]
            if any(now - stamp < grace for stamp in stamps):
                return safe  # a transaction holding one of these numbers may still commit
        safe, expected = seq, seq + 1
    for stale in [key for key in gaps if key <= safe]:
        del gaps[stale]
    return safe


def newest(db) -> int:
    return db.scalar(select(Event.seq).order_by(Event.seq.desc()).limit(1)) or 0


def entity_events(db, org, entity_type, entity_id, since, upto=None, limit=1000):
    stmt = select(Event).where(Event.org_id == org, Event.entity_type == entity_type,
                               Event.entity_id == entity_id, Event.seq > since)
    if upto is not None:
        stmt = stmt.where(Event.seq <= upto)
    return list(db.scalars(stmt.order_by(Event.seq).limit(limit)))


def entity_stream(org, entity_type, entity_id, last_event_id=0, window=22.0, pause=1.0, view=None):
    """Server-sent-event lines: replay everything after `last_event_id`, then follow new events."""
    view = view or (lambda row: {'seq': row.seq, 'kind': row.kind, 'at': row.at, 'details': row.details})
    cursor, gaps = last_event_id, {}
    with session() as db:
        guard = max(newest(db), cursor)
        replay = entity_events(db, org, entity_type, entity_id, cursor, upto=guard)
    for row in replay:
        yield f'id: {row.seq}\ndata: {json.dumps(view(row))}\n\n'
    cursor = guard
    until = time.monotonic() + window
    while time.monotonic() < until:
        with session() as db:
            safe = horizon(db, cursor, gaps)
            batch = entity_events(db, org, entity_type, entity_id, cursor, upto=safe) if safe > cursor else []
        cursor = max(cursor, safe)
        if batch:
            for row in batch:
                yield f'id: {row.seq}\ndata: {json.dumps(view(row))}\n\n'
        else:
            yield ': keepalive\n\n'
        time.sleep(pause)
