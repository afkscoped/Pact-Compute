"""Repeat real marketplace confirmation races on an isolated SQLite database.

Default: five rounds in regression CI. PACT_CONTENTION_CASES=1000 runs the gate.
This validates transactional reservations; it does not simulate a GPU test pass.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
import time

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import make_url

from pact import db, live, market, storage
from pact.policy import compile_local


def test_repeated_final_slot_races_create_exactly_one_booking(tmp_path, monkeypatch):
    cases = int(os.getenv('PACT_CONTENTION_CASES', '5'))
    assert 1 <= cases <= 1000
    postgres_url = os.getenv('PACT_CONTENTION_POSTGRES_URL')
    if postgres_url:
        target = make_url(postgres_url)
        assert target.host == '127.0.0.1' and target.database.startswith('pact_validation_')
        engine = create_engine(target, pool_pre_ping=True)
        monkeypatch.setattr(db, 'sqlite', False)
    else:
        engine = create_engine('sqlite:///' + (tmp_path / 'contention.db').as_posix(), connect_args={'timeout': 30})
        event.listen(engine, 'connect', db.configure_sqlite)
        db.Base.metadata.create_all(engine)
    monkeypatch.setattr(db, 'engine', engine)
    if postgres_url:
        from pact.config import STATE
        artifact_root = STATE / 'artifacts'
    else:
        artifact_root = tmp_path / 'artifacts'
    monkeypatch.setattr(storage, '_store', storage.LocalStore(artifact_root))
    now = time.time()
    source = 'Jobs require at least 1 GiB VRAM.'
    rules, issues = compile_local(source)
    assert not issues
    with db.session(write=True) as session:
        session.add_all(db.Organization(id=org, name=org) for org in ('supply', 'buyer-a', 'buyer-b'))
        session.flush()
        producer = db.Member(org_id='supply', username='race-producer', role='producer', password='unused-test-digest')
        buyers = [db.Member(org_id=org, username=org, role='consumer', password='unused-test-digest') for org in ('buyer-a', 'buyer-b')]
        reviewers = [db.Member(org_id=org, username=org + '-reviewer', role='reviewer', password='unused-test-digest') for org in ('buyer-a', 'buyer-b')]
        session.add_all([producer, *buyers, *reviewers])
        session.flush()
        policies = [db.Policy(org_id=buyer.org_id, title='Race policy', source=source, source_hash=db.sha(source),
                    rules=[rule.model_dump() for rule in rules], issues=[], method='reviewed-fixture', status='approved',
                    approved_at=now, approved_by=reviewer.id) for buyer, reviewer in zip(buyers, reviewers)]
        runner = db.Runner(id='race-gpu', org_id='supply', name='Controlled inventory fixture',
                           token_digest=db.sha('unused-fixture'), device='Contract-test inventory',
                           vram_mib=4096, ready=True, last_seen=now, rate_cents=250)
        session.add_all([runner, *policies])

    latency = []

    def confirm(item):
        buyer, quote_id = item
        start = time.perf_counter()
        try:
            with db.session(write=True) as session:
                result = market.confirm(session, buyer, quote_id, market.ConfirmInput())
            return 201, result, time.perf_counter() - start
        except live.LiveError as error:
            return error.status, None, time.perf_counter() - start

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            for case in range(cases):
                now = time.time()
                with db.session(write=True) as session:
                    session.get(db.Runner, runner.id).last_seen = now
                    offer = market.publish(session, producer, market.OfferInput(runner_id=runner.id, title=f'Race {case}',
                                           starts_at=now - 1, ends_at=now + 90, rate_cents=250))
                    quotes = [market.create_quote(session, buyer, market.QuoteInput(offer_id=offer['id'],
                              policy_id=policy.id, title=f'Race workload {case}', sample_count=1))
                              for buyer, policy in zip(buyers, policies)]
                assert all(quote['id'] for quote in quotes)
                results = list(pool.map(confirm, [(buyer, quote['id']) for buyer, quote in zip(buyers, quotes)]))
                assert sorted(row[0] for row in results) == [201, 409], (case, results)
                latency.extend(row[2] for row in results)
                winner = next(row[1] for row in results if row[0] == 201)
                # Duplicate confirmation must return the same booking.
                index = next(i for i, row in enumerate(results) if row[0] == 201)
                duplicate = confirm((buyers[index], quotes[index]['id']))
                assert duplicate[0] == 201 and duplicate[1]['id'] == winner['id']
                with db.session(write=True) as session:
                    booking = session.get(db.MarketBooking, winner['id'])
                    assert session.scalar(select(func.count()).select_from(db.Job).where(db.Job.status.in_(live.ACTIVE))) == 1
                    # Fixture reset between independent races; actual cancellation is covered separately.
                    session.get(db.Job, booking.job_id).status = 'cancelled'
            with db.session() as session:
                assert session.scalar(select(func.count()).select_from(db.MarketBooking).where(db.MarketBooking.producer_org_id == 'supply')) == cases
                assert session.scalar(select(func.count()).select_from(db.Job).where(db.Job.runner_id == runner.id)) == cases
        ordered = sorted(latency)
        evidence = {'cases': cases, 'confirmations': cases * 2, 'duplicate_retries': cases,
                    'double_bookings': 0, 'reservation_inventory': 'controlled test fixture, no GPU execution',
                    'database': 'PostgreSQL' if postgres_url else 'SQLite WAL', 'concurrency': 2,
                    'confirmation_p50_s': ordered[len(ordered) // 2],
                    'confirmation_p95_s': ordered[math.ceil(len(ordered) * .95) - 1]}
        output = os.getenv('PACT_CONTENTION_REPORT')
        if output:
            from pathlib import Path
            Path(output).write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    finally:
        engine.dispose()
