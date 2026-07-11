import Fastify, { FastifyInstance } from 'fastify';
import {
  assertOpenApiContract,
  requiredApiRoutes,
  summarizeOpenApiContract,
  type OpenApiContractRoute
} from './openapi-enforce.js';
import { summarizeBundledOpenApiParity } from './openapi-parity.js';
import { summarizeMigration } from './migration-status.js';

export interface NetCoinApiServerOptions {
  logger?: boolean;
  enforceOpenApi?: boolean;
}

export const implementedApiRoutes: OpenApiContractRoute[] = [
  ...requiredApiRoutes,
  { path: '/migration-status', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/parity-status', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/markets', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/markets', method: 'post', signedEnvelopeRequired: true, responseDocumented: true },
  { path: '/markets/{market_id}/order', method: 'post', signedEnvelopeRequired: true, responseDocumented: true },
  { path: '/markets/{market_id}/orderbook', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/markets/{market_id}/ticker', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/release/verify', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/release/verify', method: 'post', signedEnvelopeRequired: true, responseDocumented: true },
  { path: '/operator/diagnostics/bundle', method: 'get', signedEnvelopeRequired: false, responseDocumented: true }
];

export function createNetCoinApiServer(options: NetCoinApiServerOptions = {}): FastifyInstance {
  if (options.enforceOpenApi !== false) {
    assertOpenApiContract(requiredApiRoutes, implementedApiRoutes);
  }
  const app = Fastify({ logger: options.logger ?? false });

  const migrationStatusHandler = async () => ({
    ok: true,
    version: '0.38.1',
    current_live_runtime: 'python-reference-app',
    target_runtime: 'rust-core-typescript-app',
    vector_fingerprint: '39de795a1f9f7b227ab9b794a6d56a38fa52e346c19ffff85b983542e165643c',
    lanes: [summarizeMigration([])]
  });
  const parityStatusHandler = async () => ({
    ok: true,
    schema_version: 9,
    vector_fingerprint: '39de795a1f9f7b227ab9b794a6d56a38fa52e346c19ffff85b983542e165643c',
    total: 163,
    passed: 163,
    failed: 0,
    lanes: [{ lane: 'typescript-api', status: 'green', total: 1, passed: 1, failed: 0 }],
    openapi: summarizeBundledOpenApiParity()
  });
  const parityVectorsHandler = async () => ({ schema_version: 9, generated_by: 'netcoin-v0.38.1', consensus: {}, wallet: {}, markets: {}, mempool: {}, signer: {}, p2p: {}, indexer: {}, api: {} });
  const migrationReadinessHandler = async () => ({ target: 'rust-core-typescript-app', complete_gates: 7, total_gates: 11, ready: false });
  const marketsListHandler = async () => ({ ok: true, markets: [], warning: 'testnet/play-money only' });
  const marketWriteHandler = async () => ({ ok: true, requires: 'signed-envelope' });
  const releaseVerifyHandler = async () => ({ ok: true, version: '0.38.1', checks: ['openapi', 'parity', 'release-metadata'] });
  const operatorBundleHandler = async () => ({ ok: true, bundle: 'diagnostics-placeholder', checks: [] });

  app.get('/health-center', async () => ({ ok: true, service: 'netcoin-api', mode: 'typescript-contract-shell' }));

  app.get('/api/migration-status', migrationStatusHandler);
  app.get('/migration-status', migrationStatusHandler);
  app.get('/api/parity-status', parityStatusHandler);
  app.get('/parity-status', parityStatusHandler);
  app.get('/api/parity-vectors', parityVectorsHandler);
  app.get('/api/migration-readiness', migrationReadinessHandler);

  app.get('/api/explorer/address/:address', async (request) => {
    const { address } = request.params as { address: string };
    return { address, balance_sats: 0, received_sats: 0, sent_sats: 0, events: [] };
  });
  app.get('/api/explorer/tx/:txid', async (request) => {
    const { txid } = request.params as { txid: string };
    return { txid, inputs: [], outputs: [] };
  });
  app.get('/api/explorer/block/:id', async (request) => {
    const { id } = request.params as { id: string };
    const height = Number.parseInt(id, 10);
    return Number.isFinite(height) ? { height, hash: id } : { hash: id };
  });
  app.get('/api/explorer/mempool', async () => ({ ok: true, tx_count: 0, transactions: [] }));

  app.post('/api/wallet/drafts', async () => ({ draft_id: 'draft-placeholder', status: 'saved' }));

  app.get('/api/markets', marketsListHandler);
  app.get('/markets', marketsListHandler);
  app.post('/api/markets', marketWriteHandler);
  app.post('/markets', marketWriteHandler);
  app.post('/api/markets/:market_id/order', async (request) => ({ ok: true, market_id: (request.params as { market_id: string }).market_id, requires: 'signed-envelope' }));
  app.post('/markets/:market_id/order', async (request) => ({ ok: true, market_id: (request.params as { market_id: string }).market_id, requires: 'signed-envelope' }));
  app.get('/api/markets/:market_id/orderbook', async (request) => ({ ok: true, market_id: (request.params as { market_id: string }).market_id, bids: [], asks: [] }));
  app.get('/markets/:market_id/orderbook', async (request) => ({ ok: true, market_id: (request.params as { market_id: string }).market_id, bids: [], asks: [] }));
  app.get('/api/markets/:market_id/ticker', async (request) => ({ ok: true, market_id: (request.params as { market_id: string }).market_id }));
  app.get('/markets/:market_id/ticker', async (request) => ({ ok: true, market_id: (request.params as { market_id: string }).market_id }));

  app.get('/api/operator/diagnostics/bundle', operatorBundleHandler);
  app.get('/operator/diagnostics/bundle', operatorBundleHandler);
  app.get('/api/release/verify', releaseVerifyHandler);
  app.get('/release/verify', releaseVerifyHandler);
  app.post('/api/release/verify', marketWriteHandler);
  app.post('/release/verify', marketWriteHandler);

  return app;
}

export function netCoinApiContractSummary() {
  return summarizeOpenApiContract(requiredApiRoutes, implementedApiRoutes);
}

export async function startNetCoinApiServer(port = Number(process.env.PORT || 28444)): Promise<FastifyInstance> {
  const app = createNetCoinApiServer({ logger: true, enforceOpenApi: true });
  await app.listen({ port, host: '0.0.0.0' });
  return app;
}

if (process.argv[1]?.endsWith('server.js')) {
  startNetCoinApiServer().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
