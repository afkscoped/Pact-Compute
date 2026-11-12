import hashlib
import hmac
import json
import os
import secrets
import time

from sqlalchemy import select

from .config import GPU_ZONE, STATE
from .db import Login, Member, Organization, Runner, session, sha

COOKIE = 'pact_session'
ORG_ID = 'local-lab'
RUNNER_ID = 'native-gpu'


def password_digest(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 350_000)
    return f'{salt}:{digest.hex()}'


def password_ok(password, stored):
    salt, _ = stored.split(':', 1)
    return hmac.compare_digest(password_digest(password, salt), stored)


def provisioned_secrets():
    path = STATE / 'local-credentials.json'
    if not path.exists():
        values = {'admin_password': os.getenv('PACT_ADMIN_PASSWORD') or secrets.token_urlsafe(18),
                  'runner_token': os.getenv('PACT_RUNNER_TOKEN') or secrets.token_urlsafe(32),
                  'signing_secret': os.getenv('PACT_SIGNING_SECRET') or secrets.token_hex(32)}
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(values, stream, indent=2)
    return json.loads(path.read_text(encoding='utf-8'))


def bootstrap():
    credentials = provisioned_secrets()
    with session(write=True) as db:
        org = db.get(Organization, ORG_ID)
        if not org:
            db.add(Organization(id=ORG_ID, name='GPU Operations Lab'))
            db.flush()
        if not db.scalar(select(Member).where(Member.username == 'admin')):
            db.add(Member(org_id=ORG_ID, username='admin', password=password_digest(credentials['admin_password']), role='admin'))
        runner = db.get(Runner, RUNNER_ID)
        if not runner:
            db.add(Runner(id=RUNNER_ID, org_id=ORG_ID, name='Local GPU', token_digest=sha(credentials['runner_token']), zone=GPU_ZONE))
        elif runner.zone != GPU_ZONE:
            runner.zone = GPU_ZONE


def authenticated(db, raw):
    if not raw:
        return None
    login = db.get(Login, sha(raw))
    if login and login.expires > time.time():
        return db.get(Member, login.member_id)
    return None


def sign(value):
    secret = provisioned_secrets()['signing_secret']
    canonical = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hmac.new(secret.encode(), canonical, 'sha256').hexdigest()
