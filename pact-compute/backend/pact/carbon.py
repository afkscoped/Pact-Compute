import json
import os
import time
from datetime import datetime, timezone

import httpx

from .config import STATE
from .datasets import write_atomic


LIVE_CARBON = STATE / 'live-carbon.json'


def forecast_snapshot(zone, now):
    if not zone or not LIVE_CARBON.exists():
        return None
    try:
        data = json.loads(LIVE_CARBON.read_bytes())
    except (OSError, ValueError):
        return None
    if data['zone'] == zone and 0 <= now - data['retrieved_at'] <= 3600:
        return data
    return None


def refresh_gb():
    # NESO's public Great Britain national signal uses gCO2/kWh.
    now = time.time()
    start = datetime.fromtimestamp(now, timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    url = f'https://api.carbonintensity.org.uk/intensity/{start}/fw24h'
    response = httpx.get(url, timeout=10)
    response.raise_for_status()
    intervals = []
    for row in response.json()['data']:
        intensity = row['intensity']['forecast']
        if isinstance(intensity, (int, float)) and 0 <= intensity <= 2000:
            intervals.append({'start': datetime.fromisoformat(row['from']).timestamp(),
                              'end': datetime.fromisoformat(row['to']).timestamp(), 'intensity': intensity})
    if not intervals:
        raise ValueError('The forecast source returned no usable intervals.')
    snapshot = {'source': url, 'zone': 'GB', 'retrieved_at': now, 'unit': 'gCO2/kWh', 'intervals': intervals}
    write_atomic(LIVE_CARBON, json.dumps(snapshot).encode())
    return snapshot


def estimate(snapshot, start, end, power_w):
    if not snapshot or end <= start:
        return None
    total = 0.0
    cursor = start
    for interval in sorted(snapshot['intervals'], key=lambda item: item['start']):
        begin = max(cursor, interval['start'])
        finish = min(end, interval['end'])
        if finish <= begin:
            continue
        if begin > cursor:
            return None
        total += (finish - begin) * power_w * interval['intensity'] / 3_600_000
        cursor = finish
        if cursor >= end:
            return total
    return None


def power_bound():
    raw = os.getenv('PACT_RUNNER_POWER_BOUND_W')
    if raw:
        bound = int(raw)
        if not 1 <= bound <= 10_000:
            raise ValueError('PACT_RUNNER_POWER_BOUND_W must be between 1 and 10000.')
        return bound
    return None
