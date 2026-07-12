import { test, expect } from '@playwright/test';

test('browser wallet shell loads and exposes recovery/vault UI hooks', async ({ page }) => {
  await page.goto('/webwallet-browser/public/wallet.html');
  await expect(page.locator('body')).toContainText(/NetCoin|wallet/i);
  await expect(page.locator('script[src*="wallet-vault"]')).toHaveCount(1);
});
