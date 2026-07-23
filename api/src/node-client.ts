/** Thin HTTP gateway helpers for proxying to a running netcoin Python reference node.
 *
 * The Python node (netcoin/apps/__init__.py, netcoin/explorer_server.py) is the source of
 * truth for chain/market/wallet state. This module fetches from it and validates the
 * response shape with Zod before handing it back to a TypeScript API caller, so a
 * malformed or unexpected upstream response fails loudly instead of silently passing
 * through as if it were real data.
 */
import type { z } from 'zod';

export class UpstreamNodeError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = 'UpstreamNodeError';
    this.status = status;
    this.body = body;
  }
}

export class UpstreamValidationError extends Error {
  readonly body: unknown;
  readonly issues: unknown;

  constructor(message: string, body: unknown, issues: unknown) {
    super(message);
    this.name = 'UpstreamValidationError';
    this.body = body;
    this.issues = issues;
  }
}

export function netcoinNodeBaseUrl(): string {
  return (process.env.NETCOIN_NODE_URL || 'http://127.0.0.1:28444').replace(/\/+$/, '');
}

export interface NodeRequestOptions {
  method?: 'GET' | 'POST';
  body?: unknown;
  query?: Record<string, string | number | undefined>;
  fetchImpl?: typeof fetch;
  baseUrl?: string;
}

/** Fetches JSON from the netcoin node. Upstream `{ ok: false, error }` bodies (the
 * Python node's standard error envelope, see netcoin/explorer_server.py send_json calls)
 * are surfaced as UpstreamNodeError rather than treated as valid payloads. */
export async function fetchFromNode(path: string, options: NodeRequestOptions = {}): Promise<unknown> {
  const base = options.baseUrl ?? netcoinNodeBaseUrl();
  const method = options.method ?? 'GET';
  const url = new URL(`${base}${path}`);
  if (options.query) {
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  const fetchImpl = options.fetchImpl ?? fetch;
  const init: RequestInit = { method };
  if (method === 'POST') {
    init.headers = { 'content-type': 'application/json' };
    init.body = JSON.stringify(options.body ?? {});
  }
  let response: Response;
  try {
    response = await fetchImpl(url, init);
  } catch (error) {
    throw new UpstreamNodeError(
      `failed to reach netcoin node at ${url.toString()}: ${(error as Error).message}`,
      502,
      null
    );
  }
  const text = await response.text();
  let parsed: unknown = null;
  if (text.length > 0) {
    try {
      parsed = JSON.parse(text);
    } catch {
      throw new UpstreamNodeError(`netcoin node returned non-JSON response for ${path}`, 502, text);
    }
  }
  if (!response.ok) {
    const message =
      parsed && typeof parsed === 'object' && 'error' in (parsed as Record<string, unknown>)
        ? String((parsed as Record<string, unknown>).error)
        : `netcoin node request failed with status ${response.status}`;
    throw new UpstreamNodeError(message, response.status, parsed);
  }
  if (parsed && typeof parsed === 'object' && (parsed as Record<string, unknown>).ok === false) {
    const message = String((parsed as Record<string, unknown>).error ?? 'netcoin node reported an error');
    throw new UpstreamNodeError(message, 400, parsed);
  }
  return parsed;
}

/** Fetches from the node and validates the response against `schema`, throwing
 * UpstreamValidationError with the Zod issues if it doesn't match. */
export async function fetchAndValidate<T extends z.ZodTypeAny>(
  path: string,
  schema: T,
  options: NodeRequestOptions = {}
): Promise<z.infer<T>> {
  const data = await fetchFromNode(path, options);
  const result = schema.safeParse(data);
  if (!result.success) {
    throw new UpstreamValidationError(
      `netcoin node response for ${path} did not match the expected schema`,
      data,
      result.error.issues
    );
  }
  return result.data;
}
