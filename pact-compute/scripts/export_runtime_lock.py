"""Freeze the installed runtime/S3 dependency closure, excluding test/audit tools."""
from importlib import metadata
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def main():
    pending = []
    for name in ('requirements.txt', 'requirements-s3.txt'):
        for line in (ROOT / name).read_text().splitlines():
            if line.strip() and not line.startswith('#'):
                pending.append(Requirement(line).name)
    selected = {}
    environment = {**default_environment(), 'extra': ''}
    while pending:
        name = canonicalize_name(pending.pop())
        if name in selected:
            continue
        distribution = metadata.distribution(name)
        selected[name] = distribution.version
        for line in distribution.requires or []:
            requirement = Requirement(line)
            if requirement.marker is None or requirement.marker.evaluate(environment):
                pending.append(requirement.name)
    text = '# Resolved runtime/S3 closure on CPython 3.12; image build still requires Linux verification.\n'
    text += '\n'.join(f'{name}=={version}' for name, version in sorted(selected.items())) + '\n'
    (ROOT / 'requirements-runtime-py312.lock.txt').write_text(text, encoding='utf-8')
    print(f'Frozen {len(selected)} runtime distributions (no pytest, moto or audit tools)')


if __name__ == '__main__':
    main()
