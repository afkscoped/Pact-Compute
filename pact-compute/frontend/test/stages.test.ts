import assert from 'node:assert/strict';
import { test } from 'node:test';
import { specRows, stageRows, type Workload } from '../src/stages.ts';

test('stage rows keep canonical order and compute shares', () => {
  const rows = stageRows({ upload: 1, staging: 1, compute: 2 });
  assert.deepEqual(rows.map(row => row.key), ['staging', 'compute', 'upload']);
  assert.equal(rows[1].share, 0.5);
});
test('missing or empty timings yield no rows', () => {
  assert.deepEqual(stageRows(null), []);
  assert.deepEqual(stageRows({}), []);
  assert.equal(stageRows({ compute: 0 })[0].share, 0);
});
const spec: Workload = {
  version: 1, template_id: 'image-embeddings-v1', spec_sha256: 'f'.repeat(64),
  runtime: { kind: 'native-runner', task_sha256: 'a'.repeat(64), kernels_sha256: 'b'.repeat(64) },
  model: { name: 'M', weights_sha256: null, digest_status: 'unpinned: the runner verifies the upstream hash' },
  input_manifest: { artifact_id: null, sha256: null, rows: 4, format: 'png-base64-manifest' },
  hardware: { min_vram_mib: 4096, gpu_count: 1, backend: 'cuda', gpu_model: null },
  region: null, timeout_s: 90, output_schema: { name: 'image-embeddings-v1', rows: 4, dimension: 960 },
  retry: { max_attempts: 1, automatic_retry: false, manual_resubmit: true },
};
test('spec rows describe every required field plainly', () => {
  const rows = Object.fromEntries(specRows(spec));
  assert.match(rows['Input manifest'], /not recorded/);
  assert.match(rows['Model'], /unpinned/);
  assert.equal(rows['Timeout'], '90 s');
  assert.match(rows['Retries'], /no automatic retry/);
  assert.equal(Object.keys(rows).length, 9);
});
