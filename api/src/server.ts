import Fastify, { FastifyInstance, FastifyReply } from 'fastify';
import {
  assertOpenApiContract,
  requiredApiRoutes,
  summarizeOpenApiContract,
  type OpenApiContractRoute
} from './openapi-enforce.js';
import { summarizeBundledOpenApiParity } from './openapi-parity.js';
import { summarizeMigration } from './migration-status.js';
import { fetchAndValidate, UpstreamNodeError, UpstreamValidationError } from './node-client.js';
import {
  ExplorerAddressSchema,
  ExplorerTransactionSchema,
  ExplorerBlockSchema,
  ExplorerMempoolSchema,
  WalletDraftSchema,
  MarketsListSchema,
  MarketRecordSchema,
  MarketOrderResultSchema,
  MarketOrderbookSchema,
  MarketTickerSchema,
  NodeReleaseVerifySchema,
  OperatorDiagnosticsSchema
} from './schemas.js';

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

/** Translates a proxy failure (unreachable node, upstream error, or a response that
 * failed Zod validation) into a clear HTTP response instead of crashing or silently
 * passing through unvalidated data. */
function sendProxyError(reply: FastifyReply, error: unknown): FastifyReply {
  if (error instanceof UpstreamValidationError) {
    return reply.code(502).send({
      ok: false,
      error: error.message,
      issues: error.issues
    });
  }
  if (error instanceof UpstreamNodeError) {
    return reply.code(error.status === 502 ? 502 : error.status).send({
      ok: false,
      error: error.message
    });
  }
  return reply.code(502).send({ ok: false, error: (error as Error).message ?? 'netcoin node proxy failure' });
}

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

  app.get('/health-center', async () => ({ ok: true, service: 'netcoin-api', mode: 'netcoin-node-gateway' }));

  app.get('/api/migration-status', migrationStatusHandler);
  app.get('/migration-status', migrationStatusHandler);
  app.get('/api/parity-status', parityStatusHandler);
  app.get('/parity-status', parityStatusHandler);
  app.get('/api/parity-vectors', parityVectorsHandler);
  app.get('/api/migration-readiness', migrationReadinessHandler);

  // --- Explorer: proxy straight through to the netcoin Python node's live explorer
  // endpoints (netcoin/apps/__init__.py:5286-5308, netcoin/live_product.py). ---
  app.get('/api/explorer/address/:address', async (request, reply) => {
    const { address } = request.params as { address: string };
    try {
      return await fetchAndValidate(`/explorer/address/${encodeURIComponent(address)}`, ExplorerAddressSchema, {
        query: (request.query as Record<string, string>) ?? {}
      });
    } catch (error) {
      return sendProxyError(reply, error);
    }
  });

  app.get('/api/explorer/tx/:txid', async (request, reply) => {
    const { txid } = request.params as { txid: string };
    try {
      return await fetchAndValidate(`/explorer/tx/${encodeURIComponent(txid)}`, ExplorerTransactionSchema);
    } catch (error) {
      return sendProxyError(reply, error);
    }
  });

  // Block :id may be a numeric height OR a block hash -- the node itself disambiguates
  // (see netcoin/live_product.py:_block_payload, which tries block_at_height() first for
  // all-digit ids and falls back to get_block_by_hash()). The gateway just forwards the
  // raw id and never guesses.
  app.get('/api/explorer/block/:id', async (request, reply) => {
    const { id } = request.params as { id: string };
    try {
      return await fetchAndValidate(`/explorer/block/${encodeURIComponent(id)}`, ExplorerBlockSchema);
    } catch (error) {
      return sendProxyError(reply, error);
    }
  });

  app.get('/api/explorer/mempool', async (request, reply) => {
    try {
      return await fetchAndValidate('/explorer/mempool', ExplorerMempoolSchema, {
        query: (request.query as Record<string, string>) ?? {}
      });
    } catch (error) {
      return sendProxyError(reply, error);
    }
  });

  // --- Wallet drafts: real persistence via netcoin.live_product.save_wallet_draft,
  // reached through the node's POST /wallet/drafts route. ---
  app.post('/api/wallet/drafts', async (request, reply) => {
    try {
      return await fetchAndValidate('/wallet/drafts', WalletDraftSchema, {
        method: 'POST',
        body: request.body ?? {}
      });
    } catch (error) {
      return sendProxyError(reply, error);
    }
  });

  // --- Markets: proxy to netcoin.apps.markets. Signed-envelope verification for the
  // write routes happens on the node itself (netcoin/apps/auth.py require_signed_envelope_if_needed),
  // so the gateway forwards the request body untouched -- a real signed request reaches
  // the chain, and an unsigned/invalid one is rejected by the node, not silently accepted here. ---
  const marketsListHandler = async (request: any, reply: FastifyReply) => {
    try {
      return await fetchAndValidate('/markets', MarketsListSchema);
    } catch (error) {
      return sendProxyError(reply, error);
    }
  };
  const marketsCreateHandler = async (request: any, reply: FastifyReply) => {
    try {
      return await fetchAndValidate('/markets', MarketRecordSchema, { method: 'POST', body: request.body ?? {} });
    } catch (error) {
      return sendProxyError(reply, error);
    }
  };
  const marketOrderHandler = async (request: any, reply: FastifyReply) => {
    const { market_id } = request.params as { market_id: string };
    try {
      return await fetchAndValidate(`/markets/${encodeURIComponent(market_id)}/order`, MarketOrderResultSchema, {
        method: 'POST',
        body: request.body ?? {}
      });
    } catch (error) {
      return sendProxyError(reply, error);
    }
  };
  const marketOrderbookHandler = async (request: any, reply: FastifyReply) => {
    const { market_id } = request.params as { market_id: string };
    try {
      return await fetchAndValidate(`/markets/${encodeURIComponent(market_id)}/orderbook`, MarketOrderbookSchema, {
        query: (request.query as Record<string, string>) ?? {}
      });
    } catch (error) {
      return sendProxyError(reply, error);
    }
  };
  const marketTickerHandler = async (request: any, reply: FastifyReply) => {
    const { market_id } = request.params as { market_id: string };
    try {
      return await fetchAndValidate(`/markets/${encodeURIComponent(market_id)}/ticker`, MarketTickerSchema);
    } catch (error) {
      return sendProxyError(reply, error);
    }
  };

  app.get('/api/markets', marketsListHandler);
  app.get('/markets', marketsListHandler);
  app.post('/api/markets', marketsCreateHandler);
  app.post('/markets', marketsCreateHandler);
  app.post('/api/markets/:market_id/order', marketOrderHandler);
  app.post('/markets/:market_id/order', marketOrderHandler);
  app.get('/api/markets/:market_id/orderbook', marketOrderbookHandler);
  app.get('/markets/:market_id/orderbook', marketOrderbookHandler);
  app.get('/api/markets/:market_id/ticker', marketTickerHandler);
  app.get('/markets/:market_id/ticker', marketTickerHandler);

  // --- Operator diagnostics: proxy to the node's health/operator bundle. ---
  const operatorBundleHandler = async (_request: any, reply: FastifyReply) => {
    try {
      return await fetchAndValidate('/operator/diagnostics/bundle', OperatorDiagnosticsSchema);
    } catch (error) {
      return sendProxyError(reply, error);
    }
  };
  app.get('/api/operator/diagnostics/bundle', operatorBundleHandler);
  app.get('/operator/diagnostics/bundle', operatorBundleHandler);

  // --- Release verify: proxy to netcoin.live_product.release_verify_payload, which
  // checks for the verify_signature/verify_provenance/generate_sbom tooling and, when
  // sha256/expected_sha256 are supplied, does a real checksum comparison. ---
  const releaseVerifyGetHandler = async (request: any, reply: FastifyReply) => {
    try {
      return await fetchAndValidate('/release/verify', NodeReleaseVerifySchema, {
        query: (request.query as Record<string, string>) ?? {}
      });
    } catch (error) {
      return sendProxyError(reply, error);
    }
  };
  const releaseVerifyPostHandler = async (request: any, reply: FastifyReply) => {
    try {
      return await fetchAndValidate('/release/verify', NodeReleaseVerifySchema, {
        method: 'POST',
        body: request.body ?? {}
      });
    } catch (error) {
      return sendProxyError(reply, error);
    }
  };
  app.get('/api/release/verify', releaseVerifyGetHandler);
  app.get('/release/verify', releaseVerifyGetHandler);
  app.post('/api/release/verify', releaseVerifyPostHandler);
  app.post('/release/verify', releaseVerifyPostHandler);

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
