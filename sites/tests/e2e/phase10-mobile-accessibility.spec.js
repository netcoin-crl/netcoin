import { test, expect } from '@playwright/test';

const MOBILE = { width: 390, height: 844 };

async function expectNoHorizontalOverflow(page) {
  const dims = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(dims.scrollWidth).toBeLessThanOrEqual(dims.innerWidth + 2);
}

test.describe('Phase 10 mobile and accessibility smoke', () => {
  test.use({ viewport: MOBILE });

  test('wallet mobile surface keeps Phase 1-8 controls usable', async ({ page }) => {
    await page.goto('/sites/wallet/index.html');
    await expect(page.locator('#walletFlowGuide')).toBeVisible();
    await expect(page.locator('#feePresetCards')).toBeVisible();
    await expect(page.locator('#sendChecklist')).toBeVisible();
    await expect(page.locator('#sendMsg')).toHaveAttribute('aria-live', 'polite');
    await expectNoHorizontalOverflow(page);
  });

  test('homepage hub and features catalog do not overflow on phone viewport', async ({ page }) => {
    await page.goto('/sites/www/index.html');
    await expect(page.locator('.use-hub-grid')).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await page.goto('/sites/features/index.html');
    await expect(page.locator('#featureSearch')).toHaveAttribute('aria-label', 'Search feature catalog');
    await expectNoHorizontalOverflow(page);
  });

  test('operator and localnet status surfaces remain readable on mobile', async ({ page }) => {
    await page.goto('/sites/operator/index.html');
    await expect(page.locator('#ledgerAudit')).toBeVisible();
    await expect(page.locator('#chainstate')).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await page.goto('/sites/docs/localnet.html');
    await expect(page.locator('.localnet-status-grid')).toHaveAttribute('role', 'status');
    await expectNoHorizontalOverflow(page);
  });
});
