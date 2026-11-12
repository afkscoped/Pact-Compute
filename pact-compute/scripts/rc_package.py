"""Create a deterministic Docker context from explicit source inputs, never a workspace dump."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

REPO = Path(__file__).resolve().parents[2]
REQUIRED = ('Dockerfile', '.dockerignore', 'deploy/entrypoint.sh', 'pact-compute/alembic.ini',
            'pact-compute/requirements-runtime-py312.lock.txt', 'pact-compute/frontend/package.json',
            'pact-compute/frontend/package-lock.json', 'pact-compute/frontend/tsconfig.json',
            'pact-compute/frontend/build.mjs', 'pact-compute/frontend/index.html',
            'PACT-Compute-data-preflight/download-manifest.json')
DATA = ('openb_pod_list_default.csv', 'openb_pod_list_gpuspec33.csv',
        'openb_node_list_gpu_node.csv', 'neso_gb_2025-10-01_to_2025-10-29.json')


def inputs(root):
    selected = set(REQUIRED)
    for prefix, suffixes in [('pact-compute/backend', {'.py', '.ptx', '.mako'}),
                             ('pact-compute/frontend/src', {'.ts', '.tsx', '.css'})]:
        for path in (root / prefix).rglob('*'):
            if path.is_file() and path.suffix in suffixes and not any(part.startswith('.') for part in path.relative_to(root).parts):
                selected.add(path.relative_to(root).as_posix())
    manifest = json.loads((root / REQUIRED[-1]).read_text(encoding='utf-8-sig'))
    expected = {row['file']: row['sha256'] for row in manifest}
    for name in DATA:
        relative = 'PACT-Compute-data-preflight/' + name
        content = (root / relative).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected[name]:
            raise ValueError(f'Unapproved dataset bytes: {name}')
        selected.add(relative)
    return sorted(selected)


def package(root, target):
    root, target = root.resolve(), target.resolve()
    rows = []
    target.parent.mkdir(parents=True, exist_ok=True)
    # Validate every member before writing; a path or source error must not
    # silently leave a partial artifact described as a successful package.
    members = []
    for name in inputs(root):
        path = root / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError(f'Invalid release input: {name}')
        if any(parent.is_symlink() for parent in path.parents if parent != root and parent.is_relative_to(root)):
            raise ValueError(f'Symlinked release input: {name}')
        data = path.read_bytes()
        if name == 'deploy/entrypoint.sh':
            data = data.replace(b'\r\n', b'\n')
        members.append((name, data))
    staging = target.with_suffix(target.suffix + '.part')
    try:
        with tarfile.open(staging, 'w', format=tarfile.PAX_FORMAT) as archive:
            for name, data in members:
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                entry.mode = 0o755 if name == 'deploy/entrypoint.sh' else 0o644
                entry.mtime = 0
                archive.addfile(entry, io.BytesIO(data))
                rows.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        staging.replace(target)
    finally:
        staging.unlink(missing_ok=True)
    return {'format': 'allowlisted-docker-context-v1', 'archive_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'archive_bytes': target.stat().st_size, 'members': rows,
            'scope': 'Exact build inputs only. No image build or hosted deployment implied.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=REPO / 'pact-compute/.local/release-candidate/context.tar')
    args = parser.parse_args()
    report = package(REPO, args.output)
    reports = REPO / 'reports/release-candidate'
    reports.mkdir(parents=True, exist_ok=True)
    (reports / 'package-manifest.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Packaged {len(report["members"])} allowlisted inputs, SHA-256 {report["archive_sha256"]}')


if __name__ == '__main__':
    main()
