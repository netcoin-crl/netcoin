# NetCoin Key Management Policy

## Wallet Keys

- Prefer encrypted wallet files for any non-throwaway key.
- Use high-entropy passphrases and store backups offline.
- Run seed recovery tests before relying on a wallet.
- Use watch-only wallets for monitoring.
- Do not paste private keys or seed phrases into public community posts.
- Use auto-lock sessions for decrypted wallet material.

## Treasury Keys

- Use multisig for treasury addresses.
- Require at least two independent approvals for treasury proposals.
- Keep one signer offline.
- Rotate signers when a device, employee, or contractor changes trust status.
- Maintain an emergency signer replacement process.

## Merchant/API Keys

- Store API keys as secrets.
- Prefer scoped permissions.
- Rotate keys after incident response or staff changes.
- Monitor `/api/merchant/api-usage` for unexpected use.

## Webhook Secrets

- Use HTTPS public endpoints only in production.
- Verify HMAC signatures on every webhook event.
- Rotate webhook secrets if logs or endpoints are exposed.

## Prohibited Practices

- No long-lived plaintext private keys on shared servers.
- No seed phrases in tickets, emails, chats, screenshots, or public posts.
- No hot-wallet automation without an explicit risk acknowledgement and spending cap.
