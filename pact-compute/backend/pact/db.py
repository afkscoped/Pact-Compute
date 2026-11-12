import hashlib
import secrets
import ssl
import time
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, create_engine, event, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import DATABASE, DB_TLS, STATE


def uid() -> str:
    return secrets.token_hex(12)


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = 'organizations'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))


class Member(Base):
    __tablename__ = 'members'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password: Mapped[str] = mapped_column(String(180))
    role: Mapped[str] = mapped_column(String(20))


class Login(Base):
    __tablename__ = 'sessions'
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    member_id: Mapped[str] = mapped_column(ForeignKey('members.id'), index=True)
    expires: Mapped[float] = mapped_column(Float)
    org_id: Mapped[str | None] = mapped_column(ForeignKey('organizations.id'), nullable=True)


class Membership(Base):
    # Extra workspaces beyond a member's home org/role (members.org_id / members.role).
    __tablename__ = 'memberships'
    __table_args__ = (UniqueConstraint('member_id', 'org_id'),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    member_id: Mapped[str] = mapped_column(ForeignKey('members.id'), index=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Invitation(Base):
    __tablename__ = 'invitations'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    role: Mapped[str] = mapped_column(String(20))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('members.id'))
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    expires_at: Mapped[float] = mapped_column(Float)
    accepted_by: Mapped[str | None] = mapped_column(ForeignKey('members.id'), nullable=True)
    accepted_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    revoked_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class Policy(Base):
    __tablename__ = 'policies'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey('policies.id'))
    title: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(String(64))
    rules: Mapped[list] = mapped_column(JSON)
    issues: Mapped[list] = mapped_column(JSON)
    method: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24), default='draft')
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    approved_at: Mapped[float | None] = mapped_column(Float)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('members.id'))


class Runner(Base):
    __tablename__ = 'runners'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    token_digest: Mapped[str] = mapped_column(String(64))
    device: Mapped[str] = mapped_column(String(200), default='Waiting for enrollment')
    vram_mib: Mapped[int] = mapped_column(Integer, default=0)
    ready: Mapped[bool] = mapped_column(Boolean, default=False)
    zone: Mapped[str | None] = mapped_column(String(30))
    rate_cents: Mapped[int] = mapped_column(Integer, default=250)
    last_seen: Mapped[float] = mapped_column(Float, default=0)
    dispatch_paused: Mapped[bool] = mapped_column(Boolean, default=False)


class Job(Base):
    __tablename__ = 'jobs'
    __table_args__ = (UniqueConstraint('org_id', 'request_key'), Index('ix_jobs_runner_status', 'runner_id', 'status'))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey('policies.id'))
    submitted_by: Mapped[str] = mapped_column(ForeignKey('members.id'))
    runner_id: Mapped[str | None] = mapped_column(ForeignKey('runners.id'))
    request_key: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(24))
    spec: Mapped[dict] = mapped_column(JSON)
    decision: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    start_after: Mapped[float | None] = mapped_column(Float)
    deadline_at: Mapped[float | None] = mapped_column(Float)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)


class Attempt(Base):
    __tablename__ = 'attempts'
    __table_args__ = (UniqueConstraint('job_id', 'ordinal'),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(ForeignKey('jobs.id'), index=True)
    runner_id: Mapped[str] = mapped_column(ForeignKey('runners.id'), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    fence: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    lease_until: Mapped[float] = mapped_column(Float)
    started_at: Mapped[float | None] = mapped_column(Float)
    finished_at: Mapped[float | None] = mapped_column(Float)
    result: Mapped[dict | None] = mapped_column(JSON)


class CapacityOffer(Base):
    __tablename__ = 'capacity_offers'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    runner_id: Mapped[str] = mapped_column(ForeignKey('runners.id'), index=True)
    title: Mapped[str] = mapped_column(String(120))
    starts_at: Mapped[float] = mapped_column(Float)
    ends_at: Mapped[float] = mapped_column(Float)
    rate_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default='published')
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class MarketQuote(Base):
    __tablename__ = 'market_quotes'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    offer_id: Mapped[str] = mapped_column(ForeignKey('capacity_offers.id'))
    consumer_id: Mapped[str] = mapped_column(ForeignKey('members.id'))
    offer_version: Mapped[int] = mapped_column(Integer)
    policy_id: Mapped[str] = mapped_column(ForeignKey('policies.id'))
    spec: Mapped[dict] = mapped_column(JSON)
    selection: Mapped[dict] = mapped_column(JSON)
    issued_at: Mapped[float] = mapped_column(Float)
    expires_at: Mapped[float] = mapped_column(Float)


class MarketBooking(Base):
    __tablename__ = 'market_bookings'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    quote_id: Mapped[str] = mapped_column(ForeignKey('market_quotes.id'), unique=True)
    offer_id: Mapped[str] = mapped_column(ForeignKey('capacity_offers.id'))
    consumer_org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    producer_org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey('jobs.id'), unique=True)
    accepted_at: Mapped[float] = mapped_column(Float)


class Artifact(Base):
    __tablename__ = 'artifacts'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey('jobs.id'), index=True)
    filename: Mapped[str] = mapped_column(String(140))
    kind: Mapped[str] = mapped_column(String(30))
    digest: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class ResearchRun(Base):
    __tablename__ = 'research_runs'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('members.id'))
    config: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    finished_at: Mapped[float | None] = mapped_column(Float)
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    worker: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    artifact_id: Mapped[str | None] = mapped_column(ForeignKey('artifacts.id'))


class Event(Base):
    __tablename__ = 'events'
    __table_args__ = (Index('ix_events_entity', 'org_id', 'entity_type', 'entity_id', 'seq'),)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(60))
    details: Mapped[dict] = mapped_column(JSON)
    at: Mapped[float] = mapped_column(Float, default=time.time)


class FindingReview(Base):
    __tablename__ = 'finding_reviews'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), index=True)
    member_id: Mapped[str] = mapped_column(ForeignKey('members.id'))
    entity_type: Mapped[str] = mapped_column(String(20))
    entity_id: Mapped[str] = mapped_column(String(32), index=True)
    finding_id: Mapped[str] = mapped_column(String(80))
    disposition: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(Text)
    at: Mapped[float] = mapped_column(Float, default=time.time)


sqlite = DATABASE.startswith('sqlite')
connect_args = {'timeout': 15} if sqlite else {}
if DATABASE.startswith('postgresql+pg8000:') and DB_TLS:
    connect_args['ssl_context'] = ssl.create_default_context()
engine = create_engine(DATABASE, pool_pre_ping=True, connect_args=connect_args)

if sqlite:
    @event.listens_for(engine, 'connect')
    def configure_sqlite(connection, _):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.close()


@contextmanager
def session(write: bool = False):
    with Session(engine, expire_on_commit=False) as db:
        if write and sqlite:
            db.execute(text('BEGIN IMMEDIATE'))
        yield db
        if write:
            db.commit()


def scoped(db: Session, model, org_id: str, object_id: str, lock: bool = False):
    stmt = select(model).where(model.id == object_id, model.org_id == org_id)
    return db.scalar(stmt.with_for_update() if lock else stmt)


def record(db: Session, org: str, entity: str, entity_id: str, kind: str, **details):
    db.add(Event(org_id=org, entity_type=entity, entity_id=entity_id, kind=kind, details=details))


def sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode('utf-8') if isinstance(data, str) else data).hexdigest()


def artifact_path(digest: str) -> Path:
    return STATE / 'artifacts' / digest


def save_artifact(db: Session, org: str, data: bytes, filename: str, kind: str, job_id: str | None = None):
    digest = sha(data)
    target = artifact_path(digest)
    target.parent.mkdir(exist_ok=True)
    if not target.exists():
        staging = target.with_suffix('.' + uid() + '.part')
        staging.write_bytes(data)
        staging.replace(target)
    artifact = Artifact(org_id=org, filename=filename, kind=kind, digest=digest, size=len(data), job_id=job_id)
    db.add(artifact)
    db.flush()
    return artifact
