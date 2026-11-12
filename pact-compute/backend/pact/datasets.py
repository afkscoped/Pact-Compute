import csv
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from .config import DATA, STATE
from .db import sha, uid


PODS = 'openb_pod_list_gpuspec33.csv'
DEFAULT = 'openb_pod_list_default.csv'
NODES = 'openb_node_list_gpu_node.csv'
CARBON = 'neso_gb_2025-10-01_to_2025-10-29.json'
SCHEMA = 'pact-dataset-1'


def write_atomic(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix('.' + uid() + '.tmp')
    staged.write_bytes(data)
    staged.replace(path)


def read_manifest():
    path = DATA / 'download-manifest.json'
    return json.loads(path.read_text(encoding='utf-8-sig'))


def source_index():
    manifest = read_manifest()
    return {item['file']: item for item in manifest if item['status'] == 'downloaded'}


def verified_file(index, name):
    entry = index[name]
    data = (DATA / name).read_bytes()
    if sha(data) != entry['sha256']:
        raise ValueError(f'Source checksum changed for {name}.')
    return data


def number(row, name):
    value = row.get(name)
    return int(value) if value and value.strip() else None


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return int(parsed.astimezone(timezone.utc).timestamp())


def csv_rows(data):
    return csv.DictReader(data.decode('utf-8-sig').splitlines())


def normalize(index):
    import pyarrow as pa
    import pyarrow.parquet as pq

    raw = {name: verified_file(index, name) for name in (PODS, DEFAULT, NODES, CARBON)}
    fingerprint = sha(json.dumps({'schema': SCHEMA, 'inputs': {name: sha(content) for name, content in raw.items()}}, sort_keys=True))
    root = STATE / 'datasets' / fingerprint
    card_file = root / 'card.json'
    if card_file.exists() and all((root / name).is_file() for name in ('pods.parquet', 'nodes.parquet', 'carbon.parquet')):
        return json.loads(card_file.read_bytes())
    defaults = {r['name'] for r in csv_rows(raw[DEFAULT])}
    nodes = [
        {'source_id': row['sn'], 'gpu_count': int(row['gpu']), 'host_ram_mib': int(row['memory_mib']),
         'cpu_milli': int(row['cpu_milli']), 'gpu_model': row['model']}
        for row in csv_rows(raw[NODES])
    ]
    pods = []
    quarantined = []
    seen = set()
    for row in csv_rows(raw[PODS]):
        row_id = row['name']
        if row_id not in defaults or row_id in seen:
            raise ValueError(f'Pod variant does not match primary trace identity for {row_id}.')
        seen.add(row_id)
        gpu, fraction = number(row, 'num_gpu'), number(row, 'gpu_milli')
        arrived, started, deleted = (number(row, name) for name in ('creation_time', 'scheduled_time', 'deletion_time'))
        if arrived is None or arrived < 0 or gpu is None or not 0 <= gpu <= 8 or fraction is None or not 0 <= fraction <= 1000:
            quarantined.append(row_id)
            continue
        valid_times = started is not None and deleted is not None and arrived <= started < deleted
        proxy = deleted - started if row['pod_phase'] == 'Succeeded' and valid_times else None
        pods.append({'source_id': row_id, 'arrival_relative_s': arrived, 'scheduled_relative_s': started,
                     'deleted_relative_s': deleted, 'phase': row['pod_phase'], 'qos': row['qos'],
                     'gpu_count': gpu, 'gpu_milli': fraction, 'gpu_models': row['gpu_spec'].split('|') if row['gpu_spec'] else [],
                     'host_ram_mib': number(row, 'memory_mib'), 'cpu_milli': number(row, 'cpu_milli'),
                     'runtime_proxy_s': proxy, 'runtime_source': 'successful_lifecycle_proxy' if proxy else 'unobserved'})
    if seen != defaults:
        raise ValueError('The two pod files cover different source IDs.')
    begin, finish = timestamp('2025-10-01T00:00Z'), timestamp('2025-10-29T00:00Z')
    carbon = []
    for row in json.loads(raw[CARBON])['data']:
        start, end = timestamp(row['from']), timestamp(row['to'])
        if not begin <= start < finish:
            continue
        if end - start != 1800 or (carbon and start != carbon[-1]['end']) or start != begin + len(carbon) * 1800:
            raise ValueError('The GB carbon snapshot has a gap or invalid interval.')
        observed = row['intensity']['actual']
        if observed is None or not 0 <= observed <= 2000:
            raise ValueError('The GB carbon snapshot has a missing or out-of-range actual value.')
        carbon.append({'start': start, 'end': end, 'zone': 'GB', 'actual_g_per_kwh': observed,
                       'published_forecast': row['intensity']['forecast'], 'unit': 'gCO2/kWh'})
    if not carbon or carbon[-1]['end'] != finish:
        raise ValueError('The GB carbon snapshot ends outside the declared window.')
    root.mkdir(parents=True, exist_ok=True)
    for name, rows in (('pods', pods), ('nodes', nodes), ('carbon', carbon)):
        table_path = root / f'{name}.parquet'
        staging = table_path.with_suffix('.' + uid() + '.tmp')
        pq.write_table(pa.Table.from_pylist(rows), staging, compression='zstd')
        staging.replace(table_path)
    card = {
        'id': fingerprint, 'schema': SCHEMA, 'pods': len(pods), 'gpu_pods': sum(row['gpu_count'] > 0 for row in pods),
        'gpu_nodes': len(nodes), 'gpu_devices': sum(row['gpu_count'] for row in nodes),
        'runtime_proxies': sum(bool(row['runtime_proxy_s']) and row['gpu_count'] > 0 for row in pods),
        'carbon_intervals': len(carbon), 'carbon_zone': 'GB', 'carbon_unit': 'gCO2/kWh',
        'carbon_range': [carbon[0]['start'], carbon[-1]['end']],
        'quarantined': quarantined, 'sources': [index[name] for name in raw],
        'origins': {'arrivals': 'Alibaba production pod trace', 'runtime': 'modeled from earlier successful lifecycle proxies',
                    'grid': 'NESO historical published actual series', 'market': 'configured scenario inputs'},
    }
    write_atomic(card_file, json.dumps(card, indent=2).encode())
    return card


def import_sources():
    return normalize(source_index())


@lru_cache(maxsize=4)
def read_snapshot(snapshot_id: str):
    import pyarrow.parquet as pq

    if len(snapshot_id) != 64 or any(c not in 'abcdef0123456789' for c in snapshot_id):
        raise ValueError('Invalid snapshot identifier.')
    root = STATE / 'datasets' / snapshot_id
    card = json.loads((root / 'card.json').read_bytes())
    return card, *(pq.read_table(root / f'{name}.parquet').to_pylist() for name in ('pods', 'nodes', 'carbon'))


def available():
    root = STATE / 'datasets'
    return [json.loads(path.read_bytes()) for path in sorted(root.glob('*/card.json'))]
