# Deploy

1. `npm run build` → `public/netcoin-wallet.js`; update the SRI hashes in
   `public/wallet.html` (`openssl dgst -sha384 -binary <f> | openssl base64 -A`).
2. Copy `public/{wallet.html→index.html, wallet-app.js, netcoin-wallet.js}` to
   `/var/www/netcoin-wallet/` on the node host.
3. Install `deploy/nginx-wallet.conf` to `/etc/nginx/sites-available/netcoin-wallet`,
   symlink into `sites-enabled`, `nginx -t && systemctl reload nginx`.
4. DNS: `wallet.netcoin.online A <host-ip>`.
5. `certbot --nginx -d wallet.netcoin.online` (issues cert + HTTP→HTTPS redirect).
