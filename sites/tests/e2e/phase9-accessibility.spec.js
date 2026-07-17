import { test, expect } from '@playwright/test';

test.describe('Phase 9 accessibility hardening', () => {
  test('shared shell exposes skip link and accessible command palette', async ({ page }) => {
    await page.goto('/sites/wallet/index.html');
    await page.keyboard.press('Tab');
    await expect(page.locator('.nc-skip-link')).toBeFocused();
    await expect(page.locator('.nc-skip-link')).toHaveText('Skip to main content');

    await page.keyboard.press(process.platform === 'darwin' ? 'Meta+K' : 'Control+K');
    const palette = page.locator('#ncCommandPalette');
    await expect(palette).toHaveAttribute('role', 'dialog');
    await expect(palette).toHaveAttribute('aria-modal', 'true');
    await expect(page.locator('#ncCommandResults')).toHaveAttribute('role', 'listbox');
    await expect(page.locator('.nc-command-input')).toBeFocused();
    await page.locator('.nc-command-input').fill('wallet');
    await expect(page.locator('.nc-command-item').first()).toHaveAttribute('role', 'option');
    await page.keyboard.press('Escape');
    await expect(palette).not.toHaveClass(/open/);
  });

  test('wallet critical messages use live regions and explicit labels', async ({ page }) => {
    await page.goto('/sites/wallet/index.html');
    await expect(page.locator('#walletStatus')).toHaveAttribute('role', 'status');
    await expect(page.locator('#sendMsg')).toHaveAttribute('aria-live', 'polite');
    await expect(page.locator('#reviewWarning')).toHaveAttribute('role', 'alert');
    await expect(page.locator('#toAddr')).toHaveAttribute('aria-label', /recipient/i);
    await expect(page.locator('#rbfBumpOut')).toHaveAttribute('role', 'status');
  });

  test('newly exposed availability pages keep searchable fields labeled', async ({ page }) => {
    await page.goto('/sites/explorer/address.html');
    await expect(page.locator('#addrInput')).toHaveAttribute('aria-label', 'Search address');
    await page.goto('/sites/features/index.html');
    await expect(page.locator('#featureSearch')).toHaveAttribute('aria-label', 'Search feature catalog');
    await page.goto('/sites/docs/localnet.html');
    await expect(page.locator('.localnet-status-grid')).toHaveAttribute('role', 'status');
  });
});
