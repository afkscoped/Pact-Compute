import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx

from .config import STATE, URL
from .datasets import write_atomic
from .db import sha
from .security import RUNNER_ID, provisioned_secrets

WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
GPU_TASK = Path(__file__).with_name('gpu_task.py')
GPU_PYTHON = Path(os.getenv('PACT_GPU_PYTHON', sys.executable))
ENGINE = os.getenv('PACT_GPU_ENGINE', 'driver')
RUNNER = os.getenv('PACT_RUNNER_ID', RUNNER_ID)
if not re.fullmatch(r'[a-z0-9-]{1,32}', RUNNER):
    raise ValueError('PACT_RUNNER_ID must be a registered runner slug.')
JOURNAL = STATE / f'runner-{RUNNER}.json'


def query_power():
    try:
        process = subprocess.run(['nvidia-smi', '-i', '0', '--query-gpu=power.draw', '--format=csv,noheader,nounits'],
                                 capture_output=True, text=True, timeout=2, creationflags=WINDOW, check=True)
        watts = float(process.stdout.strip().splitlines()[0])
        return watts if 0 < watts <= 10000 else None
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response


def send_event(client, claim, state, **payload):
    return request(client, 'POST', f'/attempts/{claim["attempt_id"]}/events',
                   json={'fence': claim['fence'], 'state': state, **payload}).json()


def probe():
    result = subprocess.run([str(GPU_PYTHON), str(GPU_TASK), 'probe', '--engine', ENGINE], capture_output=True, text=True,
                            timeout=120, creationflags=WINDOW, check=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


def send_heartbeat(client, identity, claim=None):
    body = {'device': identity['device'], 'vram_mib': identity['vram_mib'], 'ready': identity['ready']}
    if claim:
        body.update(attempt_id=claim['attempt_id'], fence=claim['fence'])
    return request(client, 'POST', '/heartbeat', json=body).json()


def execute(client, claim, identity):
    folder = STATE / 'runner' / claim['attempt_id']
    folder.mkdir(parents=True, exist_ok=True)
    input_file, output_file, log_file = (folder / name for name in ('input.json', 'output.json', 'process.log'))
    staging_began = time.monotonic()
    try:
        payload = request(client, 'GET', f'/attempts/{claim["attempt_id"]}/input',
                          headers={'Lease-Fence': claim['fence']}).content
        if sha(payload) != claim['input_sha256']:
            return {'state': 'failed', 'message': 'Input checksum did not match the reservation.'}
        write_atomic(input_file, payload)
        if send_heartbeat(client, identity, claim)['cancel_requested']:
            return {'state': 'cancelled', 'message': 'Cancelled before workload start.'}
        send_event(client, claim, 'started')
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 409:
            return {'state': 'cancelled', 'message': 'The dispatch lease is no longer executable.'}
        raise
    staging = time.monotonic() - staging_began
    budget = min(claim['max_runtime_s'], max(0, claim['reserved_until'] - time.time() - 1))
    if budget <= 0:
        return {'state': 'expired', 'message': 'The reservation window elapsed.'}
    began = time.monotonic()
    samples = []
    last_heartbeat = began
    action = None
    with log_file.open('wb') as log:
        args = [str(GPU_PYTHON), str(GPU_TASK), 'execute', '--input', str(input_file), '--output', str(output_file),
                '--parent', str(os.getpid()), '--timeout', str(budget), '--engine', ENGINE]
        with subprocess.Popen(args, stdout=log, stderr=log, creationflags=WINDOW) as proc:
            try:
                while proc.poll() is None:
                    at = time.monotonic()
                    if at - began >= budget:
                        action = 'expired'
                        proc.kill()
                        break
                    value = query_power()
                    if value is not None:
                        samples.append((time.monotonic(), value))
                    if at - last_heartbeat >= 5:
                        try:
                            if send_heartbeat(client, identity, claim)['cancel_requested']:
                                action = 'cancelled'
                                proc.kill()
                                break
                            last_heartbeat = at
                        except httpx.HTTPError:
                            if at - last_heartbeat > 20:
                                action = 'failed'
                                proc.kill()
                                break
                    time.sleep(.75)
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
    duration = time.monotonic() - began
    samples = [(at, w) for at, w in samples if at <= began + duration]
    covered = sum(b[0] - a[0] for a, b in zip(samples, samples[1:]) if b[0] - a[0] <= 4)
    energy = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(samples, samples[1:]) if b[0] - a[0] <= 4)
    produced = json.loads(output_file.read_bytes()) if proc.returncode == 0 and output_file.is_file() and not action else None
    compute = produced.get('inference_seconds') if produced else None
    compute = compute if type(compute) in (int, float) and 0 <= compute <= duration else None
    stages = {'staging': round(staging, 3), **({'compute': round(compute, 6), 'startup': round(max(0, duration - compute), 3)} if compute is not None else {})}
    result = {'duration_s': round(duration, 3), 'stage_seconds': stages, 'device': identity['device'], 'power_samples': len(samples),
              'telemetry_coverage': round(min(1, covered / max(duration, .001)), 3),
              'gpu_energy_kwh': round(energy / 3_600_000, 8) if covered else None}
    if produced is not None:
        return {'state': 'succeeded', **result, 'artifact': produced}
    return {'state': action or ('expired' if proc.returncode == 124 else 'failed'), **result,
            'message': f'GPU process exited with code {proc.returncode}.'}


def save_journal(claim, result=None):
    write_atomic(JOURNAL, json.dumps({'claim': claim, 'result': result}, allow_nan=False).encode())


def flush_journal(client):
    if not JOURNAL.is_file():
        return True
    entry = json.loads(JOURNAL.read_bytes())
    claim, result = entry['claim'], entry['result']
    if result is None:
        if time.time() < claim['reserved_until'] + 2:
            return False
        result = {'state': 'interrupted', 'message': 'Runner restarted. The original execution window has elapsed.'}
    try:
        send_event(client, claim, **result)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 422) and result['state'] == 'succeeded':
            send_event(client, claim, 'failed', message='The control plane rejected the output manifest.')
        else:
            raise
    JOURNAL.unlink()
    return True


def main():
    token = os.getenv('PACT_RUNNER_TOKEN')
    if not token:
        token = (provisioned_secrets() if RUNNER == RUNNER_ID else json.loads(
            (STATE / f'{RUNNER}-credentials.json').read_bytes()))['runner_token']
    with httpx.Client(base_url=f'{URL}/api/v1/runners/{RUNNER}', headers={'Authorization': 'Bearer ' + token}, timeout=6) as client:
        identity = {'device': 'CUDA initialization pending', 'vram_mib': 0, 'ready': False}
        probed = 0.0
        while True:
            try:
                if not identity['ready'] and time.monotonic() - probed > 30:
                    probed = time.monotonic()
                    try:
                        identity = {**probe(), 'ready': True}
                        print('GPU verified:', identity['device'], flush=True)
                    except (OSError, ValueError, subprocess.SubprocessError) as exc:
                        lines = (getattr(exc, 'stderr', None) or str(exc)).strip().splitlines()
                        identity['device'] = ('CUDA unavailable: ' + (lines[-1] if lines else 'probe failed'))[:198]
                        print(identity['device'], flush=True)
                send_heartbeat(client, identity)
                if not flush_journal(client) or not identity['ready']:
                    time.sleep(2)
                    continue
                claim = request(client, 'POST', '/claim').json()
                if claim:
                    save_journal(claim)
                    print('Running GPU attempt', claim['attempt_id'], flush=True)
                    result = execute(client, claim, identity)
                    save_journal(claim, result)
                    flush_journal(client)
                    print('GPU attempt result:', result['state'], flush=True)
            except (httpx.HTTPError, OSError, ValueError) as exc:
                print('Runner will retry:', type(exc).__name__, flush=True)
            time.sleep(1.5)


if __name__ == '__main__':
    main()
