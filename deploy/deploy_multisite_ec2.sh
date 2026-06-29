#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE="${1:-}"
SSH_KEY="${2:-}"
REMOTE_TMP="/tmp/netcoin-sites.tgz"
REMOTE_CONF="/tmp/netcoin.conf"
if [ -z "$REMOTE" ]; then echo "Usage: $0 ubuntu@18.220.89.128 [/path/to/key.pem]" >&2; exit 2; fi
if [ ! -d "$ROOT/sites" ]; then echo "sites/ folder not found." >&2; exit 2; fi
SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
if [ -n "$SSH_KEY" ]; then SSH_OPTS+=(-i "$SSH_KEY"); fi
cd "$ROOT"
find sites -name '._*' -delete
tar -czf /tmp/netcoin-sites.tgz sites
scp "${SSH_OPTS[@]}" /tmp/netcoin-sites.tgz "$REMOTE:$REMOTE_TMP"

# By default this deploys site files only so it does not overwrite the live
# Certbot HTTPS nginx config. To deliberately replace nginx, run with:
#   NETCOIN_DEPLOY_NGINX=1 ./deploy/deploy_multisite_ec2.sh ubuntu@18.220.89.128
if [ "${NETCOIN_DEPLOY_NGINX:-0}" = "1" ]; then
  scp "${SSH_OPTS[@]}" "$ROOT/deploy/nginx_netcoin_multisite_http.conf" "$REMOTE:$REMOTE_CONF"
fi

ssh "${SSH_OPTS[@]}" "$REMOTE" 'set -euo pipefail
  TS=$(date +%Y%m%d-%H%M%S)
  sudo mkdir -p /opt/netcoin/sites /opt/netcoin/nginx /opt/netcoin/backups/nginx /opt/netcoin/backups/sites /opt/netcoin/logs /opt/netcoin/releases /opt/netcoin/scripts /opt/netcoin/services /opt/netcoin/app
  if [ -d /opt/netcoin/sites ]; then sudo tar -czf /opt/netcoin/backups/sites/sites.$TS.tgz -C /opt/netcoin sites || true; fi
  sudo rm -rf /opt/netcoin/sites.new
  sudo mkdir -p /opt/netcoin/sites.new
  sudo tar -xzf /tmp/netcoin-sites.tgz -C /opt/netcoin/sites.new
  sudo rm -rf /opt/netcoin/sites
  sudo mv /opt/netcoin/sites.new/sites /opt/netcoin/sites
  sudo find /opt/netcoin/sites -name "._*" -delete
  sudo chown -R www-data:www-data /opt/netcoin/sites
  sudo find /opt/netcoin/sites -type d -exec chmod 755 {} \;
  sudo find /opt/netcoin/sites -type f -exec chmod 644 {} \;
  if [ "${NETCOIN_DEPLOY_NGINX:-0}" = "1" ]; then
    if ! command -v nginx >/dev/null 2>&1; then sudo apt-get update; sudo apt-get install -y nginx; fi
    sudo mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled /etc/nginx/sites-disabled
    if [ -e /etc/nginx/sites-available/netcoin.conf ]; then sudo cp /etc/nginx/sites-available/netcoin.conf /opt/netcoin/backups/nginx/netcoin.conf.$TS; fi
    sudo cp /tmp/netcoin.conf /etc/nginx/sites-available/netcoin.conf
    sudo cp /tmp/netcoin.conf /opt/netcoin/nginx/netcoin.conf
    sudo ln -sf /etc/nginx/sites-available/netcoin.conf /etc/nginx/sites-enabled/netcoin.conf
  fi
  sudo nginx -t
  sudo systemctl reload nginx || sudo systemctl restart nginx
  echo "Netcoin responsive sites deployment finished. Nginx preserved unless NETCOIN_DEPLOY_NGINX=1 was set."
'
