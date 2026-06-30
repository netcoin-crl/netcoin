# Nginx security header snippet

Use this with HTTPS after validating that all sites load correctly. Adjust CSP only if a page needs more sources.

```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
add_header X-Frame-Options "DENY" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

limit_req_zone $binary_remote_addr zone=netcoin_api:10m rate=10r/s;
location /api/ {
    limit_req zone=netcoin_api burst=30 nodelay;
    proxy_pass http://127.0.0.1:28444/;
}
```

Do not enable HSTS until HTTPS works reliably for every subdomain.
