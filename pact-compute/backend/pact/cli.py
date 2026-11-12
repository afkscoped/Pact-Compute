import argparse
import getpass
import hmac
import json
import re
from pathlib import Path

from sqlalchemy import select

from .benchmark import evaluate
from .config import STATE
from .datasets import import_sources, write_atomic
from .db import Base, Member, Organization, Runner, engine, session, sha, sqlite
from .security import ORG_ID, bootstrap, password_digest, sign


def main():
    parser = argparse.ArgumentParser(prog='pact')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    sub.add_parser('import')
    sub.add_parser('benchmark')
    sub.add_parser('market-demo')
    study = sub.add_parser('publication-study')
    study.add_argument('--seeds', type=int, default=20)
    study.add_argument('--jobs', type=int, default=90)
    check = sub.add_parser('verify')
    check.add_argument('evidence', type=Path)
    member = sub.add_parser('member')
    member.add_argument('username')
    member.add_argument('role', choices=['admin', 'operator', 'reviewer', 'submitter', 'researcher', 'producer', 'consumer'])
    member.add_argument('--org', default=ORG_ID)
    member.add_argument('--org-name')
    runner = sub.add_parser('enroll-runner')
    runner.add_argument('runner_id')
    runner.add_argument('name')
    runner.add_argument('--org', default=ORG_ID)
    runner.add_argument('--zone')
    runner.add_argument('--rate-cents', type=int, default=250)
    args = parser.parse_args()
    if args.command == 'init':
        if sqlite:
            Base.metadata.create_all(engine)
        bootstrap()
        print('Control-plane data initialized.')
    elif args.command == 'import':
        card = import_sources()
        print(f'{card["id"]}: {card["gpu_pods"]} GPU pods and {card["carbon_intervals"]} carbon intervals.')
    elif args.command == 'benchmark':
        print(json.dumps(evaluate(STATE / 'evaluations'), indent=2))
    elif args.command == 'market-demo':
        from .demo import provision_demo

        print(f'Local market accounts are ready. Open {provision_demo()} privately for their passwords.')
    elif args.command == 'publication-study':
        from .publication import run

        run(STATE / 'evaluations', seeds=args.seeds, jobs=args.jobs, progress=lambda line: print(line, flush=True))
        print('Publication metrics and evidence saved under .local/evaluations.')
    elif args.command == 'verify':
        data = json.loads(args.evidence.read_bytes())
        if not hmac.compare_digest(sign(data['manifest']), data['hmac_sha256']):
            parser.exit(1, 'Evidence signature mismatch.\n')
        print('Evidence signature verified.')
    elif args.command == 'enroll-runner':
        if not re.fullmatch(r'[a-z0-9-]{1,32}', args.runner_id) or not 1 <= len(args.name) <= 100:
            parser.error('Use a runner slug up to 32 characters and a name up to 100.')
        if args.zone and not re.fullmatch(r'[A-Z0-9_-]{2,20}', args.zone):
            parser.error('Use an uppercase grid zone code.')
        if not 0 <= args.rate_cents <= 100000:
            parser.error('Enter a rate between 0 and 100000 credit cents per GPU-hour.')
        token = sign({'purpose': 'runner-enrollment-v1', 'runner': args.runner_id})
        digest = sha(token)
        with session(write=True) as db:
            existing = db.get(Runner, args.runner_id)
            if not db.get(Organization, args.org):
                parser.error('Choose an existing organization.')
            if existing and (existing.org_id, existing.token_digest) != (args.org, digest):
                parser.error('This runner ID is already enrolled.')
            if not existing:
                db.add(Runner(id=args.runner_id, org_id=args.org, name=args.name, token_digest=digest,
                              zone=args.zone, rate_cents=args.rate_cents))
        target = STATE / f'{args.runner_id}-credentials.json'
        write_atomic(target, json.dumps({'runner_id': args.runner_id, 'runner_token': token}, indent=2).encode())
        print(f'Runner enrolled. Store its token privately from {target}.')
    else:
        if not re.fullmatch(r'[a-z][a-z0-9._-]{1,63}', args.username) or not re.fullmatch(r'[a-z0-9-]{1,32}', args.org):
            parser.error('Use a valid username and organization slug.')
        password = getpass.getpass('New account password: ')
        if len(password) < 12:
            parser.error('Use at least 12 characters.')
        digest = password_digest(password)
        with session(write=True) as db:
            if db.scalar(select(Member).where(Member.username == args.username)):
                parser.error('The username already exists.')
            if not db.get(Organization, args.org):
                if not args.org_name:
                    parser.error('Supply --org-name when creating a new organization.')
                db.add(Organization(id=args.org, name=args.org_name))
                db.flush()
            db.add(Member(org_id=args.org, username=args.username, role=args.role, password=digest))
        print('Account created.')


if __name__ == '__main__':
    main()
