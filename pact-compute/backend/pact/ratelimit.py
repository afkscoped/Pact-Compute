"""Database-backed limits shared by every API replica (no per-process state).

One table row = one hit that stays "live" until its expiry. A bucket is allowed while its
live rows are below the limit. The same primitive gives sliding-window rate limits, a
single-flight lock and a cooldown.
"""
import time

from sqlalchemy import delete, func, select, text

from .db import RateHit, session, sqlite


def _guard(db, bucket):
    if not sqlite:  # serialize concurrent replicas per bucket; SQLite already uses BEGIN IMMEDIATE
        db.execute(text('SELECT pg_advisory_xact_lock(hashtext(:bucket))'), {'bucket': bucket})


def hit(bucket: str, limit: int, window: float, now: float | None = None) -> int | None:
    """Record a hit if fewer than `limit` are live. Returns the row id, or None when blocked."""
    now = time.time() if now is None else now
    with session(write=True) as db:
        _guard(db, bucket)
        db.execute(delete(RateHit).where(RateHit.bucket == bucket, RateHit.until <= now))
        live = db.scalar(select(func.count()).select_from(RateHit).where(RateHit.bucket == bucket)) or 0
        if live >= limit:
            return None
        row = RateHit(bucket=bucket, until=now + window)
        db.add(row)
        db.flush()
        return row.id


def blocked(bucket: str, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    with session() as db:
        return bool(db.scalar(select(func.count()).select_from(RateHit).where(RateHit.bucket == bucket, RateHit.until > now)))


def mark(bucket: str, seconds: float, now: float | None = None) -> None:
    """Unconditionally open a cooldown for `seconds`."""
    now = time.time() if now is None else now
    with session(write=True) as db:
        db.add(RateHit(bucket=bucket, until=now + seconds))


def release(row_id: int | None) -> None:
    if row_id is None:
        return
    with session(write=True) as db:
        db.execute(delete(RateHit).where(RateHit.id == row_id))


def reset(prefix: str = '') -> None:
    """Forget every bucket starting with `prefix` (tests and operator recovery)."""
    with session(write=True) as db:
        db.execute(delete(RateHit).where(RateHit.bucket.like(prefix + '%')))
