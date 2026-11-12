# RC validation evidence and commands

Run project commands from `C:\Users\nithe\Pact-Compute\pact-compute`. No command below targets the deployed database. Keep the completed milestone directory unchanged; RC drivers write to `reports/release-candidate`.

## Accepted local checks

| Check | Command | Evidence |
| --- | --- | --- |
| Affected backend/frontend regression | `.\.venv\Scripts\python.exe scripts/validate.py final --label rc-final --reports-dir ../reports/release-candidate` | `rc-final-summary.json`, `rc-final-pytest.xml`, `rc-final-*.log` |
| Browser accessibility | `.\.venv\Scripts\python.exe scripts/rc_browser.py` | `accessibility-summary.json`, `accessibility-browser.log`, `accessibility-views.json` |
| Deterministic source context | `.\.venv\Scripts\python.exe scripts/rc_package.py` | `package-manifest.json`; private/ignored `.local/release-candidate/context.tar` |
| Clean frontend from package | `.\.venv\Scripts\python.exe scripts/rc_packaging_smoke.py` | `packaging-summary.json`, `packaged-frontend.log` |
| Linux runtime smoke | `wsl.exe -d Ubuntu --cd /mnt/c/Users/nithe/Pact-Compute/pact-compute --exec .local/rc-linux-runtime/bin/python scripts/rc_linux_smoke.py` | `linux-smoke.json`, `linux-smoke.log`, `linux-installed.json` |
| Common-secret patterns | `.\.venv\Scripts\python.exe scripts/security_scan.py --output-dir ../reports/release-candidate` | `secret-scan.json`; values never emitted |
| Git whitespace | `git diff --check` from repository root | Final hygiene record |

The existing WSL Ubuntu environment was used with a project-local venv. Its 42 pinned runtime packages were installed from the recorded runtime lock; only that venv's pip was updated to 26.3. No system package, Docker service or external cloud resource was installed/created. Runtime install and pip logs are retained.

The release archive contains 82 regular allowlisted files, approved active dataset bytes, backend/migration/PTX source, frontend build inputs, runtime lock and entrypoint. Tar metadata is fixed, entrypoint line endings normalized, and repeated real archives are byte-identical. Private canaries are excluded in regression fixtures. Production application dependencies are installed separately from the GPU runner and test/audit tools. A version lock is not an artifact-hash lock; immutable image/base digests remain an image-gate requirement.

## Accessibility scope

Edge automation checks consumer Home/exchange/bookings/jobs/agreements/team; producer capacity/exchange; reviewer agreements; operator incidents; researcher research/data/explain. These are isolated role fixtures, not every populated state or every interaction. The researcher fixture reuses frozen study outputs rather than rerunning research. Pricing/FSM transition and runtime/allocation table alternatives are opened and audited. Tagged WCAG A/AA axe violations are zero in those tested views.

Keyboard testing opens the 390px drawer, verifies focus stays inside over 18 Tab presses, closes with Escape and restores opener focus. Home reflow is checked at 320px. Reduced-motion media preference is confirmed. CSS `zoom=2` at a 1280px viewport is explicitly a **proxy**, not native browser zoom or a WCAG conformance certificate.

Human acceptance still needs native Edge/Firefox 200% and 400% zoom, Windows NVDA or Narrator reading order/names/status announcements, keyboard completion of populated quote/approval/invitation/error forms, chart/table comprehension, color-independent meaning, motion behavior, focus visibility/obscuring and target-size review. Record browser/assistive-technology versions, routes, actual observations and reviewer sign-off. Automation cannot supply those observations.

## Evidence provenance

`rc-final-summary.json` binds the current regression to its captured source. Earlier `rc-summary.json` contains a build result invalidated by fatal log output; it is retained, not accepted. Corrected frontend evidence has a real successful bundle log and fresh packaged HTML/JS/CSS. `packaging-before.json`, `packaged-frontend-before.log` and `rc-frontend-build-before.log` retain adverse outcomes.

Accessibility and Linux package results refer to their own source/archive identity. Later changes confined to validation scripts do not imply a GPU/research rerun. `source-manifest.json` and the release assessment explicitly distinguish the inherited completed milestone from current checks. Six package/lock files match that milestone; reuse the dated advisory scans with their GPU coverage limitation. Never run `finalize_validation.py` to relabel historical results against new bytes.

## Actual container gate — NOT EXECUTED

When an authorized Docker engine is available, use the sanitized archive, not a workspace upload. From `pact-compute`, this cross-platform Python command avoids PowerShell binary-pipeline conversion:

```python
import subprocess
from pathlib import Path
with Path('.local/release-candidate/context.tar').open('rb') as source:
    subprocess.run(['docker', 'build', '--pull', '--tag', 'pact-compute:rc-review', '-'], stdin=source, check=True)
```

Record build log, resolved base digests, `docker image inspect pact-compute:rc-review`, package/SBOM and image vulnerability scan results. Then in an isolated local shell run:

```sh
docker run --detach --name pact-rc-review --publish 127.0.0.1:18768:8765 \
  --env PACT_DATABASE_URL=sqlite:////data/rc.db --env PACT_URL=http://127.0.0.1:18768 \
  --env PACT_SECURE_COOKIE=0 --env PACT_RUN_MIGRATIONS=1 --env PACT_RUN_IMPORT=1 \
  --env GROQ_API_KEY= --env PACT_LLM_API_KEY= pact-compute:rc-review
docker exec pact-rc-review python -m pip check
docker exec pact-rc-review python -m alembic current
docker exec pact-rc-review python -m pact.cli artifacts-verify
```

Expect `/api/health` 200/sqlite, schema `0007`, `dataset import ok`, frontend HTML and referenced assets 200, unauthenticated `/api/v1/jobs` 401. In this disposable container only, kill the worker PID via `docker exec` and verify container exit nonzero; repeat with the API. Restart cleanly, call `docker stop --time 30 pact-rc-review`, and verify graceful termination/no orphan children. Do not expose generated admin/runner credentials via `docker logs` or `cat`.

For example, the following targets the module process inside that explicitly named disposable container, without guessing a host PID:

```sh
docker exec pact-rc-review python -c "import os,signal;from pathlib import Path;pid=next(int(p.name) for p in Path('/proc').iterdir() if p.name.isdigit() and b'pact.worker' in (p/'cmdline').read_bytes().split(bytes([0])));os.kill(pid,signal.SIGKILL)"
docker wait pact-rc-review
```

Expect the wait result `1`. Start the same disposable container again and repeat selecting `pact.api:app` to test API death. These commands are prepared instructions and have not run here.

Repeat with a disposable PostgreSQL database and private test storage credentials supplied through a private env file, then exercise a real artifact round trip and container restart. The artifact hash, signature and metadata must survive. Remove only the explicitly named disposable container/volume after retaining evidence and checking no real data is attached. No container run or image scan pass is claimed here.
