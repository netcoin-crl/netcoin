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

export const ExplorerAddressSchema = z.object({
  address: z.string(),
  balance_sats: z.number().int().optional(),
  received_sats: z.number().int().optional(),
  sent_sats: z.number().int().optional(),
  events: z.array(z.unknown()).default([])
});

export const WalletDraftSchema = z.object({
  draft_id: z.string(),
  status: z.enum(['saved', 'review', 'blocked']).default('saved'),
  amount_sats: z.number().int().nonnegative().optional(),
  destination: z.string().optional()
});

export const MarketOrderSchema = z.object({
  market_id: z.string().min(1),
  outcome: z.enum(['YES', 'NO', 'yes', 'no']),
  side: z.enum(['buy', 'sell', 'BUY', 'SELL']),
  order_type: z.enum(['limit', 'market']).default('limit'),
  price: z.number().min(0).max(1).optional(),
  quantity: z.number().positive()
});

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

export const ExplorerTransactionSchema = z.object({
  txid: z.string(),
  block_hash: z.string().optional(),
  confirmations: z.number().int().nonnegative().optional(),
  inputs: z.array(z.unknown()).default([]),
  outputs: z.array(z.unknown()).default([])
});

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
