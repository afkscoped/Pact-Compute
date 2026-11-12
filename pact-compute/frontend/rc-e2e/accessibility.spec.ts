import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const state = process.env.PACT_RC_STATE_DIR!;
const reports = path.resolve('..', '..', 'reports', 'release-candidate');
async function login(page: Page, role: string) {
  const roles = JSON.parse(await readFile(path.join(state, 'rc-roles.json'), 'utf8'));
  const account = role === 'admin' ? { username: 'admin', password: JSON.parse(await readFile(path.join(state, 'local-credentials.json'), 'utf8')).admin_password } : roles[role];
  const response = await page.request.post('/api/v1/session', { data: account });
  expect(response.status()).toBe(200);
  await page.goto('/');
  await expect(page.locator('main h1')).toBeVisible();
}

test('mobile navigation keeps keyboard focus inside and returns it on Escape', async ({ page }) => {
  await login(page, 'consumer');
  await page.setViewportSize({ width: 390, height: 844 });
  const opener = page.getByRole('button', { name: 'Open navigation' });
  await opener.focus();
  await page.keyboard.press('Enter');
  const panel = page.locator('aside.sidebar');
  await expect.poll(() => panel.evaluate(node => node.contains(document.activeElement))).toBeTruthy();
  for (let i = 0; i < 18; i++) {
    await page.keyboard.press('Tab');
    expect(await panel.evaluate(node => node.contains(document.activeElement))).toBe(true);
  }
  await page.keyboard.press('Escape');
  await expect(page.getByRole('navigation', { name: 'Primary' })).toBeHidden();
  await expect(opener).toBeFocused();
});

test('role screens, 320px reflow and chart alternatives have automated accessibility evidence', async ({ page }) => {
  const results: Record<string, unknown> = {};
  const views: Record<string, string[]> = {
    consumer: ['/', '/market', '/bookings', '/jobs', '/agreements', '/team'],
    producer: ['/capacity', '/market'], reviewer: ['/agreements'],
    operator: ['/incidents'], researcher: ['/research', '/data', '/explain'],
  };
  try {
    for (const [role, routes] of Object.entries(views)) {
      await login(page, role);
      for (const route of routes) {
        await page.goto('/#' + route);
        await expect(page.locator('main h1')).toBeVisible();
        await expect(page.getByText('Loading workspace…', { exact: true })).toHaveCount(0);
        await expect(page.getByRole('status').filter({ hasText: /Loading/ })).toHaveCount(0);
        const audit = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
        results[role + route] = audit.violations;
        expect(audit.violations.map(item => ({ id: item.id, impact: item.impact, targets: item.nodes.map(node => node.target) }))).toEqual([]);
        if (route === '/explain') {
          await expect(page.getByText('Publication comparisons', { exact: true })).toBeVisible();
          await page.getByRole('button', { name: 'Pricing and FSM', exact: true }).click();
          const transitions = page.getByText('Accessible transition table', { exact: true });
          await transitions.focus();
          await page.keyboard.press('Enter');
          await expect(page.getByRole('columnheader', { name: 'Support', exact: true })).toBeVisible();
          results.pricingCharts = (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze()).violations;
          expect(results.pricingCharts).toEqual([]);
          await page.getByRole('button', { name: 'Runtime and allocation', exact: true }).click();
          await expect(page.getByRole('heading', { name: 'Held-out runtime estimates', exact: true })).toBeVisible();
          await expect(page.getByRole('columnheader', { name: 'Wait p95 (min)', exact: true })).toBeVisible();
          results.runtimeCharts = (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze()).violations;
          expect(results.runtimeCharts).toEqual([]);
        }
      }
      await page.request.delete('/api/v1/session');
    }
    await login(page, 'consumer');
    await page.setViewportSize({ width: 320, height: 800 });
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    // This is an explicit narrow-layout check, not an assertion about native browser zoom.
    results.reflow320 = { documentWidth: await page.evaluate(() => document.documentElement.scrollWidth), viewport: 320 };
    await page.emulateMedia({ reducedMotion: 'reduce' });
    results.reducedMotion = await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
    await page.setViewportSize({ width: 1280, height: 1000 });
    await page.locator('html').evaluate(node => { node.style.zoom = '2'; });
    results.cssZoom200 = { kind: 'CSS zoom reflow proxy, not native browser zoom',
      documentWidth: await page.evaluate(() => document.documentElement.scrollWidth),
      viewport: 1280 };
    await expect(page.getByRole('heading', { name: /Welcome/ })).toBeVisible();
  } finally {
    await writeFile(path.join(reports, 'accessibility-views.json'), JSON.stringify(results, null, 2));
  }
});
