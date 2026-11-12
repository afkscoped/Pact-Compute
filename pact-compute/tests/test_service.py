import subprocess
import sys
import threading

import pytest

from pact import service


@pytest.mark.parametrize('status', [0, 7])
def test_unexpected_worker_exit_stops_the_api_and_fails_service(status, monkeypatch):
    children = []
    popen = subprocess.Popen
    def track(command):
        child = popen(command)
        children.append(child)
        return child
    monkeypatch.setattr(service.subprocess, 'Popen', track)
    result = service.supervise({'worker': [sys.executable, '-c', f'import time; time.sleep(.2); raise SystemExit({status})'],
                                'api': [sys.executable, '-c', 'import time; time.sleep(60)']}, poll=.02)
    assert result == 1 and len(children) == 2
    assert all(child.poll() is not None for child in children)


def test_requested_shutdown_reaps_all_children(monkeypatch):
    stop = threading.Event()
    children = []
    popen = subprocess.Popen
    def track(command):
        child = popen(command)
        children.append(child)
        return child
    monkeypatch.setattr(service.subprocess, 'Popen', track)
    timer = threading.Timer(.3, stop.set)
    timer.start()
    try:
        assert service.supervise({'api': [sys.executable, '-c', 'import time; time.sleep(60)']}, stop, poll=.02) == 0
    finally:
        timer.join()
    assert all(child.poll() is not None for child in children)
