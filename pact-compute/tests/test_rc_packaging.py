import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location('rc_package', Path(__file__).parents[1] / 'scripts/rc_package.py')
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)


def fixture(root):
    for name in rc.REQUIRED:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('packaging unit fixture\n')
    manifest = []
    for name in rc.DATA:
        data = ('unit packaging fixture ' + name).encode()
        (root / 'PACT-Compute-data-preflight' / name).write_bytes(data)
        manifest.append({'file': name, 'sha256': hashlib.sha256(data).hexdigest()})
    (root / rc.REQUIRED[-1]).write_text(json.dumps(manifest))
    for name in ('pact-compute/backend/pact/api.py', 'pact-compute/frontend/src/main.tsx'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('source fixture\n')


def test_context_is_deterministic_and_excludes_secrets_and_generated_files(tmp_path):
    fixture(tmp_path)
    forbidden = ('env', 'deploy.env', '.env.local', 'reports/private.json',
                 'pact-compute/.gpu-venv/credentials.json', 'pact-compute/frontend/node_modules/library.js',
                 'pact-compute/backend/pact/.env', 'pact-compute/backend/pact/local-credentials.json')
    for name in forbidden:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('packaging canary; not a real secret')
    first = rc.package(tmp_path, tmp_path / 'one.tar')
    second = rc.package(tmp_path, tmp_path / 'two.tar')
    assert first == second
    with tarfile.open(tmp_path / 'one.tar') as archive:
        names = archive.getnames()
        assert not set(forbidden) & set(names)
        assert all(archive.getmember(name).isfile() for name in names)
    assert len(first['members']) == len(rc.REQUIRED) + len(rc.DATA) + 2


def test_context_refuses_changed_dataset_and_missing_required_file(tmp_path):
    fixture(tmp_path)
    (tmp_path / 'Dockerfile').unlink()
    with pytest.raises(ValueError, match='Invalid release input'):
        rc.package(tmp_path, tmp_path / 'missing.tar')
    (tmp_path / 'Dockerfile').write_text('fixture')
    (tmp_path / 'PACT-Compute-data-preflight' / rc.DATA[0]).write_text('tampered fixture')
    with pytest.raises(ValueError, match='Unapproved dataset'):
        rc.package(tmp_path, tmp_path / 'tampered.tar')
