from typing import Annotated

from fastapi import Cookie, Depends, HTTPException

from .db import Member, scoped, session
from .security import COOKIE, authenticated


def current_user(raw: Annotated[str | None, Cookie(alias=COOKIE)] = None):
    with session() as db:
        member = authenticated(db, raw)
        if member:
            return member
    raise HTTPException(401, 'Sign in to continue.')


User = Annotated[Member, Depends(current_user)]


def require(member, *roles):
    if member.role not in roles:
        raise HTTPException(403, 'This action requires a different role.')


def entity(db, model, member, object_id):
    row = scoped(db, model, member.org_id, object_id)
    if not row:
        raise HTTPException(404, 'Record not found.')
    return row
