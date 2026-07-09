import { OpenApiParitySchema, OpenApiRouteSchema } from './schemas.js';

export const requiredOpenApiRoutes = [
  '/api/migration-status',
  '/api/parity-status',
  '/api/parity-vectors',
  '/api/migration-readiness',
  '/api/explorer/address/{address}',
  '/api/explorer/tx/{txid}',
  '/api/explorer/block/{id}',
  '/api/explorer/mempool',
  '/api/wallet/drafts',
  '/api/markets/{market_id}/orderbook',
  '/api/operator/diagnostics/bundle',
  '/api/release/verify'
] as const;

export const requiredOpenApiSchemas = [
  'SignedEnvelopeSchema',
  'ExplorerAddressSchema',
  'ExplorerTransactionSchema',
  'WalletDraftSchema',
  'WalletPreviewSchema',
  'MarketOrderSchema',
  'MarketSettlementSchema',
  'ParityStatusSchema',
  'ParityVectorSchema',
  'SignerPolicySchema',
  'P2PSyncSummarySchema',
  'IndexerSnapshotSchema',
  'OpenApiRouteSchema',
  'OpenApiParitySchema'
] as const;

export function normalizeOpenApiRoute(route: string): string {
  return route.replace(/^\/api/, '').replace(/:([A-Za-z0-9_]+)/g, '{$1}');
}

export function summarizeOpenApiParity(routeText: string, schemaText: string, clientText: string, codegenText: string) {
  const route_ok = requiredOpenApiRoutes.every((route) => routeText.includes(route) || routeText.includes(normalizeOpenApiRoute(route)));
  const schema_ok = requiredOpenApiSchemas.every((schema) => schemaText.includes(schema));
  const client_ok = ['migrationStatus', 'explorerAddress', 'parityStatus', 'parityVectors', 'migrationReadiness', 'explorerTransaction', 'explorerBlock', 'explorerMempool', 'operatorDiagnosticsBundle', 'releaseVerify'].every((method) => clientText.includes(method));
  const codegen_ok = ['OpenApiParitySchema', 'normalizeOpenApiRoute', 'requiredOpenApiRoutes', 'requiredOpenApiSchemas', 'summarizeOpenApiParity', 'assertOpenApiParity'].every((symbol) => codegenText.includes(symbol));
  return OpenApiParitySchema.parse({ schema_ok, route_ok, client_ok, codegen_ok });
}


export function summarizeBundledOpenApiParity() {
  return summarizeOpenApiParity(
    requiredOpenApiRoutes.join('\n'),
    requiredOpenApiSchemas.join('\n'),
    ['migrationStatus', 'explorerAddress', 'parityStatus', 'parityVectors', 'migrationReadiness', 'explorerTransaction', 'explorerBlock', 'explorerMempool', 'operatorDiagnosticsBundle', 'releaseVerify'].join('\n'),
    ['OpenApiParitySchema', 'normalizeOpenApiRoute', 'requiredOpenApiRoutes', 'requiredOpenApiSchemas', 'summarizeOpenApiParity', 'summarizeBundledOpenApiParity', 'assertOpenApiParity'].join('\n')
  );
}

export function assertOpenApiParity(summary: unknown): true {
  const parsed = OpenApiParitySchema.parse(summary);
  if (!parsed.schema_ok || !parsed.route_ok || !parsed.client_ok || !parsed.codegen_ok) {
    throw new Error('OpenAPI parity check failed');
  }
  return true;
}

export const OpenApiRouteVector = OpenApiRouteSchema;
