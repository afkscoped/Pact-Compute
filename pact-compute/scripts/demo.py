"""Persistent local faculty demo, isolated from the configured teammate database."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser

import psutil

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.local' / 'faculty-demo'
HOST = '127.0.0.1'
PORT = 8767
URL = f'http://{HOST}:{PORT}'
SIGN_IN_URL = f'{URL}/?start=sign-in'
START_REQUIRED = 3  # Exit status for the PowerShell launcher's preflight.


def registered_process(row):
    try:
        process = psutil.Process(row['pid'])
        if abs(process.create_time() - row['created']) < .01:
            return process
    except psutil.NoSuchProcess:
        pass
    return None


def check_port():
    with socket.socket() as probe:
        try:
            probe.bind((HOST, PORT))
        except OSError as error:
            raise SystemExit(f'Cannot start the faculty demo on {URL}: {error}') from None


def show_demo(args, already_running=False):
    status = 'already running' if already_running else 'running'
    print(f'Faculty demo {status}. Open the sign-in page at {SIGN_IN_URL}')
    print(f'Admin password (admin_password): {STATE / "local-credentials.json"}')
    print(f'Producer and consumer passwords: {STATE / "market-credentials.json"}')
    print('Stop with run-demo.cmd -Stop. GPU readiness is shown in the console.')
    if not args.no_browser:
        webbrowser.open_new_tab(SIGN_IN_URL)


def open_existing(registry, args):
    rows = json.loads(registry.read_text()) if registry.exists() else []
    processes = [registered_process(row) for row in rows]
    if not any(processes):
        check_port()
        return False

    if not all(processes):
        raise SystemExit('A demo service stopped. Run .\\run-demo.cmd -Stop and then .\\run-demo.cmd.')
    api = processes[0]
    api_pids = {api.pid, *(child.pid for child in api.children(recursive=True))}
    owns_port = any(connection.pid in api_pids and connection.status == psutil.CONN_LISTEN
                    and connection.laddr == (HOST, PORT) for connection in psutil.net_connections(kind='tcp4'))
    if not owns_port:
        raise SystemExit(f'The saved demo is not listening on {URL}. Run .\\run-demo.cmd -Stop before retrying.')
    try:
        with urlopen(URL + '/api/health', timeout=3) as response:
            healthy = json.load(response).get('status') == 'ok'
    except (OSError, ValueError):
        healthy = False
    if not healthy:
        raise SystemExit('The demo API did not pass its health check. Run .\\run-demo.cmd -Stop before retrying.')
    if len(processes) < 3 and not args.no_gpu:
        raise SystemExit('The demo is running without the GPU. Run .\\run-demo.cmd -Stop and then .\\run-demo.cmd.')
    show_demo(args, already_running=True)
    return True


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--stop', action='store_true')
    action.add_argument('--open-existing', action='store_true')
    parser.add_argument('--no-gpu', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    registry = STATE / 'processes.json'
    if args.stop:
        if registry.exists():
            for row in reversed(json.loads(registry.read_text())):
                try:
                    process = registered_process(row)
                    if process is not None:
                        for child in process.children(recursive=True):
                            child.terminate()
                        process.terminate()
                        try:
                            process.wait(10)
                        except psutil.TimeoutExpired:
                            process.kill()
                except psutil.NoSuchProcess:
                    pass
            registry.unlink()
        print('Faculty demo stopped. Saved accounts and results are retained.')
        return
    if open_existing(registry, args):
        return
    if args.open_existing:
        return START_REQUIRED
    credentials = STATE / 'local-credentials.json'
    if not credentials.exists():
        credentials.write_text(json.dumps({k: secrets.token_urlsafe(32) for k in
            ('admin_password', 'runner_token', 'signing_secret')}, indent=2))
    secret = json.loads(credentials.read_text())
    env = {**os.environ, 'PYTHONPATH': str(ROOT / 'backend'), 'PYTHONUTF8': '1',
           'PACT_STATE_DIR': str(STATE), 'PACT_DATABASE_URL': 'sqlite:///' + (STATE / 'demo.db').as_posix(),
           'PACT_DB_TLS': '0', 'PACT_URL': URL, 'PACT_SECURE_COOKIE': '0',
           'PACT_ARTIFACT_BACKEND': 'local', 'PACT_SOURCE_DIR': str(ROOT.parent / 'PACT-Compute-data-preflight'),
           'GROQ_API_KEY': '', 'PACT_LLM_API_KEY': '', 'PACT_RUNNER_ID': 'native-gpu',
           'PACT_RUNNER_GRID_ZONE': '', 'PACT_GPU_PYTHON': os.getenv('PACT_DEMO_GPU_PYTHON', sys.executable), 'PACT_GPU_ENGINE': 'driver',
           'PACT_ADMIN_PASSWORD': secret['admin_password'], 'PACT_RUNNER_TOKEN': secret['runner_token'],
           'PACT_SIGNING_SECRET': secret['signing_secret'], 'TORCH_HOME': str(STATE / 'torch')}
    def run(*command):
        subprocess.run([sys.executable, *command], cwd=ROOT, env=env, check=True)
    for command in ('init', 'import', 'market-demo'):
        run('-m', 'pact.cli', command)
    if not (STATE / 'evaluations' / 'publication-study.json').exists():
        run('-m', 'pact.cli', 'publication-study', '--seeds', '20', '--jobs', '90')
        run('-m', 'pact.cli', 'benchmark')
    if not args.no_gpu:
        weights = STATE / 'torch/hub/checkpoints/mobilenet_v3_large-5c1a4163.pth'
        cached = ROOT / '.local/torch/hub/checkpoints' / weights.name
        if not weights.exists() and cached.exists():
            weights.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cached, weights)
        subprocess.run([env['PACT_GPU_PYTHON'], 'backend/pact/gpu_task.py', 'prepare', '--engine', 'driver'], cwd=ROOT, env=env, check=True)
        env['PACT_MODEL_WEIGHTS_SHA256'] = hashlib.sha256(weights.read_bytes()).hexdigest()
    children = []
    try:
        commands = [('api', ['uvicorn', 'pact.api:app', '--host', HOST, '--port', str(PORT)])]
        commands += [('worker', ['pact.worker'])]
        if not args.no_gpu:
            commands += [('runner', ['pact.runner'])]
        for name, command in commands:
            with (STATE / (name + '.log')).open('w') as log:
                child = subprocess.Popen([sys.executable, '-m', *command], cwd=ROOT, env=env,
                    stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            children.append(child)
        for _ in range(90):
            if any(child.poll() is not None for child in children):
                raise RuntimeError('A service exited. See .local/faculty-demo/*.log.')
            try:
                with urlopen(URL + '/api/health', timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(.5)
        else:
            raise RuntimeError('API did not become ready.')
        registry.write_text(json.dumps([{'pid': child.pid, 'created': psutil.Process(child.pid).create_time()}
                                       for child in children]))
    except BaseException:
        for child in children:
            child.terminate()
        raise
    show_demo(args)


if __name__ == '__main__':
    sys.exit(main())
