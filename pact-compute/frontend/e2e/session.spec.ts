import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { expect, test } from '@playwright/test';

test('demo launch resets the active session and sign out fits on a short screen', async ({ page }) => {
  const state = process.env.PACT_STATE_DIR || path.resolve('..', '.local');
  const credentials = JSON.parse(await readFile(path.join(state, 'local-credentials.json'), 'utf8'));
  await page.setViewportSize({ width: 1024, height: 540 });
  const login = page.getByRole('heading', { name: 'Sign in to your workspace' });
  const workspace = page.getByRole('combobox', { name: 'Workspace', exact: true });
  const username = page.getByLabel('Username', { exact: true });
  const password = page.getByLabel('Password', { exact: true });
  const overview = page.getByRole('heading', { name: 'Operations overview' });

  await page.goto('/');
  await workspace.selectOption('operations');
  await username.fill('admin');
  await password.fill(credentials.admin_password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(overview).toBeVisible();

  await page.goto('/?start=sign-in');
  await expect(login).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
  await expect(workspace).toHaveValue('');
  await expect(username).toHaveValue('');
  await expect(password).toHaveValue('');
  expect((await page.request.get('/api/v1/session')).status()).toBe(401);

  await workspace.selectOption('operations');
  await username.fill('admin');
  await password.fill(credentials.admin_password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(overview).toBeVisible();
  await page.reload();
  await expect(overview).toBeVisible();

  const signOut = page.getByRole('button', { name: 'Sign out', exact: true });
  await expect(signOut).toBeInViewport({ ratio: 1 });
  await signOut.click();
  await expect(login).toBeVisible();
  expect((await page.request.get('/api/v1/session')).status()).toBe(401);
  await page.reload();
  await expect(login).toBeVisible();
});
