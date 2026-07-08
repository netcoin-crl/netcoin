/** TypeScript parity helper skeleton mirroring v0.22 vector cases. */
export function moneyInRange(amountSats: number, maxMoneySats: number): boolean {
  return Number.isInteger(amountSats) && amountSats >= 0 && amountSats <= maxMoneySats;
}

export function txFeeOk(inputSats: number, outputSats: number): boolean {
  return inputSats >= 0 && outputSats >= 0 && inputSats >= outputSats;
}

export function walletDecision(inputCount: number, balanceAfterSats: number, warnings: string[] = [], feeRateSatVb = 0, dustChangeSats = 0, recipientReused = false): 'allow' | 'review' | 'block' {
  const lower = warnings.map((warning) => warning.toLowerCase());
  if (balanceAfterSats < 0 || lower.some((w) => w.includes('frozen') || w.includes('poison')) || feeRateSatVb >= 250) return 'block';
  if (lower.length > 0 || inputCount > 20 || feeRateSatVb >= 50 || (dustChangeSats > 0 && dustChangeSats < 546) || recipientReused) return 'review';
  return 'allow';
}

export function validQuote(priceBps: number, quantity: number): boolean {
  return quantity > 0 && priceBps > 0 && priceBps < 10_000;
}

export function orderNotionalOk(priceBps: number, quantity: number, minNotionalSats: number): boolean {
  return Math.floor((priceBps * quantity) / 10_000) >= minNotionalSats;
}
