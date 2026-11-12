"""Keyset (cursor) pagination.

List endpoints keep returning a JSON array (existing clients keep working) and report the next page in
the `X-Next-Cursor` response header; it is absent on the last page. Pass it back as `?cursor=` with an
optional `?limit=` (1-100). Order is a stable (primary, id) key, so pages never skip or repeat rows even
while new rows arrive, and cost does not grow with page depth (unlike OFFSET).
"""
import base64
import json
from typing import Annotated

from fastapi import HTTPException, Query, Response
from sqlalchemy import and_, or_

Limit = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[str | None, Query(max_length=300)]


def encode(values: list) -> str:
    return base64.urlsafe_b64encode(json.dumps(values, separators=(',', ':')).encode()).decode().rstrip('=')


def decode(cursor: str) -> list:
    try:
        values = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
        if isinstance(values, list) and len(values) == 2 and isinstance(values[1], str) and isinstance(values[0], (int, float, str)):
            return values
    except (ValueError, UnicodeDecodeError):
        pass
    raise HTTPException(422, 'The page cursor is not valid. Reload the list.')


def page(db, stmt, primary, secondary, descending: bool, limit: int, cursor: str | None):
    """Rows of `stmt` ordered by (primary, secondary) after `cursor`; returns (rows, next_cursor or None)."""
    if cursor:
        first, second = decode(cursor)
        after = (lambda column, value: column < value) if descending else (lambda column, value: column > value)
        stmt = stmt.where(or_(after(primary, first), and_(primary == first, after(secondary, second))))
    order = (primary.desc(), secondary.desc()) if descending else (primary, secondary)
    rows = list(db.scalars(stmt.order_by(*order).limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    return rows, (encode([getattr(rows[-1], primary.key), getattr(rows[-1], secondary.key)]) if more else None)


def set_next(response: Response, next_cursor: str | None) -> None:
    if next_cursor:
        response.headers['X-Next-Cursor'] = next_cursor
