"""Content provenance for local validation, excluding private and generated state."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PREFIXES = ('pact-compute/backend/', 'pact-compute/frontend/src/', 'pact-compute/frontend/e2e/',
            'pact-compute/frontend/test/', 'pact-compute/frontend/rc-e2e/', 'pact-compute/scripts/', 'pact-compute/tests/', '.github/workflows/')


def capture():
    names = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    files = {}
    for name in sorted(set(names)):
        if name.startswith(PREFIXES) or name in {'Dockerfile', '.dockerignore', '.gitignore', '.gitattributes', 'deploy/entrypoint.sh',
            'pact-compute/pytest.ini', 'pact-compute/alembic.ini', 'pact-compute/frontend/package.json',
            'pact-compute/frontend/package-lock.json', 'pact-compute/frontend/tsconfig.json',
            'pact-compute/frontend/build.mjs', 'pact-compute/frontend/playwright.config.ts',
            'pact-compute/frontend/playwright.rc.config.ts'} or name.startswith('pact-compute/requirements'):
            path = ROOT / name
            if path.is_file():
                files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'fingerprint': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(), 'files': files}
