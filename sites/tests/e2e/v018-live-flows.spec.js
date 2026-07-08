import { test, expect } from '@playwright/test';

test('v0.18 explorer live pages expose connected controls', async ({ page }) => {
  await page.goto('/sites/explorer/address.html');
  await expect(page.locator('body')).toContainText('Address');
  await expect(page.locator('body')).toContainText('CSV');
  await page.goto('/sites/explorer/mempool.html');
  await expect(page.locator('body')).toContainText('Mempool');
});

test('v0.18 markets pages expose live orderbook and settlement workspaces', async ({ page }) => {
  await page.goto('/sites/markets/trade.html');
  await expect(page.locator('body')).toContainText('Order ticket');
  await expect(page.locator('body')).toContainText('YES');
  await page.goto('/sites/markets/disputes.html');
  await expect(page.locator('body')).toContainText('Dispute');
  await page.goto('/sites/markets/settlement.html');
  await expect(page.locator('body')).toContainText('Settlement');
});

test('v0.18 wallet send workflow keeps draft and offline export controls visible', async ({ page }) => {
  await page.goto('/sites/wallet/index.html');
  await expect(page.locator('body')).toContainText('Save draft');
  await expect(page.locator('body')).toContainText('Export unsigned');
});

test('v0.18 operator exchange faucet and release pages expose live controls', async ({ page }) => {
  for (const url of ['/sites/operator/index.html','/sites/exchange/index.html','/sites/faucet/admin.html','/sites/download/verify.html']) {
    await page.goto(url);
    await expect(page.locator('.site-nav')).toHaveCount(1);
  }
  await page.goto('/sites/faucet/admin.html');
  await expect(page.locator('body')).toContainText('Emergency pause');
  await page.goto('/sites/download/verify.html');
  await expect(page.locator('body')).toContainText('artifact');
});
