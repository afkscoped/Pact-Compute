from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import select

from .db import Login, Membership, scoped, session, sha
from .security import COOKIE, authenticated


@dataclass(frozen=True)
class Principal:
    """The signed-in person acting in one workspace (their active organization and role)."""
    id: str
    username: str
    org_id: str
    role: str
    home_org_id: str


def current_user(raw: Annotated[str | None, Cookie(alias=COOKIE)] = None):
    with session() as db:
        member = authenticated(db, raw)
        if member:
            org_id, role = member.org_id, member.role
            login = db.get(Login, sha(raw))
            if login and login.org_id and login.org_id != member.org_id:
                # Re-validated on every request so a removed membership stops working at once.
                extra = db.scalar(select(Membership).where(Membership.member_id == member.id, Membership.org_id == login.org_id))
                if extra:
                    org_id, role = extra.org_id, extra.role
            return Principal(member.id, member.username, org_id, role, member.org_id)
    raise HTTPException(401, 'Sign in to continue.')


User = Annotated[Principal, Depends(current_user)]


def require(member, *roles):
    if member.role not in roles:
        raise HTTPException(403, 'This action requires a different role.')


def entity(db, model, member, object_id):
    row = scoped(db, model, member.org_id, object_id)
    if not row:
        raise HTTPException(404, 'Record not found.')
    return row
