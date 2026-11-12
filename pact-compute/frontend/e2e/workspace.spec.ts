import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { expect, test } from '@playwright/test';

test('approves an agreement, executes a real GPU job, and runs the trace benchmark', async ({ page }) => {
  const workspace = path.resolve('..', '.local');
  const credentials = JSON.parse(await readFile(path.join(workspace, 'local-credentials.json'), 'utf8'));
  const evidence = path.join(workspace, 'verified');
  await mkdir(evidence, { recursive: true });
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByLabel('Password', { exact: true }).fill(credentials.admin_password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Operations overview' })).toBeVisible();
  await expect(page.getByText('GPU connected', { exact: true })).toBeVisible({ timeout: 75_000 });
  await page.getByRole('link', { name: 'Agreements', exact: true }).click();
  await page.getByRole('button', { name: 'Load example' }).click();
  await page.getByRole('button', { name: 'Extract rules' }).click();
  await expect(page.getByText('6 source-linked rules')).toBeVisible();
  await page.getByRole('button', { name: 'Approve policy' }).click();
  await expect(page.getByText('Approved', { exact: true })).toBeVisible();
  const policyId = page.url().split('/').at(-1)!;
  await page.getByRole('link', { name: 'Submit a job' }).click();
  await page.getByLabel('Job name').fill('Live GPU verification');
  await page.getByLabel('Approved agreement').selectOption(policyId);
  await page.getByRole('button', { name: 'Preview placement' }).click();
  await expect(page.getByText('An eligible reservation is available.')).toBeVisible();
  await page.getByRole('button', { name: 'Submit live job' }).click();
  await expect(page.getByRole('heading', { name: 'Live GPU verification' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Output', exact: true })).toBeVisible({ timeout: 90_000 });
  await expect(page.getByRole('heading', { name: 'Policy audit' })).toBeVisible();
  const jobId = page.url().split('/').at(-1)!;
  const job = await (await page.request.get('/api/v1/jobs/' + jobId)).json();
  expect(job.status).toBe('succeeded');
  expect(job.findings.filter((entry: { status: string }) => entry.status === 'fail')).toEqual([]);
  const result = job.attempts[0].result;
  const output = await page.request.get('/api/v1/artifacts/' + result.artifact_id);
  const bytes = await output.body();
  const manifest = JSON.parse(bytes.toString('utf8'));
  expect(createHash('sha256').update(bytes).digest('hex')).toBe(result.sha256);
  expect(manifest.backend).toBe('cuda');
  expect(manifest.items).toHaveLength(4);
  expect(manifest.items.every((item: { embedding: number[] }) => item.embedding.length === 960)).toBe(true);
  expect(manifest.items[0].embedding).not.toEqual(manifest.items[1].embedding);
  await writeFile(path.join(evidence, 'image-embeddings.json'), bytes);
  await writeFile(path.join(evidence, 'gpu-job-evidence.json'), await (await page.request.get('/api/v1/jobs/' + jobId + '/evidence.json')).body());
  await page.screenshot({ path: path.join(evidence, 'gpu-job.png'), fullPage: true });

  await page.getByRole('link', { name: 'Agreements', exact: true }).click();
  await page.getByLabel('Agreement name').fill('Infeasible GPU memory');
  await page.getByLabel('Service agreement').fill('Jobs require at least 32 GiB VRAM.');
  await page.getByRole('button', { name: 'Extract rules' }).click();
  await page.getByRole('button', { name: 'Approve policy' }).click();
  await expect(page.getByText('Approved', { exact: true })).toBeVisible();
  const badPolicy = page.url().split('/').at(-1)!;
  await page.getByRole('link', { name: 'Submit a job' }).click();
  await page.getByLabel('Job name').fill('Rejected memory verification');
  await page.getByLabel('Approved agreement').selectOption(badPolicy);
  await page.getByRole('button', { name: 'Preview placement' }).click();
  await expect(page.getByText('No runner satisfies the current policy and inventory.')).toBeVisible();
  await page.getByRole('button', { name: 'Record rejected request' }).click();
  await expect(page.getByRole('heading', { name: 'Rejected memory verification' })).toBeVisible();
  await expect(page.getByText('Minimum GPU memory (MiB)', { exact: true }).last()).toBeVisible();

  await page.getByRole('link', { name: 'Research Lab', exact: true }).click();
  await page.getByLabel('Run name').fill('Verified Alibaba and NESO replay');
  await page.getByLabel('GPU jobs per seed').fill('45');
  await page.getByLabel('Paired seeds').fill('1');
  await page.getByRole('button', { name: 'Run experiment' }).click();
  await expect(page.getByRole('heading', { name: 'Scheduler comparison' })).toBeVisible({ timeout: 90_000 });
  await expect(page.getByRole('heading', { name: 'Provider strategy audit' })).toBeVisible();
  const runId = page.url().split('/').at(-1)!;
  const replay = await (await page.request.get('/api/v1/runs/' + runId)).json();
  expect(replay.status).toBe('completed');
  expect(Object.keys(replay.result.summary)).toHaveLength(5);
  expect(replay.result.summary.carbon_aware.completed).toBeGreaterThan(0);
  await writeFile(path.join(evidence, 'research-metrics.csv'), await (await page.request.get('/api/v1/runs/' + runId + '/metrics.csv')).body());
  await writeFile(path.join(evidence, 'research-evidence.json'), await (await page.request.get('/api/v1/artifacts/' + replay.artifact_id)).body());
  await page.screenshot({ path: path.join(evidence, 'research.png'), fullPage: true });
  await page.getByRole('link', { name: 'Overview', exact: true }).click();
  await page.screenshot({ path: path.join(evidence, 'overview.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('button', { name: 'Open navigation' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Primary' })).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({ path: path.join(evidence, 'mobile.png'), fullPage: true });
  expect(errors).toEqual([]);
  await writeFile(path.join(evidence, 'verification.json'), JSON.stringify({
    job_id: jobId, run_id: runId, artifact_sha256: result.sha256, rows: manifest.items.length,
    dimension: manifest.dimension, engine: manifest.engine, device: manifest.device, gpu_inference_seconds: manifest.inference_seconds,
    gpu_energy_kwh: result.gpu_energy_kwh, telemetry_coverage: result.telemetry_coverage,
    findings: job.findings.map((finding: { id: string; status: string }) => ({ id: finding.id, status: finding.status })),
    replay: replay.result.summary,
  }, null, 2));
});
