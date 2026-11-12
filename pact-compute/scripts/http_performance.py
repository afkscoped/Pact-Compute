"""Bounded API measurements against the supervised local validation instance."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import platform
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT.parent / 'reports' / 'final-validation'
STATE = ROOT / '.local' / 'validation' / 'browser'


def main():
    # Only the generated validation account is used. Never read user .env files.
    password = json.loads((STATE / 'local-credentials.json').read_bytes())['admin_password']
    with httpx.Client(base_url='http://127.0.0.1:8766', timeout=15) as client:
        client.post('/api/v1/session', json={'username': 'admin', 'password': password}).raise_for_status()
        policy = client.post('/api/v1/policies', json={'title': 'Bounded performance fixture',
                             'source': 'Jobs require at least 1 GiB VRAM.'})
        policy.raise_for_status()
        policy_id = policy.json()['id']
        client.post('/api/v1/policies/' + policy_id + '/approve').raise_for_status()
        spec = {'policy_id': policy_id, 'title': 'Performance preview', 'sample_count': 1}
        # Quote generation changes no capacity. Use the actual verified runner;
        # the separate contention fixture measures confirmation transactions.
        runners = client.get('/api/v1/runners').json()
        ready = next(row for row in runners if row['ready'] and row['id'] == 'native-gpu')
        now = time.time()
        offer = client.post('/api/v1/market/offers', json={'runner_id': ready['id'], 'title': 'Bounded quote benchmark',
                            'starts_at': now - 1, 'ends_at': now + 3600, 'rate_cents': 250})
        offer.raise_for_status()
        quote = {**spec, 'offer_id': offer.json()['id']}
        results = []
        for name, method, endpoint, body in [('jobs-read', 'GET', '/api/v1/jobs?limit=20', None),
                                          ('placement-preview', 'POST', '/api/v1/jobs/preview', spec),
                                          ('quote-generation', 'POST', '/api/v1/market/quotes', quote)]:
            def request(_):
                began = time.perf_counter()
                response = client.request(method, endpoint, json=body)
                response.raise_for_status()
                return time.perf_counter() - began
            # Warmup is excluded; report the declared small, warm local load.
            request(0)
            with ThreadPoolExecutor(max_workers=4) as pool:
                values = sorted(pool.map(request, range(100)))
            results.append({'endpoint': endpoint, 'name': name, 'samples': len(values), 'concurrency': 4,
                            'p50_s': values[len(values) // 2], 'p95_s': values[math.ceil(.95 * len(values)) - 1],
                            'max_s': values[-1], 'target_p95_s': 2,
                            'gate': 'PASS' if values[math.ceil(.95 * len(values)) - 1] < 2 else 'FAIL'})
        verification = STATE / 'verified' / 'verification.json'
        transfer = None
        if verification.exists():
            record = json.loads(verification.read_bytes())
            job = client.get('/api/v1/jobs/' + record['job_id'])
            job.raise_for_status()
            artifact_id = job.json()['attempts'][0]['result']['artifact_id']
            began = time.perf_counter()
            output = client.get('/api/v1/artifacts/' + artifact_id)
            output.raise_for_status()
            assert hashlib.sha256(output.content).hexdigest() == record['artifact_sha256']
            transfer = {'bytes': len(output.content), 'seconds': time.perf_counter() - began, 'hash_verified': True}
    report = {'platform': platform.platform(), 'database': 'isolated SQLite WAL',
              'scope': 'Warm loopback API with small local fixture; no WAN, production or long-duration throughput claim',
              'measurements': results, 'artifact_transfer': transfer}
    (REPORTS / 'performance-http.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Bounded local API measurements recorded (100 samples per endpoint, concurrency 4)')


if __name__ == '__main__':
    main()
