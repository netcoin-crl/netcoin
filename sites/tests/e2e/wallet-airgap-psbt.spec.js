import { test, expect } from '@playwright/test';

const API_TXID = 'c'.repeat(64);
const FAKE_UTXO_TXID = 'a'.repeat(64);

async function mockWalletApi(page) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api/, '') || '/';
    const json = (body) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    if (path.startsWith('/balance/')) return json({ spendable_sats: 5000000000, total_sats: 5000000000, immature_sats: 0 });
    if (path.startsWith('/address/')) return json({ address: decodeURIComponent(path.split('/').pop() || ''), transaction_ids: [] });
    if (path === '/utxos') {
      const address = url.searchParams.get('address') || 'net1qtest';
      return json({ utxos: [{ txid: FAKE_UTXO_TXID, vout: 0, output: { amount: 5000000000, address } }] });
    }
    if (path === '/info') return json({ height: 15800, target_spacing_seconds: 300 });
    if (path === '/tx' && route.request().method() === 'POST') return json({ txid: API_TXID });
    return json({ ok: true });
  });
}

async function createWallet(page) {
  await page.goto('/sites/wallet/index.html');
  await expect(page.locator('#welcome')).toBeVisible();
  await page.locator('#btnCreate').click();
  await page.locator('#createPw').fill('correct horse battery staple');
  await page.locator('#btnCreateConfirm').click();
  await expect(page.locator('#backupQuiz')).toBeVisible();
  await page.locator('#btnQuizSkip').click();
  await expect(page.locator('#walletView')).toBeVisible();
}

test('airgap PSBT loop: create unsigned -> sign offline -> import -> broadcast', async ({ page }) => {
  await mockWalletApi(page);
  await createWallet(page);

  const address = await page.locator('#addr').getAttribute('title');
  expect(address).toMatch(/^net/);

  // Fill the send fields that makeUnsignedPsbt() reads (self-send is a valid recipient).
  await page.evaluate((addr) => {
    document.getElementById('toAddr').value = addr;
    document.getElementById('amount').value = '1';
    document.getElementById('fee').value = '0.01';
    // Reveal the advanced offline-signing card so its buttons are clickable.
    document.querySelectorAll('.wallet-section').forEach((s) => s.classList.add('active-section'));
  }, address);

  // 1. Create unsigned PSBT.
  await page.locator('#btnMakePsbt').click();
  await expect(page.locator('#psbtOut')).not.toBeEmpty();
  expect(await page.locator('#psbtOut').inputValue()).toContain('netpsbt:');

  // 2. Sign offline (software signer on this device).
  await expect(page.locator('#btnSignPsbtOffline')).toBeEnabled();
  await page.locator('#btnSignPsbtOffline').click();
  await expect(page.locator('#signedPsbtOut')).not.toBeEmpty();
  expect(await page.locator('#signedPsbtOut').inputValue()).toContain('netpsbt-signed:');

  // 3. Import the signed PSBT (re-verifies intent hash) and review.
  await page.locator('#btnImportSignedPsbt').click();
  await expect(page.locator('#psbtReview')).toBeVisible();
  await expect(page.locator('#psbtReview')).toContainText('To');
  await expect(page.locator('#psbtReview')).toContainText('NET');

  // 4. Broadcast the signed transaction.
  await expect(page.locator('#btnBroadcastSignedPsbt')).toBeEnabled();
  await page.locator('#btnBroadcastSignedPsbt').click();
  await expect(page.locator('#descriptorMsg')).toContainText('Broadcast');
});

test('airgap PSBT refuses a tampered signed payload', async ({ page }) => {
  await mockWalletApi(page);
  await createWallet(page);
  const address = await page.locator('#addr').getAttribute('title');
  await page.evaluate((addr) => {
    document.getElementById('toAddr').value = addr;
    document.getElementById('amount').value = '1';
    document.getElementById('fee').value = '0.01';
    document.querySelectorAll('.wallet-section').forEach((s) => s.classList.add('active-section'));
  }, address);
  await page.locator('#btnMakePsbt').click();
  await page.locator('#btnSignPsbtOffline').click();

  // Tamper: flip a byte inside the base64 signed payload, then import.
  const tampered = await page.evaluate(() => {
    const t = document.getElementById('signedPsbtOut').value;
    const body = t.slice('netpsbt-signed:'.length);
    const obj = JSON.parse(atob(body));
    obj.intent.amount = 999; // change where/how much -> intent hash must no longer match
    return 'netpsbt-signed:' + btoa(JSON.stringify(obj));
  });
  await page.locator('#signedPsbtOut').fill(tampered);
  await page.locator('#btnImportSignedPsbt').click();
  await expect(page.locator('#descriptorMsg')).toContainText('tampered');
  await expect(page.locator('#btnBroadcastSignedPsbt')).toBeDisabled();
});
