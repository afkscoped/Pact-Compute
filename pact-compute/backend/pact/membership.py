"""Self-service membership: invitations, extra workspaces and the workspace switcher."""
import secrets
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .access import User, require
from .db import Invitation, Login, Member, Membership, Organization, record, session, sha
from .security import COOKIE, authenticated, password_digest

router = APIRouter(prefix='/api/v1', tags=['membership'])
INVITE_SECONDS = 7 * 24 * 3600


class InviteInput(BaseModel):
    role: Literal['reviewer', 'consumer', 'producer']


class AcceptInput(BaseModel):
    code: str = Field(min_length=20, max_length=100)
    username: str | None = Field(default=None, pattern=r'^[a-z][a-z0-9._-]{1,63}$')
    password: str | None = Field(default=None, min_length=12, max_length=200)


class SwitchInput(BaseModel):
    org_id: str = Field(min_length=1, max_length=32)


def invitation_view(row, now):
    status = ('accepted' if row.accepted_at else 'revoked' if row.revoked_at
              else 'expired' if row.expires_at <= now else 'pending')
    return {'id': row.id, 'role': row.role, 'status': status, 'created_at': row.created_at, 'expires_at': row.expires_at}


@router.post('/invitations', status_code=201)
def invite(body: InviteInput, member: User):
    require(member, 'admin', 'producer', 'consumer')
    # Participants may bring in reviewers or colleagues in their own participant role; privileged roles stay with platform admins.
    if body.role != 'reviewer' and body.role != member.role:
        raise HTTPException(403, 'You can invite a reviewer or a colleague with your own role.')
    code = secrets.token_urlsafe(32)
    with session(write=True) as db:
        row = Invitation(org_id=member.org_id, role=body.role, token_digest=sha(code), created_by=member.id,
                         expires_at=time.time() + INVITE_SECONDS)
        db.add(row)
        db.flush()
        record(db, member.org_id, 'invitation', row.id, 'InvitationCreated', actor=member.id, role=body.role)
        return {**invitation_view(row, time.time()), 'code': code}


@router.get('/invitations')
def invitations(member: User):
    require(member, 'admin', 'producer', 'consumer')
    now = time.time()
    with session() as db:
        rows = db.scalars(select(Invitation).where(Invitation.org_id == member.org_id)
                          .order_by(Invitation.created_at.desc()).limit(100))
        return [invitation_view(row, now) for row in rows]


@router.delete('/invitations/{invitation_id}')
def revoke(invitation_id: str, member: User):
    require(member, 'admin', 'producer', 'consumer')
    with session(write=True) as db:
        row = db.get(Invitation, invitation_id)
        if not row or row.org_id != member.org_id:
            raise HTTPException(404, 'Record not found.')
        if row.accepted_at:
            raise HTTPException(409, 'This invitation was already accepted.')
        if not row.revoked_at:
            row.revoked_at = time.time()
            record(db, member.org_id, 'invitation', row.id, 'InvitationRevoked', actor=member.id)
        return invitation_view(row, time.time())


@router.post('/invitations/accept', status_code=201)
def accept(body: AcceptInput, request: Request, response: Response,
           raw: Annotated[str | None, Cookie(alias=COOKIE)] = None):
    from . import api
    api.limit_auth_attempts(request, api.registration_attempts, 6, 'Too many attempts. Try again in a minute.')
    now = time.time()
    digest = sha(body.code)
    with session() as db:
        existing = authenticated(db, raw) if raw and not body.username else None
        existing_id = existing.id if existing else None
    if not existing_id and not (body.username and body.password):
        raise HTTPException(422, 'Enter a username and password to create your account, or sign in first.')
    password = password_digest(body.password) if body.password and not existing_id else None
    token = None
    try:
        with session(write=True) as db:
            invitation = db.scalar(select(Invitation).where(Invitation.token_digest == digest))
            if not invitation or invitation.revoked_at or invitation.accepted_at or invitation.expires_at <= now:
                raise HTTPException(404, 'This invitation code is not valid. Ask for a new one.')
            claimed = db.execute(update(Invitation).where(
                Invitation.id == invitation.id, Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None)).values(accepted_at=now)).rowcount
            if claimed != 1:
                raise HTTPException(404, 'This invitation code is not valid. Ask for a new one.')
            if existing_id:
                person = db.get(Member, existing_id)
                if person.org_id == invitation.org_id or db.scalar(select(Membership.id).where(
                        Membership.member_id == person.id, Membership.org_id == invitation.org_id)):
                    raise HTTPException(409, 'You already belong to this workspace.')
                db.add(Membership(member_id=person.id, org_id=invitation.org_id, role=invitation.role))
                db.get(Login, sha(raw)).org_id = invitation.org_id
            else:
                person = Member(org_id=invitation.org_id, username=body.username, password=password, role=invitation.role)
                db.add(person)
                db.flush()
                token = api.create_session(db, person)
            invitation.accepted_by = person.id
            record(db, invitation.org_id, 'invitation', invitation.id, 'InvitationAccepted',
                   actor=person.id, role=invitation.role)
            result = {'id': person.id, 'username': person.username, 'role': invitation.role,
                      'organization': db.get(Organization, invitation.org_id).name}
    except IntegrityError as error:
        with session() as db:
            if db.scalar(select(Member.id).where(Member.username == body.username)):
                raise HTTPException(409, 'This username is already taken.') from error
        raise
    if token:
        api.set_session_cookie(response, token)
    return result


@router.get('/memberships')
def memberships(member: User):
    with session() as db:
        home = db.get(Member, member.id)
        rows = [(home.org_id, home.role, True)] + [(m.org_id, m.role, False) for m in db.scalars(
            select(Membership).where(Membership.member_id == member.id).order_by(Membership.created_at))]
        return [{'org_id': org, 'organization': db.get(Organization, org).name, 'role': role, 'home': is_home,
                 'active': org == member.org_id} for org, role, is_home in rows]


@router.post('/session/workspace')
def switch(body: SwitchInput, member: User, raw: Annotated[str | None, Cookie(alias=COOKIE)] = None):
    with session(write=True) as db:
        home = db.get(Member, member.id)
        if body.org_id != home.org_id and not db.scalar(select(Membership.id).where(
                Membership.member_id == member.id, Membership.org_id == body.org_id)):
            raise HTTPException(403, 'You do not belong to that workspace.')
        db.get(Login, sha(raw)).org_id = None if body.org_id == home.org_id else body.org_id
    return {'status': 'switched', 'org_id': body.org_id}
