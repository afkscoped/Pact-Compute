import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 210_000,
  expect: { timeout: 20_000 },
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.PACT_TEST_URL || 'http://127.0.0.1:8765',
    channel: process.env.PACT_TEST_BROWSER || 'msedge',
    viewport: { width: 1440, height: 1050 },
    screenshot: 'only-on-failure',
    actionTimeout: 12000,
  },
});
