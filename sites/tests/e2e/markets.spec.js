import { test, expect } from '@playwright/test';

test('markets labs page exposes CLOB and dispute workflow controls', async ({ page }) => {
  await page.goto('/sites/markets/index.html');
  await expect(page.locator('body')).toContainText('Discover markets');
  await expect(page.locator('#loadPolymarket')).toContainText('Load ideas');
  await expect(page.locator('#marketProStrip')).toContainText('Trade');
  await expect(page.locator('#operatorTools summary')).toContainText('Advanced tools');
  await expect(page.locator('#submitEvidence')).toHaveCount(1);
  await expect(page.locator('#submitDispute')).toHaveCount(1);
  await expect(page.locator('#orderType')).toContainText('Market');
});
