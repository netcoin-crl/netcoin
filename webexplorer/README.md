# NetCoin Explorer (live SPA)

A dynamic, read-only block explorer that queries the node through a same-origin
`/api/*` relay (no regeneration, always current). Replaces the old static
pre-rendered site.

- `public/index.html` + `public/explorer-app.js` — the SPA (strict CSP, no inline JS).
- `tools/devserver.py` — local dev only: serves `public/` and proxies `/api` to a node.

## Deploy (on the node host, nginx)
1. Copy `public/{index.html,explorer-app.js}` → `/var/www/netcoin-explorer/`.
2. In the explorer nginx vhost add (keeps `/faucet`):
   ```nginx
   location /api/ {
       proxy_pass http://127.0.0.1:28444/;
       proxy_set_header Host $host;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
   }
   ```
3. `nginx -t && systemctl reload nginx`.
