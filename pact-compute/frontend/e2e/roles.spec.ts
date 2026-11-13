import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

test('consumer signup, reviewer invitation and inbox approval work across isolated sessions', async ({ page, browser, baseURL }) => {
  const suffix = Date.now().toString(36);
  const password = 'local-browser-fixture-password';
  await page.goto('/');
  const loginAudit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await page.getByLabel('Organization name').fill('Browser validation ' + suffix);
  await page.getByLabel('Username', { exact: true }).fill('consumer-' + suffix);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Explainable AI', exact: true })).toBeVisible();
  await page.goto('/#/team');
  const invitation = page.waitForResponse(response => response.url().endsWith('/api/v1/invitations') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Create invitation code' }).click();
  const { code } = await (await invitation).json();
  const reviewerContext = await browser.newContext({ baseURL });
  try {
    const reviewer = await reviewerContext.newPage();
    await reviewer.goto('/');
    await reviewer.getByRole('button', { name: 'I have an invitation code', exact: true }).click();
    await reviewer.getByLabel('Invitation code', { exact: true }).fill(code);
    await reviewer.getByLabel('Username', { exact: true }).fill('reviewer-' + suffix);
    await reviewer.getByLabel('Password', { exact: true }).fill(password);
    await reviewer.getByRole('button', { name: 'Join workspace', exact: true }).click();
    await expect(reviewer.getByRole('heading', { name: 'Agreements', exact: true })).toBeVisible();
    const draftResponse = await page.request.post('/api/v1/policies', { data: { title: 'Browser review ' + suffix,
      source: 'Jobs require at least 3 GiB VRAM.' } });
    expect(draftResponse.status()).toBe(201);
    const draft = await draftResponse.json();
    expect((await page.request.post('/api/v1/policies/' + draft.id + '/approve')).status()).toBe(403);
    await reviewer.reload();
    const card = reviewer.getByRole('article', { name: 'Review Browser review ' + suffix });
    await expect(card).toBeVisible();
    await card.getByRole('button', { name: 'Approve', exact: true }).click();
    await expect.poll(async () => (await (await page.request.get('/api/v1/policies/' + draft.id)).json()).status).toBe('approved');
    await page.goto('/#/');
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Welcome, consumer-' + suffix })).toBeVisible();
    // Keyboard skip navigation and narrow-screen layout are actual browser checks.
    await page.keyboard.press('Tab');
    await page.getByRole('button', { name: 'Skip to main content' }).focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('main')).toBeFocused();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await page.getByRole('button', { name: 'Open navigation' }).click();
    await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible();
    await page.getByRole('button', { name: 'Close navigation' }).last().click();
    const homeAudit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
    const report = { login: loginAudit.violations, consumerHome390: homeAudit.violations };
    await writeFile(path.resolve(process.env.PACT_TEST_REPORT_DIR || path.resolve('..', '..', 'reports', 'final-validation'), 'accessibility-axe.json'), JSON.stringify(report, null, 2));
    expect(report).toEqual({ login: [], consumerHome390: [] });
    await page.context().setOffline(true);
    await page.getByRole('button', { name: 'Open navigation' }).click();
    await page.getByRole('navigation', { name: 'Primary' }).getByRole('link', { name: 'GPU exchange', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Try again', exact: true }).first()).toBeVisible();
    await page.context().setOffline(false);
    const recovered = page.waitForResponse(response => response.url().includes('/api/v1/market/offers') && response.status() === 200);
    await page.getByRole('button', { name: 'Try again', exact: true }).first().click();
    await recovered;
    await expect(page.getByText('Live updates', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Try again', exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Open navigation' }).click();
    await page.getByRole('button', { name: 'Sign out' }).click();
    await expect(page.getByRole('heading', { name: 'Sign in to your workspace' })).toBeVisible();
    expect((await page.request.get('/api/v1/session')).status()).toBe(401);
  } finally { await reviewerContext.close(); }
});

test('operator explores a policy revision and resolves a stale-heartbeat fixture with evidence', async ({ page }) => {
  const state = process.env.PACT_STATE_DIR || path.resolve('..', '.local');
  const credentials = JSON.parse(await readFile(path.join(state, 'local-credentials.json'), 'utf8'));
  await page.goto('/');
  await page.getByRole('combobox', { name: 'Workspace', exact: true }).selectOption('operations');
  await page.getByLabel('Username', { exact: true }).fill('admin');
  await page.getByLabel('Password', { exact: true }).fill(credentials.admin_password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Operations overview' })).toBeVisible();
  const runner = await (await page.request.post('/api/v1/runners', { data: { name: 'Browser heartbeat fixture ' + Date.now() } })).json();
  expect((await page.request.post('/api/v1/runners/' + runner.id + '/heartbeat', {
    headers: { Authorization: 'Bearer ' + runner.token }, data: { device: 'Non-executing browser fixture', vram_mib: 0, ready: false },
  })).ok()).toBeTruthy();
  const original = await (await page.request.post('/api/v1/policies', { data: { title: 'What-if budget fixture ' + Date.now(),
    source: 'Jobs require at least 3 GiB VRAM.\nCharge must not exceed 0.01 credits.' } })).json();
  expect(original.issues).toEqual([]);
  expect((await page.request.post('/api/v1/policies/' + original.id + '/approve')).ok()).toBeTruthy();
  await page.goto('/#/jobs/new');
  await page.reload();
  await page.getByLabel('Job name').fill('What-if browser fixture');
  await page.getByLabel('Approved agreement').selectOption(original.id);
  await page.getByRole('button', { name: 'Preview placement', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'What would make this feasible?' })).toBeVisible();
  const option = page.locator('article').filter({ hasText: 'Would use' }).first();
  await expect(option).toBeVisible();
  await option.getByRole('button', { name: 'Review this change' }).click();
  await page.getByRole('button', { name: 'Accept and create a revision for review' }).click();
  await expect.poll(() => page.url().includes('#/agreements/')).toBeTruthy();
  const revisionId = page.url().split('/').at(-1)!;
  expect(revisionId).not.toBe(original.id);
  const unchanged = await (await page.request.get('/api/v1/policies/' + original.id)).json();
  expect(unchanged.rules).toEqual(original.rules);
  expect((await (await page.request.get('/api/v1/policies/' + revisionId)).json()).status).toBe('draft');
  // One deliberately non-executing runner stops sending heartbeats. Actual GPU
  // execution is verified by the separate physical workflows, not this fixture.
  await expect.poll(async () => (await (await page.request.get('/api/v1/incidents')).json())
    .some((item: { subject: { id: string } }) => item.subject.id === runner.id), { timeout: 40000 }).toBeTruthy();
  await page.goto('/#/incidents');
  const incident = page.getByRole('article', { name: 'Runner stopped reporting' }).filter({ hasText: runner.name });
  await expect(incident).toBeVisible();
  await incident.getByRole('button', { name: 'Take ownership' }).click();
  await expect(incident).toContainText('owner admin');
  await incident.getByLabel('Resolution note (recorded)').fill('Confirmed this is the non-executing browser validation fixture.');
  await incident.getByRole('button', { name: 'Record resolution' }).click();
  await expect(incident).toHaveCount(0);
  const resolved = await (await page.request.get('/api/v1/incidents?status=resolved')).json();
  expect(resolved.some((item: { subject: { id: string }; status: string }) => item.subject.id === runner.id && item.status === 'resolved')).toBeTruthy();
});
