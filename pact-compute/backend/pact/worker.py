import json
import logging
import threading
import time

from sqlalchemy import or_, select

from .carbon import refresh_gb
from .config import GPU_ZONE
from .db import ResearchRun, Runner, record, save_artifact, session, uid
from .live import expire_leases, organization_lock
from .research import Scenario, experiment
from .security import sign

LOGGER = logging.getLogger('pact.worker')
LEASE = 150


class LeaseLost(Exception):
    pass


def claim():
    now = time.time()
    with session(write=True) as db:
        stmt = select(ResearchRun).where(or_(ResearchRun.status == 'queued',
                                            (ResearchRun.status == 'running') & (ResearchRun.lease_until < now)))
        run = db.scalar(stmt.order_by(ResearchRun.created_at).with_for_update(skip_locked=True).limit(1))
        if run:
            run.worker = uid()
            run.lease_until = now + LEASE
            run.status = 'running'
            run.progress = 0
            record(db, run.org_id, 'run', run.id, 'ExperimentStarted', worker=run.worker)
        return run


def locked_run(db, leased):
    run = db.scalar(select(ResearchRun).where(ResearchRun.id == leased.id).with_for_update())
    if not run or run.status != 'running' or run.worker != leased.worker:
        raise LeaseLost(leased.id)
    return run


def progress(leased, percent=None):
    with session(write=True) as db:
        run = locked_run(db, leased)
        run.lease_until = time.time() + LEASE
        if percent is not None and percent > run.progress:
            run.progress = min(99, percent)
            if run.progress % 10 == 0:
                record(db, run.org_id, 'run', run.id, 'ExperimentProgress', percent=run.progress)


def process(leased):
    finished = threading.Event()

    def renew():
        while not finished.wait(30):
            try:
                progress(leased)
            except LeaseLost:
                break
            except Exception:
                LOGGER.exception('Could not renew research lease')

    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    try:
        spec = Scenario.model_validate(leased.config['scenario'])
        result, evidence = experiment(spec, leased.config['rules'], lambda value: progress(leased, value))
        manifest = {'schema': 'pact-research-evidence-1', 'run_id': leased.id,
                    'policy_hash': leased.config.get('policy_hash'), **evidence}
        bundle = json.dumps({'manifest': manifest, 'hmac_sha256': sign(manifest)}, allow_nan=False, separators=(',', ':')).encode()
        with session(write=True) as db:
            run = locked_run(db, leased)
            artifact = save_artifact(db, run.org_id, bundle, 'research-evidence.json', 'research')
            run.result = result
            run.artifact_id = artifact.id
            run.status = 'completed'
            run.finished_at = time.time()
            run.progress = 100
            record(db, run.org_id, 'run', run.id, 'ExperimentCompleted', artifact_id=artifact.id, sha256=artifact.digest)
        LOGGER.info('Experiment %s completed', leased.id)
    except LeaseLost:
        LOGGER.warning('Research run %s was reclaimed', leased.id)
    except Exception as exc:
        LOGGER.exception('Experiment %s failed', leased.id)
        with session(write=True) as db:
            try:
                run = locked_run(db, leased)
            except LeaseLost:
                return
            run.status = 'failed'
            run.error = str(exc)[:500] if isinstance(exc, (ValueError, FileNotFoundError)) else 'Research worker failed. See the operator log.'
            run.finished_at = time.time()
            record(db, run.org_id, 'run', run.id, 'ExperimentFailed', message=run.error)
    finally:
        finished.set()
        thread.join()


def reconcile():
    with session() as db:
        orgs = list(db.scalars(select(Runner.org_id).distinct().order_by(Runner.org_id)))
    for org in orgs:
        with session(write=True) as db:
            organization_lock(db, org)
            expire_leases(db, org, time.time())


def maintain(stop):
    last_carbon = 0
    while not stop.is_set():
        try:
            reconcile()
            if GPU_ZONE == 'GB' and time.monotonic() - last_carbon > 600:
                last_carbon = time.monotonic()
                refresh_gb()
        except Exception:
            LOGGER.exception('Maintenance will retry')
        stop.wait(4)


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    stop = threading.Event()
    supervisor = threading.Thread(target=maintain, args=(stop,), daemon=True)
    supervisor.start()
    try:
        while True:
            try:
                job = claim()
                if job:
                    process(job)
                else:
                    time.sleep(1.2)
            except Exception:
                LOGGER.exception('Worker will retry')
                time.sleep(4)
    finally:
        stop.set()


if __name__ == '__main__':
    main()
