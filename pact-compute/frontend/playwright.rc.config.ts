import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './rc-e2e', testMatch: 'accessibility.spec.ts', workers: 1,
  timeout: 180_000, expect: { timeout: 15_000 },
  use: { baseURL: 'http://127.0.0.1:18766', channel: 'msedge', viewport: { width: 1440, height: 1000 }, screenshot: 'off' },
});
