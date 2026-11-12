"""Real local process recovery exercised only by the supervised browser harness."""
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

import httpx


def exercise(root, state, reports, env, children, streams):
    def wait(operation, predicate, timeout=45):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            try:
                value = operation()
                if predicate(value):
                    return value
            except httpx.HTTPError:
                pass
            time.sleep(.05)
        raise AssertionError('Local recovery condition did not complete in the declared timeout')

    def restart(index, arguments):
        old = children[index]
        assert old.poll() is None
        old.terminate()
        old.wait(timeout=15)
        children[index] = subprocess.Popen([sys.executable, '-m', *arguments], cwd=root, env=env,
            stdout=streams[index], stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    credentials = json.loads((state / 'local-credentials.json').read_bytes())
    with httpx.Client(base_url=env['PACT_URL'], timeout=10) as client:
        client.post('/api/v1/session', json={'username': 'admin', 'password': credentials['admin_password']}).raise_for_status()
        draft = client.post('/api/v1/policies', json={'title': 'Real recovery fixture', 'source': 'Jobs require at least 1 GiB VRAM.'})
        draft.raise_for_status()
        policy_id = draft.json()['id']
        client.post('/api/v1/policies/' + policy_id + '/approve').raise_for_status()

        def submit(title):
            response = client.post('/api/v1/jobs', headers={'Idempotency-Key': 'recovery-' + uuid.uuid4().hex},
                                   json={'title': title, 'policy_id': policy_id, 'sample_count': 1, 'mode': 'live'})
            response.raise_for_status()
            return response.json()['id']

        job_id = submit('Cancellation during real runner workload startup')
        endpoint = '/api/v1/jobs/' + job_id
        wait(lambda: client.get(endpoint).json(), lambda body: body['status'] == 'running')
        cancelled = client.post(endpoint + '/cancel')
        cancelled.raise_for_status()
        result = wait(lambda: client.get(endpoint).json(), lambda body: body['status'] in {'cancelled', 'failed', 'succeeded', 'expired'})
        assert result['status'] == 'cancelled', 'Cancellation must be acknowledged by the actual runner'
        assert any(event['kind'] == 'CapacityReleased' for event in result['events'])
        assert not result['attempts'][0]['result'].get('artifact_id')
        journal = state / 'runner-native-gpu.json'
        wait(lambda: journal.exists(), lambda exists: not exists)
        # Stop only our now-idle runner. The next job must be executed by the new process.
        restart(2, ['pact.runner'])
        next_job = submit('Physical GPU execution after runner process restart')
        completed = wait(lambda: client.get('/api/v1/jobs/' + next_job).json(),
                         lambda body: body['status'] in {'succeeded', 'failed', 'expired'}, timeout=90)
        assert completed['status'] == 'succeeded' and len(completed['attempts']) == 1
        # A cookie established before an actual API process restart must remain valid.
        retained = client.get('/api/v1/session').json()['id']
        cursor = completed['events'][-2]['seq']
        final_seq = completed['events'][-1]['seq']
        restart(0, ['uvicorn', 'pact.api:app', '--host', '127.0.0.1', '--port', '8766'])
        wait(lambda: client.get('/api/health'), lambda response: response.status_code == 200)
        assert client.get('/api/v1/session').json()['id'] == retained
        with client.stream('GET', '/api/v1/jobs/' + next_job + '/events', headers={'Last-Event-ID': str(cursor)}) as stream:
            stream.raise_for_status()
            first_id = next(line for line in stream.iter_lines() if line.startswith('id: '))
            assert first_id == f'id: {final_seq}'
        persisted = client.get('/api/v1/jobs/' + next_job).json()
        assert persisted['status'] == 'succeeded' and len(persisted['attempts']) == 1
    report = {'actual_local_processes': True, 'cancel_during_workload_startup': 'PASS',
              'cancellation_acknowledged_and_capacity_released': True,
              'runner_process_restart_then_physical_execution': 'PASS', 'attempt_count_after_restart': 1,
              'api_process_restart_session_persistence': 'PASS', 'sse_last_event_id_after_restart': 'PASS',
              'scope': 'Managed loopback processes and local GPU only; no pre-existing service or hosted mutation'}
    (reports / 'runtime-recovery.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
