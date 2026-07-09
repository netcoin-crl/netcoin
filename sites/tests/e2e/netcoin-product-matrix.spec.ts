import { test, expect } from '@playwright/test';

const surfaces = [
  { name: 'wallet', path: 'sites/wallet/index.html', checks: ['overview', 'send', 'receive', 'activity'] },
  { name: 'explorer', path: 'sites/explorer/index.html', checks: ['address', 'tx', 'block', 'mempool'] },
  { name: 'markets', path: 'sites/markets/index.html', checks: ['orderbook', 'portfolio', 'trades', 'settlement'] },
  { name: 'faucet', path: 'sites/faucet/index.html', checks: ['challenge', 'claim', 'status', 'admin'] },
  { name: 'operator', path: 'sites/operator/index.html', checks: ['health', 'diagnostics', 'bundle', 'alerts'] },
  { name: 'exchange', path: 'sites/exchange/index.html', checks: ['deposits', 'withdrawals', 'custody', 'reserves'] }
];

test.describe('NetCoin v0.36 browser E2E matrix', () => {
  for (const surface of surfaces) {
    test(`${surface.name} surface has a reachable product shell`, async ({ page }) => {
      await page.goto(`/${surface.path}`);
      await expect(page.locator('body')).toBeVisible();
      const body = (await page.locator('body').innerText()).toLowerCase();
      for (const check of surface.checks) {
        expect(body).toContain(check);
      }
    });
  }
});
