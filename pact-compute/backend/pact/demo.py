import json
import secrets
import time
from urllib.parse import urlsplit

from sqlalchemy import select

from .config import STATE, URL
from .datasets import write_atomic
from .db import Member, Organization, Policy, record, session, sha
from .policy import EXAMPLE, compile_local
from .security import ORG_ID, password_digest

ACCOUNTS = {
    'demo-producer': (ORG_ID, 'producer'),
    'demo-consumer': ('demo-vision', 'consumer'),
    'demo-consumer-2': ('demo-research', 'consumer'),
    'demo-reviewer': ('demo-vision', 'reviewer'),
    'demo-reviewer-2': ('demo-research', 'reviewer'),
}


def local_demo_origin(url):
    """Permit isolated development ports while rejecting remote/lookalike origins."""
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost'}
                and parsed.port is not None and not parsed.username and not parsed.password
                and parsed.path in {'', '/'} and not parsed.query and not parsed.fragment)
    except ValueError:
        return False


def provision_demo():
    if not local_demo_origin(URL):
        raise RuntimeError('Demo users are for a local installation. Provision named accounts for deployment.')
    path = STATE / 'market-credentials.json'
    if not path.exists():
        write_atomic(path, json.dumps({name: secrets.token_urlsafe(18) for name in ACCOUNTS}, indent=2).encode())
    passwords = json.loads(path.read_bytes())
    with session(write=True) as db:
        for slug, title in [('demo-vision', 'Vision Lab'), ('demo-research', 'Research Studio')]:
            if not db.get(Organization, slug):
                db.add(Organization(id=slug, name=title))
        db.flush()
        members = {}
        for name, (org, role) in ACCOUNTS.items():
            member = db.scalar(select(Member).where(Member.username == name))
            if member and (member.org_id, member.role) != (org, role):
                raise RuntimeError('A demo username is already assigned to another workspace.')
            if not member:
                member = Member(org_id=org, username=name, role=role, password=password_digest(passwords[name]))
                db.add(member)
            members[name] = member
        db.flush()
        rules, issues = compile_local(EXAMPLE)
        if issues:
            raise RuntimeError('The demo agreement failed policy validation.')
        for name in ('demo-reviewer', 'demo-reviewer-2'):
            reviewer = members[name]
            existing = db.scalar(select(Policy).where(Policy.org_id == reviewer.org_id, Policy.method == 'demo-reviewed'))
            if not existing:
                policy = Policy(org_id=reviewer.org_id, title='Approved image batch SLA', source=EXAMPLE, source_hash=sha(EXAMPLE),
                                rules=[item.model_dump() for item in rules], issues=[], method='demo-reviewed',
                                status='approved', approved_by=reviewer.id, approved_at=time.time())
                db.add(policy)
                db.flush()
                record(db, reviewer.org_id, 'policy', policy.id, 'PolicyApproved', actor=reviewer.id, source_hash=policy.source_hash)
    return path
