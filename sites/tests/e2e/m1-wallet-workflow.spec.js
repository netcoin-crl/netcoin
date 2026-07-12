import { test, expect } from '@playwright/test';

const API_TXID = 'b'.repeat(64);
const FAKE_UTXO_TXID = 'a'.repeat(64);

async function mockWalletApi(page) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, '') || '/';
    const json = (body) => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });

    if (path.startsWith('/balance/')) {
      return json({ spendable_sats: 5000000000, total_sats: 5000000000, immature_sats: 0 });
    }
    if (path.startsWith('/address/')) {
      return json({ address: decodeURIComponent(path.split('/').pop() || ''), transaction_ids: [] });
    }
    if (path === '/utxos') {
      const address = url.searchParams.get('address') || 'net1qtest';
      return json({
        utxos: [
          { txid: FAKE_UTXO_TXID, vout: 0, output: { amount: 5000000000, address } },
        ],
      });
    }
    if (path === '/info') {
      return json({ height: 15800, target_spacing_seconds: 300 });
    }
    if (path === '/supply') {
      return json({ next_subsidy: '50' });
    }
    if (path === '/tokens') {
      return json({ tokens: [] });
    }
    if (path === '/wallet/workflow') {
      return json({ drafts: [], approvals: [], fee_presets: { slow: '0.00005000', normal: '0.00050000', fast: '0.00500000' }, offline_signing: { unsigned_export: true } });
    }
    if (path === '/wallet/limits/check') {
      return json({ ok: true, limits: { mode: 'daily' }, reasons: [] });
    }
    if (path === '/wallet/spend-log' || path === '/wallet/backup-health') {
      return json({ ok: true });
    }
    if (path === '/tx' && request.method() === 'POST') {
      return json({ txid: API_TXID });
    }
    return json({ ok: true });
  });
}

async function createWalletAndSkipBackupQuiz(page) {
  await page.goto('/sites/wallet/index.html');
  await expect(page.locator('#welcome')).toBeVisible();
  await page.locator('#btnCreate').click();
  await expect(page.locator('#create')).toBeVisible();
  await expect(page.locator('#newPhrase')).toContainText('net');
  await page.locator('#createPw').fill('correct horse battery staple');
  await page.locator('#btnCreateConfirm').click();
  await expect(page.locator('#backupQuiz')).toBeVisible();
  await page.locator('#btnQuizSkip').click();
  await expect(page.locator('#walletView')).toBeVisible();
  await expect(page.locator('#walletTabs')).toBeVisible();
  await expect(page.locator('#addr')).not.toBeEmpty();
}

test.describe('M1 wallet workflow regression coverage', () => {
  test.beforeEach(async ({ page }) => {
    await mockWalletApi(page);
    await page.addInitScript(() => {
      window.localStorage.clear();
      window.sessionStorage.clear();
    });
  });

  test('create wallet, receive, send, lock, and unlock stay functional', async ({ page }) => {
    await createWalletAndSkipBackupQuiz(page);

    const walletAddress = await page.locator('#addr').getAttribute('title');
    expect(walletAddress).toMatch(/^net/);

    await page.locator('#requestAmount').fill('1.25');
    await page.locator('#requestLabel').fill('M1 test payment');
    await page.locator('#btnMakePaymentLink').click();
    await expect(page.locator('#receiveOut')).toBeVisible();
    await expect(page.locator('#paymentUri')).toContainText(`netcoin:${walletAddress}`);
    await expect(page.locator('#paymentUri')).toContainText('amount=1.25');

    await page.locator('#toAddr').fill(walletAddress);
    await page.locator('#amount').fill('0.01');
    // #fee lives inside the collapsed "Fee & coin control" details panel.
    await page.locator('details.send-advanced-panel > summary').click();
    await page.locator('#fee').fill('0.00050000');
    await page.locator('#btnSend').click();
    await expect(page.locator('#sendReview')).toBeVisible();
    await expect(page.locator('#reviewTo')).toHaveText(walletAddress || '');
    await expect(page.locator('#reviewAmount')).toContainText('0.01 NET');
    await page.locator('#btnConfirmSend').click();
    await expect(page.locator('#sendMsg')).toContainText(`Sent ✓ txid ${API_TXID.slice(0, 16)}`);

    await page.locator('#btnLock').click();
    await expect(page.locator('#unlock')).toBeVisible();
    await expect(page.locator('#walletView')).toBeHidden();
    await page.locator('#unlockPw').fill('correct horse battery staple');
    await page.locator('#btnUnlock').click();
    await expect(page.locator('#walletView')).toBeVisible();
    await expect(page.locator('#walletTabs')).toBeVisible();
  });

  test('tab shell renders without relying on the Lock wallet button anchor', async ({ page }) => {
    await createWalletAndSkipBackupQuiz(page);
    const diagnostics = await page.evaluate(() => {
      const wallet = document.getElementById('walletView');
      const tabs = document.getElementById('walletTabs');
      const lock = document.getElementById('btnLock');
      return {
        hasTabs: Boolean(tabs),
        firstChildIsTabs: wallet?.firstElementChild?.id === 'walletTabs',
        lockButtonNestedInOverview: Boolean(lock?.closest('.wallet-overview-card')),
        activeCards: Array.from(document.querySelectorAll('.wallet-section.active-section')).map((el) => el.id || el.getAttribute('data-wallet-tab')),
      };
    });

    expect(diagnostics.hasTabs).toBe(true);
    expect(diagnostics.firstChildIsTabs).toBe(true);
    expect(diagnostics.lockButtonNestedInOverview).toBe(true);
    expect(diagnostics.activeCards).toContain('wallet-home');
    expect(diagnostics.activeCards).toContain('wallet-send');
  });
});
