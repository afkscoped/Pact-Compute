"""Independent stream regressions with a disposable database and real event rows."""
from contextlib import contextmanager
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pact import outbox
from pact.db import Event, Organization


@pytest.fixture
def event_store(tmp_path, monkeypatch):
    engine = create_engine('sqlite:///' + (tmp_path / 'events.db').as_posix())
    Organization.__table__.create(engine)
    Event.__table__.create(engine)

    @contextmanager
    def session():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    monkeypatch.setattr(outbox, 'session', session)
    with Session(engine) as db:
        db.add_all([Organization(id='events-a', name='A'), Organization(id='events-b', name='B')])
        db.commit()
    yield engine
    engine.dispose()


def append(engine, start, count):
    with Session(engine) as db:
        db.add_all(Event(org_id='events-b' if i % 11 == 0 else 'events-a', entity_type='job',
                         entity_id='stream-job', kind='Step', details={'ordinal': i})
                   for i in range(start, start + count))
        db.commit()


def ordinals(lines):
    return [json.loads(line.split('data: ', 1)[1])['details']['ordinal']
            for line in lines if line.startswith('id:')]


def test_reconnect_drains_all_pages_without_cross_tenant_events(event_store):
    append(event_store, 0, 2505)
    expected = [i for i in range(2505) if i % 11]
    stream = outbox.entity_stream('events-a', 'job', 'stream-job', window=0)
    lines = list(stream)
    assert ordinals(lines) == expected
    # Reconnect from an actual emitted ID, rather than an ordinal or a global tip.
    cut = lines[1200]
    last_id = int(cut.splitlines()[0].split(': ')[1])
    assert ordinals(outbox.entity_stream('events-a', 'job', 'stream-job', last_id, window=0)) == expected[1201:]


def test_live_delivery_drains_burst_larger_than_one_batch(event_store):
    stream = outbox.entity_stream('events-a', 'job', 'stream-job', window=1, pause=0)
    assert next(stream).startswith(': keepalive')
    append(event_store, 0, 2505)
    assert ordinals(stream) == [i for i in range(2505) if i % 11]
