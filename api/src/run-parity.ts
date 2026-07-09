/** Executable TypeScript parity runner.
 * Loads the SAME frozen parity vectors the Python reference and Rust core use,
 * and asserts the TypeScript executor reproduces the expected results. Exits
 * non-zero on any mismatch so CI gates the typescript-api-contracts lane. */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { moneyInRange, txFeeOk, validQuote, orderNotionalOk } from './parity-executor.js';

interface VectorCase {
  id: string;
  kind?: string;
  expected?: boolean;
  amount_sats?: number;
  max_money_sats?: number;
  input_sats?: number;
  output_sats?: number;
  price_bps?: number;
  quantity?: number;
  min_notional_sats?: number;
}

const here = dirname(fileURLToPath(import.meta.url));
const fixturePath = join(here, '..', 'fixtures', 'parity-vectors.json');
const fixture = JSON.parse(readFileSync(fixturePath, 'utf8')) as Record<string, unknown>;

const cases: VectorCase[] = Object.values(fixture).flatMap((section) =>
  section && typeof section === 'object' && 'cases' in section
    ? ((section as { cases: VectorCase[] }).cases ?? [])
    : []
);

const handlers: Record<string, (c: VectorCase) => boolean> = {
  money_range: (c) => moneyInRange(c.amount_sats!, c.max_money_sats!),
  tx_fee: (c) => txFeeOk(c.input_sats!, c.output_sats!),
  quote: (c) => validQuote(c.price_bps!, c.quantity!),
  order_notional: (c) => orderNotionalOk(c.price_bps!, c.quantity!, c.min_notional_sats!)
};

let checked = 0;
let failed = 0;
for (const c of cases) {
  const handler = c.kind ? handlers[c.kind] : undefined;
  if (!handler) continue;
  const got = handler(c);
  checked += 1;
  if (got !== c.expected) {
    failed += 1;
    console.error(`FAIL ${c.id} (${c.kind}): got ${got}, expected ${c.expected}`);
  }
}

console.log(
  JSON.stringify({ lane: 'typescript-api-parity', checked, failed, ok: failed === 0 })
);
if (checked === 0 || failed > 0) {
  process.exit(1);
}
