# Recommended Web Security Headers

For hosted deployments, add these headers at the reverse proxy after HTTPS is working:

```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
add_header X-Frame-Options "DENY" always;
add_header Strict-Transport-Security "max-age=15552000; includeSubDomains" always;
```

Add Content-Security-Policy per site. Do not enable HSTS until HTTPS works for every subdomain.
