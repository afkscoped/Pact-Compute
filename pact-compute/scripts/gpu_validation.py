"""Independent physical CUDA output checks plus real subprocess failure cases."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.local' / 'validation' / 'browser'
REPORTS = ROOT.parent / 'reports' / 'final-validation'


def main():
    env = {**os.environ, 'PACT_STATE_DIR': str(STATE), 'PACT_DATABASE_URL': 'sqlite://',
           'PYTHONUTF8': '1', 'GROQ_API_KEY': '', 'PACT_LLM_API_KEY': ''}
    env.pop('TORCH_HOME', None)
    os.environ.update(env)
    sys.path.insert(0, str(ROOT / 'backend'))
    from pact.live import JobInput, prepared_images
    folder = STATE / 'independent-gpu-check'
    folder.mkdir(parents=True, exist_ok=True)
    inputs = prepared_images(JobInput(policy_id='local-fixture', title='Independent hardware verification', sample_count=2))
    input_path, output_path = folder / 'input.json', folder / 'output.json'
    input_path.write_bytes(inputs)
    python = ROOT / '.gpu-venv' / 'Scripts' / 'python.exe'
    task = ROOT / 'backend' / 'pact' / 'gpu_task.py'
    args = [str(python), str(task), 'execute', '--input', str(input_path), '--output', str(output_path),
            '--parent', str(os.getpid()), '--timeout', '90', '--engine', 'driver']
    run = subprocess.run(args, env=env, capture_output=True, timeout=100)
    assert run.returncode == 0, 'Physical GPU workload failed; inspect private local runtime state'
    result = json.loads(output_path.read_bytes())
    source = json.loads(inputs)
    assert result['backend'] == 'cuda' and result['engine'] == 'driver'
    assert result['dimension'] == 960 and len(result['items']) == 2
    for expected, item in zip(source['images'], result['items'], strict=True):
        assert item['sha256'] == expected['sha256'] and item['row'] == expected['row']
        assert len(item['embedding']) == 960 and all(math.isfinite(x) for x in item['embedding'])
        assert abs(sum(x * x for x in item['embedding']) - 1) < 0.001
    assert result['items'][0]['embedding'] != result['items'][1]['embedding']
    # The timeout terminates a real child process, including during model startup.
    timed = subprocess.run([*args[:args.index('--timeout')], '--timeout', '0.01', '--engine', 'driver'],
                           env=env, capture_output=True, timeout=30)
    assert timed.returncode == 124
    altered = json.loads(inputs)
    altered['images'][0]['sha256'] = '0' * 64
    input_path.write_text(json.dumps(altered), encoding='utf-8')
    invalid = subprocess.run(args, env=env, capture_output=True, timeout=60)
    assert invalid.returncode != 0 and b'Image checksum mismatch' in invalid.stderr
    negative = folder / 'invalid-model'
    weights = STATE / 'torch' / 'hub' / 'checkpoints' / 'mobilenet_v3_large-5c1a4163.pth'
    corrupt = negative / 'torch' / 'hub' / 'checkpoints' / weights.name
    corrupt.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(weights, corrupt)
    with corrupt.open('r+b') as stream:
        stream.write(b'INVALID')
    bad_model = subprocess.run([str(python), str(task), 'probe', '--engine', 'driver'],
                              env={**env, 'PACT_STATE_DIR': str(negative)}, capture_output=True, timeout=60)
    assert bad_model.returncode != 0 and b'upstream hash check' in bad_model.stderr
    report = {key: result[key] for key in ('device', 'cuda', 'torch', 'engine', 'weights_sha256', 'kernels_sha256', 'inference_seconds', 'dimension')}
    report.update(rows=2, artifact_sha256=hashlib.sha256(output_path.read_bytes()).hexdigest(),
                  input_hashes_verified=True, vectors_finite_and_unit_norm=True,
                  timeout_exit_code=timed.returncode, invalid_input_rejected=True, invalid_model_rejected=True,
                  scope='Physical CUDA Driver API execution; GPU board energy is measured separately by the browser runner workflow')
    (REPORTS / 'gpu-independent-verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('Physical GPU output, timeout, input integrity and model integrity checks passed')


if __name__ == '__main__':
    main()
