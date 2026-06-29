# Responsive desktop layout update

This release keeps the mobile-friendly stacked layout, but expands NetCoin sites on laptops and desktop screens.

## Breakpoints

- Under 760px: compact mobile layout with horizontally scrollable top navigation.
- 900px and up: wider containers, larger cards, and multi-column dashboard sections.
- 1180px and up: full laptop/desktop width, larger tables, and denser card grids.

## Deployment note

The deployment script now preserves the live Certbot HTTPS Nginx configuration by default. It deploys `/opt/netcoin/sites` only. Set `NETCOIN_DEPLOY_NGINX=1` only if you intentionally want to replace the Nginx config.
