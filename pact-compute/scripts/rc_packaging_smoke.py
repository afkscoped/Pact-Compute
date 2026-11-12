"""Clean frontend install/build using only the deterministic release context."""
import json
import os
from pathlib import Path
import subprocess
import tarfile
import uuid

from rc_package import REPO, package
from validation_manifest import capture


def main():
    project = REPO / 'pact-compute'
    reports = REPO / 'reports/release-candidate'
    archive = project / '.local/release-candidate/context.tar'
    before = capture()
    first = json.loads((reports / 'package-manifest.json').read_text())
    second = package(REPO, archive.with_name('context-repeat.tar'))
    assert first == second and archive.read_bytes() == archive.with_name('context-repeat.tar').read_bytes()
    source = project / '.local' / ('rc-clean-frontend-' + uuid.uuid4().hex[:8])
    with tarfile.open(archive) as bundle:
        bundle.extractall(source, filter='data')
    cache = project / '.local/rc-npm-cache'
    cache.mkdir(parents=True, exist_ok=True)
    userconfig = cache / 'empty.npmrc'
    userconfig.write_text('', encoding='utf-8')
    env = {**os.environ, 'NPM_TOKEN': '', 'NODE_AUTH_TOKEN': '', 'npm_config_cache': str(cache),
           'npm_config_userconfig': str(userconfig), 'npm_config_registry': 'https://registry.npmjs.org/'}
    npm = 'npm.cmd' if os.name == 'nt' else 'npm'
    checks = []
    with (reports / 'packaged-frontend.log').open('wb') as log:
        for command in ([npm, 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], [npm, 'run', 'build']):
            result = subprocess.run(command, cwd=source / 'pact-compute/frontend', env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log.write(result.stdout)
            fatal = b"Unhandled 'error' event" in result.stdout or b'FATAL ERROR:' in result.stdout
            checks.append({'command': command, 'exit_code': result.returncode or int(fatal),
                           'process_exit_code': result.returncode, 'fatal_output_detected': fatal})
            if checks[-1]['exit_code']:
                break
    dist = source / 'pact-compute/frontend/dist'
    generated = sorted(p.relative_to(dist).as_posix() for p in dist.rglob('*') if p.is_file())
    report = {'archive_sha256': first['archive_sha256'], 'deterministic_repeat_identical': True,
              'members': len(first['members']), 'archive_bytes': first['archive_bytes'], 'checks': checks,
              'fresh_build_files': generated, 'source': before, 'source_unchanged': before == capture(),
              'scope': 'Clean npm install/build from allowlisted archive on this OS. No OCI image build.'}
    (reports / 'packaging-summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    passed = all(not row['exit_code'] for row in checks) and 'index.html' in generated and before == capture()
    print('Clean packaged frontend:', 'PASS' if passed else 'FAIL')
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
