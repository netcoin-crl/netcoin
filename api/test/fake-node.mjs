import http from 'node:http';

/** A lightweight stand-in for the netcoin Python reference node's HTTP API.
 * Routes are matched by exact path or a predicate function so tests can drive
 * specific upstream behavior (happy path, malformed body, error envelope). */
export function startFakeNode(routes) {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url ?? '/', 'http://localhost');
    let body = '';
    req.on('data', (chunk) => {
      body += chunk;
    });
    req.on('end', () => {
      const match = routes.find(
        (route) => route.method === req.method && (typeof route.path === 'string' ? route.path === url.pathname : route.path.test(url.pathname))
      );
      if (!match) {
        res.writeHead(404, { 'content-type': 'application/json' });
        res.end(JSON.stringify({ ok: false, error: 'not found' }));
        return;
      }
      const parsedBody = body.length > 0 ? JSON.parse(body) : {};
      const result = match.handler({ url, body: parsedBody });
      const status = result.status ?? 200;
      if (result.raw !== undefined) {
        res.writeHead(status, { 'content-type': 'text/plain' });
        res.end(result.raw);
        return;
      }
      res.writeHead(status, { 'content-type': 'application/json' });
      res.end(JSON.stringify(result.body));
    });
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      resolve({ server, baseUrl: `http://127.0.0.1:${address.port}` });
    });
  });
}
