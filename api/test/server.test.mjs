import { test } from 'node:test';
import assert from 'node:assert/strict';
import { startFakeNode } from './fake-node.mjs';
import { createNetCoinApiServer } from '../dist/server.js';

async function withGateway(routes, fn) {
  const { server: fakeNode, baseUrl } = await startFakeNode(routes);
  const previousUrl = process.env.NETCOIN_NODE_URL;
  process.env.NETCOIN_NODE_URL = baseUrl;
  const app = createNetCoinApiServer({ logger: false });
  try {
    await fn(app);
  } finally {
    await app.close();
    fakeNode.close();
    if (previousUrl === undefined) delete process.env.NETCOIN_NODE_URL;
    else process.env.NETCOIN_NODE_URL = previousUrl;
  }
}

test('explorer address: happy path proxies real node data', async () => {
  await withGateway(
    [
      {
        method: 'GET',
        path: '/explorer/address/n1exampleaddr',
        handler: () => ({
          body: {
            address: 'n1exampleaddr',
            balance: { total_sats: 5000, spendable_sats: 5000 },
            utxos: [{ outpoint: 'abc:0', amount_sats: 5000 }],
            history: [{ txid: 'abc', height: 10 }],
            history_count: 1,
            profile: { address: 'n1exampleaddr', total_sats: 5000 },
            exports: { csv: '/api/explorer/address/n1exampleaddr/csv' }
          }
        })
      }
    ],
    async (app) => {
      const response = await app.inject({ method: 'GET', url: '/api/explorer/address/n1exampleaddr' });
      assert.equal(response.statusCode, 200);
      const payload = response.json();
      assert.equal(payload.address, 'n1exampleaddr');
      assert.equal(payload.balance.total_sats, 5000);
      assert.equal(payload.history.length, 1);
    }
  );
});

test('explorer address: malformed upstream response surfaces a clear 502, not a crash or pass-through', async () => {
  await withGateway(
    [
      {
        method: 'GET',
        path: '/explorer/address/bad',
        // Missing required "balance" key -- the real node always includes it.
        handler: () => ({ body: { address: 'bad' } })
      }
    ],
    async (app) => {
      const response = await app.inject({ method: 'GET', url: '/api/explorer/address/bad' });
      assert.equal(response.statusCode, 502);
      const payload = response.json();
      assert.equal(payload.ok, false);
      assert.match(payload.error, /did not match the expected schema/);
      assert.ok(Array.isArray(payload.issues));
    }
  );
});

test('explorer tx: happy path', async () => {
  await withGateway(
    [
      {
        method: 'GET',
        path: '/explorer/tx/deadbeef',
        handler: () => ({ body: { ok: true, txid: 'deadbeef', short_txid: 'deadbeef', risk: { risk_level: 'low' } } })
      }
    ],
    async (app) => {
      const response = await app.inject({ method: 'GET', url: '/api/explorer/tx/deadbeef' });
      assert.equal(response.statusCode, 200);
      assert.equal(response.json().txid, 'deadbeef');
    }
  );
});

test('explorer tx: not-found from node is a 200 { ok:false } body per the node contract, still validated', async () => {
  await withGateway(
    [
      {
        method: 'GET',
        path: '/explorer/tx/missing',
        handler: () => ({ body: { ok: false, txid: 'missing', error: 'transaction not found', mempool: false } })
      }
    ],
    async (app) => {
      const response = await app.inject({ method: 'GET', url: '/api/explorer/tx/missing' });
      // The gateway treats any ok:false body as an upstream error, matching the node's
      // own error-envelope convention used elsewhere (send_json({ok:false,...})).
      assert.equal(response.statusCode, 400);
      assert.match(response.json().error, /transaction not found/);
    }
  );
});

test('explorer block: proxies a numeric height id through untouched', async () => {
  await withGateway(
    [
      {
        method: 'GET',
        path: '/explorer/block/42',
        handler: () => ({ body: { ok: true, height: 42, hash: 'hash-at-42', tx_count: 1, txids: ['t1'] } })
      }
    ],
    async (app) => {
      const response = await app.inject({ method: 'GET', url: '/api/explorer/block/42' });
      assert.equal(response.statusCode, 200);
      const payload = response.json();
      assert.equal(payload.height, 42);
      assert.equal(payload.hash, 'hash-at-42');
    }
  );
});

test('explorer block: proxies a hash-string id through untouched (no height/hash guessing in the gateway)', async () => {
  await withGateway(
    [
      {
        method: 'GET',
        path: '/explorer/block/0000abc123hash',
        handler: () => ({ body: { ok: true, height: 7, hash: '0000abc123hash', tx_count: 0, txids: [] } })
      }
    ],
    async (app) => {
      const response = await app.inject({ method: 'GET', url: '/api/explorer/block/0000abc123hash' });
      assert.equal(response.statusCode, 200);
      const payload = response.json();
      assert.equal(payload.hash, '0000abc123hash');
      assert.equal(payload.height, 7);
    }
  );
});

test('explorer mempool: happy path', async () => {
  await withGateway(
    [
      {
        method: 'GET',
        path: '/explorer/mempool',
        handler: () => ({ body: { summary: { size: 1 }, transactions: [{ txid: 't1' }], count: 1, generated_at: 100 } })
      }
    ],
    async (app) => {
      const response = await app.inject({ method: 'GET', url: '/api/explorer/mempool' });
      assert.equal(response.statusCode, 200);
      assert.equal(response.json().count, 1);
    }
  );
});

test('wallet drafts: POST persists via the node and returns the real draft', async () => {
  await withGateway(
    [
      {
        method: 'POST',
        path: '/wallet/drafts',
        handler: ({ body }) => ({
          body: {
            draft_id: 'draft_123_1',
            to: body.to ?? '',
            amount: body.amount ?? '',
            fee: body.fee ?? '',
            memo: body.memo ?? '',
            status: 'draft',
            created_at: 123
          }
        })
      }
    ],
    async (app) => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/wallet/drafts',
        payload: { to: 'n1dest', amount: '1.5', fee: '0.0001' }
      });
      assert.equal(response.statusCode, 200);
      const payload = response.json();
      assert.equal(payload.draft_id, 'draft_123_1');
      assert.notEqual(payload.draft_id, 'draft-placeholder');
      assert.equal(payload.to, 'n1dest');
    }
  );
});

test('markets: list, create, order, orderbook, ticker all proxy through', async () => {
  await withGateway(
    [
      { method: 'GET', path: '/markets', handler: () => ({ body: { markets: [{ market_id: 'mkt_1' }], totals: { count: 1 }, warning: 'testnet' } }) },
      {
        method: 'POST',
        path: '/markets',
        handler: ({ body }) => ({ body: { market_id: 'mkt_new', question: body.question, status: 'open' } })
      },
      {
        method: 'POST',
        path: '/markets/mkt_1/order',
        handler: ({ body }) => ({ body: { market_id: 'mkt_1', order_id: 'ord_1', outcome: body.outcome } })
      },
      {
        method: 'GET',
        path: '/markets/mkt_1/orderbook',
        handler: () => ({ body: { market_id: 'mkt_1', bids: [[0.4, 10]], asks: [[0.6, 5]] } })
      },
      { method: 'GET', path: '/markets/mkt_1/ticker', handler: () => ({ body: { market_id: 'mkt_1', last_price: 0.5 } }) }
    ],
    async (app) => {
      const list = await app.inject({ method: 'GET', url: '/api/markets' });
      assert.equal(list.statusCode, 200);
      assert.equal(list.json().markets[0].market_id, 'mkt_1');

      const create = await app.inject({
        method: 'POST',
        url: '/api/markets',
        payload: {
          question: 'Will it rain?',
          signed_envelope: { address: 'n1a', method: 'POST', path: '/markets', body_hash: 'x'.repeat(32), timestamp: 1, nonce: 'n', signature: 's' }
        }
      });
      assert.equal(create.statusCode, 200);
      assert.equal(create.json().market_id, 'mkt_new');

      const order = await app.inject({ method: 'POST', url: '/api/markets/mkt_1/order', payload: { outcome: 'YES', side: 'buy', quantity: 1 } });
      assert.equal(order.statusCode, 200);
      assert.equal(order.json().order_id, 'ord_1');

      const orderbook = await app.inject({ method: 'GET', url: '/api/markets/mkt_1/orderbook' });
      assert.equal(orderbook.statusCode, 200);
      assert.equal(orderbook.json().bids.length, 1);

      const ticker = await app.inject({ method: 'GET', url: '/api/markets/mkt_1/ticker' });
      assert.equal(ticker.statusCode, 200);
      assert.equal(ticker.json().market_id, 'mkt_1');
    }
  );
});

test('markets: node rejects an unsigned/invalid write and the gateway surfaces that rejection', async () => {
  await withGateway(
    [
      {
        method: 'POST',
        path: '/markets/mkt_1/order',
        handler: () => ({ status: 400, body: { ok: false, error: 'signed envelope required for /markets' } })
      }
    ],
    async (app) => {
      const response = await app.inject({ method: 'POST', url: '/api/markets/mkt_1/order', payload: { outcome: 'YES', side: 'buy', quantity: 1 } });
      assert.equal(response.statusCode, 400);
      assert.match(response.json().error, /signed envelope required/);
    }
  );
});

test('release verify: happy path proxies the real checksum/tool verification', async () => {
  await withGateway(
    [
      {
        method: 'GET',
        path: '/release/verify',
        handler: () => ({
          body: {
            tools: { verify_signature: true, verify_provenance: true, generate_sbom: true },
            checksum: { provided: '', expected: '', match: null },
            commands: { signature: 'python tools/verify_signature.py <artifact> <signature>' },
            status: 'ready'
          }
        })
      }
    ],
    async (app) => {
      const response = await app.inject({ method: 'GET', url: '/api/release/verify' });
      assert.equal(response.statusCode, 200);
      assert.equal(response.json().status, 'ready');
    }
  );
});

test('gateway returns a clear error when the node is unreachable', async () => {
  const previousUrl = process.env.NETCOIN_NODE_URL;
  process.env.NETCOIN_NODE_URL = 'http://127.0.0.1:1';
  const app = createNetCoinApiServer({ logger: false });
  try {
    const response = await app.inject({ method: 'GET', url: '/api/explorer/mempool' });
    assert.equal(response.statusCode, 502);
    assert.match(response.json().error, /failed to reach netcoin node/);
  } finally {
    await app.close();
    if (previousUrl === undefined) delete process.env.NETCOIN_NODE_URL;
    else process.env.NETCOIN_NODE_URL = previousUrl;
  }
});
