"""Supervise the API and optional research worker in the single-container deployment."""
import logging
import os
import signal
import subprocess
import sys
import threading

LOGGER = logging.getLogger('pact.service')


def supervise(commands, stop=None, poll=.1, shutdown_timeout=10):
    stop = stop or threading.Event()
    children = {}
    result = 0
    try:
        for name, command in commands.items():
            children[name] = subprocess.Popen(command)
            LOGGER.info('Started %s process', name)
        while not stop.wait(poll):
            ended = next((name for name, child in children.items() if child.poll() is not None), None)
            if ended is not None:
                LOGGER.error('%s exited unexpectedly (status %s); stopping the service', ended, children[ended].returncode)
                result = 1
                break
    except (OSError, subprocess.SubprocessError):
        LOGGER.error('Could not start a required service process')
        result = 1
    finally:
        for child in children.values():
            if child.poll() is None:
                child.terminate()
        for child in children.values():
            try:
                child.wait(timeout=shutdown_timeout)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    return result


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    stop = threading.Event()
    def request_stop(_signal, _frame):
        stop.set()
    for name in (signal.SIGTERM, signal.SIGINT):
        signal.signal(name, request_stop)
    commands = {}
    if os.getenv('PACT_RUN_WORKER', '1') == '1':
        commands['worker'] = [sys.executable, '-m', 'pact.worker']
    commands['api'] = [sys.executable, '-m', 'uvicorn', 'pact.api:app', '--host', '0.0.0.0',
                       '--port', os.getenv('PORT', '8765'), '--proxy-headers', '--forwarded-allow-ips=*']
    return supervise(commands, stop)


if __name__ == '__main__':
    raise SystemExit(main())
