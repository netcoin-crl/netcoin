import { defineConfig } from '@playwright/test';

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:4173';
const port = new URL(baseURL).port || '4173';

export default defineConfig({
  testDir: '.',
  timeout: 30000,
  use: {
    baseURL,
    trace: 'retain-on-failure'
  },
  webServer: process.env.PLAYWRIGHT_SKIP_WEBSERVER ? undefined : {
    command: `python3 -m http.server ${port}`,
    url: baseURL,
    reuseExistingServer: true,
    timeout: 10000
  }
});
