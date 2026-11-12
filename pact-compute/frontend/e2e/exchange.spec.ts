import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';

test('producer and consumers share a live booking and inspect its protocol', async ({ browser, baseURL }) => {
  const state = process.env.PACT_STATE_DIR || path.resolve('..', '.local');
  const passwords = JSON.parse(await readFile(path.join(state, 'market-credentials.json'), 'utf8'));
  const contexts = await Promise.all([1, 2, 3].map(() => browser.newContext({ baseURL })));
  const [producer, consumer, rival] = await Promise.all(contexts.map(context => context.newPage()));
  const errors: string[] = [];
  for (const page of [producer, consumer, rival]) page.on('pageerror', error => errors.push(error.message));
  async function signIn(page: Page, role: 'producer' | 'consumer', username: string) {
    await page.goto('/');
    await page.getByRole('combobox', { name: 'Workspace', exact: true }).selectOption(role);
    await page.getByLabel('Username', { exact: true }).fill(username);
    await page.getByLabel('Password', { exact: true }).fill(passwords[username]);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page.getByRole('heading', { name: role === 'producer' ? 'Producer exchange' : 'Welcome, ' + username, exact: true })).toBeVisible();
    if (role === 'consumer') await page.goto('/#/market');
  }
  try {
    await Promise.all([signIn(producer, 'producer', 'demo-producer'), signIn(consumer, 'consumer', 'demo-consumer'),
      signIn(rival, 'consumer', 'demo-consumer-2')]);
    const policies = new Map<Page, string>();
    if (process.env.PACT_TEST_VRAM_GIB) {
      for (const [buyer, username] of [[consumer, 'demo-reviewer'], [rival, 'demo-reviewer-2']] as const) {
        const reviewer = await browser.newContext({ baseURL });
        const login = await reviewer.request.post('/api/v1/session', { data: { username, password: passwords[username] } });
        expect(login.ok()).toBeTruthy();
        const config = await (await reviewer.request.get('/api/v1/config')).json();
        const draft = await (await reviewer.request.post('/api/v1/policies', { data: { title: 'Verified local GPU policy',
          source: config.example_contract.replace('4 GiB', process.env.PACT_TEST_VRAM_GIB + ' GiB') } })).json();
        expect((await reviewer.request.post('/api/v1/policies/' + draft.id + '/approve')).ok()).toBeTruthy();
        policies.set(buyer, draft.id);
        await reviewer.close();
      }
      await Promise.all([consumer.reload(), rival.reload()]);
    }
    await expect(producer.getByText('GPU connected', { exact: true })).toBeVisible({ timeout: 75_000 });
    await expect(consumer.getByText('Live updates', { exact: true })).toBeVisible();
    const offer = 'Shared RTX slot ' + Date.now();
    await producer.getByRole('button', { name: 'Publish capacity', exact: true }).click();
    await producer.getByLabel('Offer name').fill(offer);
    await producer.getByRole('button', { name: 'Publish offer', exact: true }).click();
    const requestQuote = async (page: Page) => {
      const listing = page.locator('article').filter({ hasText: offer });
      await expect(listing).toBeVisible();
      await listing.getByRole('button', { name: 'Request quote for ' + offer, exact: true }).click();
      if (policies.has(page)) await page.getByRole('combobox', { name: /^Agreement/ }).selectOption(policies.get(page)!);
      await page.getByRole('button', { name: 'Get quote', exact: true }).click();
      await expect(page.getByRole('button', { name: 'Confirm reservation', exact: true })).toBeEnabled();
    };
    await Promise.all([requestQuote(consumer), requestQuote(rival)]);
    await Promise.all([consumer, rival].map(page => page.getByRole('button', { name: 'Confirm reservation', exact: true }).click()));
    await expect.poll(() => [consumer.url(), rival.url()].filter(url => url.includes('#/bookings/')).length,
      { timeout: 20000 }).toBe(1);
    const winner = consumer.url().includes('#/bookings/') ? consumer : rival;
    const loser = winner === consumer ? rival : consumer;
    await expect(loser.getByRole('alert')).toContainText('quoted slot or terms changed');
    const id = winner.url().split('/').at(-1)!;
    await producer.getByRole('link', { name: 'Bookings', exact: true }).click();
    const row = producer.locator('tr').filter({ hasText: offer });
    await expect(row).toBeVisible();
    await row.getByRole('link').click();
    await expect(producer.getByText('Succeeded', { exact: true })).toBeVisible({ timeout: 90_000 });
    await expect(winner.getByText('Succeeded', { exact: true })).toBeVisible();
    await expect(winner.getByText('Pass', { exact: true }).first()).toBeVisible();
    const endpoint = '/api/v1/market/bookings/' + id;
    expect((await loser.request.get(endpoint)).status()).toBe(404);
    const [producerReceipt, consumerReceipt] = await Promise.all([producer, winner].map(async page => (await page.request.get(endpoint + '/receipt')).json()));
    expect(producerReceipt).toEqual(consumerReceipt);
    expect(consumerReceipt.manifest.booking.protocol.verdict).toBe('pass');
    expect(consumerReceipt.manifest.booking.artifact_sha256).toMatch(/^[a-f0-9]{64}$/);
    const booking = await (await winner.request.get(endpoint)).json();
    expect((await producer.request.get('/api/v1/jobs/' + booking.job_id)).status()).toBe(404);
    await winner.getByRole('link', { name: 'Explain', exact: true }).click();
    await expect(winner.getByRole('heading', { name: 'Explainable AI', exact: true })).toBeVisible();
    await expect(winner.getByText('Publication comparisons', { exact: true })).toBeVisible({ timeout: 15000 });
    await winner.getByRole('button', { name: 'Pricing and FSM', exact: true }).click();
    await expect(winner.getByRole('heading', { name: 'Learned pricing states' })).toBeVisible();
    await winner.getByRole('button', { name: 'Runtime and allocation', exact: true }).click();
    await expect(winner.getByRole('heading', { name: 'Held-out runtime estimates' })).toBeVisible();
    const evidence = path.join(state, 'verified');
    await mkdir(evidence, { recursive: true });
    await writeFile(path.join(evidence, 'market-receipt.json'), JSON.stringify(consumerReceipt, null, 2));
    await producer.screenshot({ path: path.join(evidence, 'market-producer.png'), fullPage: true });
    await winner.screenshot({ path: path.join(evidence, 'explainable-ai.png'), fullPage: true });
    await winner.setViewportSize({ width: 390, height: 844 });
    await expect.poll(() => winner.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
    await winner.screenshot({ path: path.join(evidence, 'explainable-ai-mobile.png'), fullPage: true });
    expect(errors).toEqual([]);
  } finally {
    await Promise.all(contexts.map(context => context.close()));
  }
});
