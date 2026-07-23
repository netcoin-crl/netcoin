/** Typed NetCoin API schema foundation.
 *
 * These schemas mirror the Python reference API. They are migration contracts,
 * not yet the live production TypeScript API.
 */
import { z } from 'zod';

export const SignedEnvelopeSchema = z.object({
  address: z.string().min(1),
  nonce: z.string().min(1),
  timestamp: z.number().int().nonnegative(),
  method: z.string().min(1),
  path: z.string().min(1),
  body_hash: z.string().min(32),
  signature: z.string().min(1)
});

// Real shape returned by netcoin.live_product.explorer_address_live (netcoin/live_product.py:84).
export const ExplorerAddressSchema = z
  .object({
    address: z.string(),
    balance: z.record(z.string(), z.unknown()),
    utxos: z.array(z.unknown()).default([]),
    history: z.array(z.unknown()).default([]),
    history_count: z.number().int().nonnegative().optional(),
    profile: z.record(z.string(), z.unknown()).optional(),
    exports: z.record(z.string(), z.unknown()).optional()
  })
  .passthrough();

// Real shape returned by netcoin.live_product.save_wallet_draft (netcoin/live_product.py:354).
export const WalletDraftSchema = z
  .object({
    draft_id: z.string(),
    status: z.string().default('draft'),
    to: z.string().optional(),
    amount: z.string().optional(),
    fee: z.string().optional(),
    memo: z.string().optional(),
    created_at: z.number().int().nonnegative().optional()
  })
  .passthrough();

export const MarketOrderSchema = z.object({
  market_id: z.string().min(1),
  outcome: z.enum(['YES', 'NO', 'yes', 'no']),
  side: z.enum(['buy', 'sell', 'BUY', 'SELL']),
  order_type: z.enum(['limit', 'market']).default('limit'),
  price: z.number().min(0).max(1).optional(),
  quantity: z.number().positive()
});

// Response shapes for the netcoin.apps.markets endpoints (netcoin/apps/markets/__init__.py).
// These payloads are large and evolve with the market engine, so we anchor on the
// stable identifying fields and pass the rest through rather than over-specify.
export const MarketsListSchema = z
  .object({
    markets: z.array(z.unknown()).optional(),
    count: z.number().int().nonnegative().optional()
  })
  .passthrough();

export const MarketRecordSchema = z
  .object({
    market_id: z.string()
  })
  .passthrough();

export const MarketOrderResultSchema = z
  .object({
    market_id: z.string().optional(),
    order_id: z.string().optional()
  })
  .passthrough();

export const MarketOrderbookSchema = z
  .object({
    market_id: z.string().optional(),
    bids: z.array(z.unknown()).optional(),
    asks: z.array(z.unknown()).optional()
  })
  .passthrough();

export const MarketTickerSchema = z
  .object({
    market_id: z.string().optional()
  })
  .passthrough();

// Real shape returned by netcoin.live_product.release_verify_payload (netcoin/live_product.py:661).
export const NodeReleaseVerifySchema = z
  .object({
    tools: z.record(z.string(), z.boolean()),
    checksum: z
      .object({
        provided: z.string(),
        expected: z.string(),
        match: z.boolean().nullable()
      })
      .passthrough(),
    commands: z.record(z.string(), z.string()),
    status: z.string()
  })
  .passthrough();

// Generic upstream error envelope: { ok: false, error: "..." } (netcoin/explorer_server.py send_json paths).
export const NodeErrorSchema = z
  .object({
    ok: z.literal(false),
    error: z.string()
  })
  .passthrough();

export const MigrationStatusSchema = z.object({
  ok: z.boolean(),
  version: z.string(),
  current_live_runtime: z.string(),
  target_runtime: z.string(),
  vector_fingerprint: z.string(),
  lanes: z.array(z.unknown())
});

export type SignedEnvelope = z.infer<typeof SignedEnvelopeSchema>;
export type ExplorerAddress = z.infer<typeof ExplorerAddressSchema>;
export type WalletDraft = z.infer<typeof WalletDraftSchema>;
export type MarketOrder = z.infer<typeof MarketOrderSchema>;
export type MigrationStatus = z.infer<typeof MigrationStatusSchema>;


export const ParityLaneSchema = z.object({
  lane: z.string(),
  status: z.enum(['green', 'red']),
  total: z.number().int().nonnegative(),
  passed: z.number().int().nonnegative(),
  failed: z.number().int().nonnegative()
});

export const ParityStatusSchema = z.object({
  ok: z.boolean(),
  schema_version: z.number().int().positive(),
  vector_fingerprint: z.string().length(64),
  total: z.number().int().nonnegative(),
  passed: z.number().int().nonnegative(),
  failed: z.number().int().nonnegative(),
  lanes: z.array(ParityLaneSchema)
});

export type ParityLane = z.infer<typeof ParityLaneSchema>;
export type ParityStatus = z.infer<typeof ParityStatusSchema>;

// Real shape returned by netcoin.live_product.explorer_tx_live (netcoin/live_product.py:218).
// On a missing transaction the node still returns 200 with { ok: false, error }.
export const ExplorerTransactionSchema = z
  .object({
    ok: z.boolean(),
    txid: z.string(),
    error: z.string().optional(),
    short_txid: z.string().optional(),
    risk: z.record(z.string(), z.unknown()).optional(),
    tx: z.record(z.string(), z.unknown()).optional()
  })
  .passthrough();

// Real shape returned by netcoin.live_product.explorer_block_live (netcoin/live_product.py:227).
// Accepts either a numeric height or a block hash as :id -- the node disambiguates.
export const ExplorerBlockSchema = z
  .object({
    ok: z.boolean(),
    id: z.string().optional(),
    error: z.string().optional(),
    height: z.number().int().nonnegative().optional(),
    hash: z.string().optional(),
    tx_count: z.number().int().nonnegative().optional(),
    txids: z.array(z.string()).optional()
  })
  .passthrough();

// Real shape returned by netcoin.live_product.explorer_mempool_live (netcoin/live_product.py:235).
export const ExplorerMempoolSchema = z
  .object({
    summary: z.record(z.string(), z.unknown()).optional(),
    transactions: z.array(z.unknown()).default([]),
    count: z.number().int().nonnegative(),
    generated_at: z.number().int().nonnegative().optional()
  })
  .passthrough();

export const WalletPreviewSchema = z.object({
  decision: z.enum(['allow', 'review', 'block']),
  amount_sats: z.number().int(),
  fee_sats: z.number().int(),
  fee_rate_sat_vb: z.number().int().optional(),
  warnings: z.array(z.string()).default([])
});

export const MarketSettlementSchema = z.object({
  market_id: z.string(),
  locked_collateral_sats: z.number().int().nonnegative(),
  claimable_payout_sats: z.number().int().nonnegative(),
  fees_sats: z.number().int().nonnegative(),
  conserved: z.boolean()
});

export const ParityVectorSchema = z.object({
  schema_version: z.number().int().positive(),
  generated_by: z.string(),
  consensus: z.unknown(),
  wallet: z.unknown(),
  markets: z.unknown(),
  mempool: z.unknown().optional(),
  signer: z.unknown().optional(),
  p2p: z.unknown().optional(),
  indexer: z.unknown().optional(),
  api: z.unknown()
});

export type ExplorerTransaction = z.infer<typeof ExplorerTransactionSchema>;
export type WalletPreview = z.infer<typeof WalletPreviewSchema>;
export type MarketSettlement = z.infer<typeof MarketSettlementSchema>;
export type ParityVector = z.infer<typeof ParityVectorSchema>;


export const SignerPolicySchema = z.object({
  decision: z.enum(['allow', 'review', 'block']),
  required_signers: z.number().int().positive(),
  available_signers: z.number().int().nonnegative()
});

export const P2PSyncSummarySchema = z.object({
  accepted: z.boolean(),
  linked: z.boolean(),
  checkpoint_ok: z.boolean(),
  protocol_ok: z.boolean()
});

export const IndexerSnapshotSchema = z.object({
  height: z.number().int().nonnegative().optional(),
  address: z.string().optional(),
  balance_sats: z.number().int().optional(),
  market_id: z.string().optional(),
  hash: z.string().optional()
});

export const OpenApiRouteSchema = z.object({
  method: z.enum(['GET', 'POST', 'PUT', 'PATCH', 'DELETE']).default('GET'),
  path: z.string().min(1),
  operation_id: z.string().optional()
});

export const OpenApiParitySchema = z.object({
  schema_ok: z.boolean(),
  route_ok: z.boolean(),
  client_ok: z.boolean(),
  codegen_ok: z.boolean()
});

export const MigrationReadinessSchema = z.object({
  target: z.string(),
  complete_gates: z.number().int().nonnegative(),
  total_gates: z.number().int().nonnegative(),
  ready: z.boolean()
});

export const OperatorDiagnosticsSchema = z.object({
  generated_at: z.string().optional(),
  checks: z.array(z.unknown()).default([]),
  ok: z.boolean().optional()
});

export const ReleaseVerifySchema = z.object({
  ok: z.boolean(),
  checks: z.array(z.unknown()).default([]),
  version: z.string().optional()
});

export type SignerPolicy = z.infer<typeof SignerPolicySchema>;
export type P2PSyncSummary = z.infer<typeof P2PSyncSummarySchema>;
export type IndexerSnapshot = z.infer<typeof IndexerSnapshotSchema>;
export type OpenApiRoute = z.infer<typeof OpenApiRouteSchema>;
export type OpenApiParity = z.infer<typeof OpenApiParitySchema>;
export type MigrationReadiness = z.infer<typeof MigrationReadinessSchema>;
export type OperatorDiagnostics = z.infer<typeof OperatorDiagnosticsSchema>;
export type ReleaseVerify = z.infer<typeof ReleaseVerifySchema>;
