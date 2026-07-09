export interface OpenApiContractRoute {
  path: string;
  method: 'get' | 'post' | 'put' | 'patch' | 'delete';
  signedEnvelopeRequired: boolean;
  responseDocumented: boolean;
}

export interface OpenApiContractSummary {
  ok: boolean;
  routeCount: number;
  implementedRouteCount: number;
  missingRoutes: string[];
  unsignedSensitiveWrites: string[];
  undocumentedResponses: string[];
  duplicateRoutes: string[];
}

export const requiredApiRoutes: OpenApiContractRoute[] = [
  { path: '/health-center', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/migration-status', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/parity-status', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/parity-vectors', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/migration-readiness', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/explorer/address/{address}', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/explorer/tx/{txid}', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/explorer/block/{id}', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/explorer/mempool', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/wallet/drafts', method: 'post', signedEnvelopeRequired: true, responseDocumented: true },
  { path: '/api/markets', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/markets', method: 'post', signedEnvelopeRequired: true, responseDocumented: true },
  { path: '/api/markets/{market_id}/order', method: 'post', signedEnvelopeRequired: true, responseDocumented: true },
  { path: '/api/markets/{market_id}/orderbook', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/markets/{market_id}/ticker', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/operator/diagnostics/bundle', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/release/verify', method: 'get', signedEnvelopeRequired: false, responseDocumented: true },
  { path: '/api/release/verify', method: 'post', signedEnvelopeRequired: true, responseDocumented: true }
];

export function normalizeOpenApiPath(path: string): string {
  const withoutTrailingSlash = path.length > 1 ? path.replace(/\/+$/, '') : path;
  return withoutTrailingSlash.replace(/:[a-zA-Z_][a-zA-Z0-9_]*/g, (item) => `{${item.slice(1)}}`);
}

export function routeKey(route: Pick<OpenApiContractRoute, 'method' | 'path'>): string {
  return `${route.method.toLowerCase()} ${normalizeOpenApiPath(route.path)}`;
}

function duplicateRouteKeys(routes: OpenApiContractRoute[]): string[] {
  const seen = new Set<string>();
  const duplicates = new Set<string>();
  for (const route of routes) {
    const key = routeKey(route);
    if (seen.has(key)) {
      duplicates.add(key);
    }
    seen.add(key);
  }
  return [...duplicates].sort();
}

export function summarizeOpenApiContract(
  routes: OpenApiContractRoute[] = requiredApiRoutes,
  implementedRoutes: OpenApiContractRoute[] = routes
): OpenApiContractSummary {
  const implemented = new Set(implementedRoutes.map(routeKey));
  const missingRoutes = routes
    .filter((route) => !implemented.has(routeKey(route)))
    .map((route) => `${route.method.toUpperCase()} ${route.path}`);
  const unsignedSensitiveWrites = routes
    .filter((route) => ['post', 'put', 'patch', 'delete'].includes(route.method) && route.signedEnvelopeRequired !== true)
    .map((route) => `${route.method.toUpperCase()} ${route.path}`);
  const undocumentedResponses = routes
    .filter((route) => route.responseDocumented !== true)
    .map((route) => `${route.method.toUpperCase()} ${route.path}`);
  const duplicateRoutes = duplicateRouteKeys(implementedRoutes);
  return {
    ok: missingRoutes.length === 0 && unsignedSensitiveWrites.length === 0 && undocumentedResponses.length === 0 && duplicateRoutes.length === 0,
    routeCount: routes.length,
    implementedRouteCount: implementedRoutes.length,
    missingRoutes,
    unsignedSensitiveWrites,
    undocumentedResponses,
    duplicateRoutes
  };
}

export function assertOpenApiContract(
  routes: OpenApiContractRoute[] = requiredApiRoutes,
  implementedRoutes: OpenApiContractRoute[] = routes
): OpenApiContractSummary {
  const summary = summarizeOpenApiContract(routes, implementedRoutes);
  if (!summary.ok) {
    throw new Error(`NetCoin OpenAPI contract failed: ${JSON.stringify(summary)}`);
  }
  return summary;
}
