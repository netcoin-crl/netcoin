import { test, expect } from '@playwright/test';

const pages = [
  ['/sites/operator/index.html', /Operator/i, 'Live feature wiring'],
  ['/sites/exchange/index.html', /Exchange/i, 'Custody balances'],
  ['/sites/explorer/address.html', /Address/i, 'CSV statement'],
  ['/sites/explorer/tx.html', /Transaction/i, 'txid'],
  ['/sites/explorer/block.html', /Block/i, 'height'],
  ['/sites/explorer/mempool.html', /Mempool/i, 'Pending transactions'],
  ['/sites/markets/trade.html', /Markets/i, 'Order ticket'],
  ['/sites/markets/portfolio.html', /Portfolio/i, 'Open orders'],
  ['/sites/markets/disputes.html', /Dispute/i, 'Evidence'],
  ['/sites/markets/settlement.html', /Settlement/i, 'Settlement report'],
  ['/sites/community/index.html', /Community/i, 'Leaderboard'],
  ['/sites/features/index.html', /Feature/i, 'Live wiring'],
  ['/sites/faucet/admin.html', /Faucet Admin/i, 'Recent abuse decisions'],
  ['/sites/download/verify.html', /Verify Release/i, 'Signature command'],
];

for (const [url, title, text] of pages) {
  test(url + ' exposes v0.17 product UI', async ({ page }) => {
    await page.goto(url);
    await expect(page.locator('body')).toContainText(title);
    await expect(page.locator('body')).toContainText(text);
    await expect(page.locator('.site-nav')).toHaveCount(1);
  });
}

test('wallet merges overview send receive activity contacts into one workspace', async ({ page }) => {
  await page.goto('/sites/wallet/index.html');
  await expect(page.locator('body')).toContainText('NetCoin Wallet');
  await expect(page.locator('body')).toContainText('Create wallet');
});
