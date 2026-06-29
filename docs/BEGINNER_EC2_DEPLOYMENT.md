# Beginner EC2 Deployment Guide

This guide is for a beginner deploying NetCoin websites to one Ubuntu EC2 server.
It assumes DNS subdomains already point to the EC2 public IP.

## What you are building

One EC2 server runs Nginx. All NetCoin subdomains point to the same server IP.
Nginx reads the requested domain name and serves the matching folder.

```text
wallet.netcoin.online      -> /opt/netcoin/sites/wallet
explorer.netcoin.online    -> /opt/netcoin/sites/explorer
pay.netcoin.online         -> /opt/netcoin/sites/pay
merchant.netcoin.online    -> /opt/netcoin/sites/merchant
faucet.netcoin.online      -> /opt/netcoin/sites/faucet
community.netcoin.online   -> /opt/netcoin/sites/community
markets.netcoin.online     -> /opt/netcoin/sites/markets
docs.netcoin.online        -> /opt/netcoin/sites/docs
api.netcoin.online         -> /opt/netcoin/sites/api
status.netcoin.online      -> /opt/netcoin/sites/status
```

NetCoin API calls go to the node:

```text
/api/* -> http://127.0.0.1:28444/
```

Faucet calls go to the faucet service:

```text
/faucet/* -> http://127.0.0.1:8081/faucet
```

Do not use port `3000` for NetCoin. Port `3000` may belong to another app.

## Terminal basics

Your laptop terminal prompt may look like this:

```text
yourname@MacBookPro ~ %
```

Your EC2 terminal prompt may look like this:

```text
ubuntu@ip-172-31-37-78:~$
```

When a command says **on your laptop**, do not run it after SSH-ing into EC2.
When a command says **on EC2**, SSH in first.

To open a second terminal on macOS, press `Command + N` in Terminal.
To leave EC2, run:

```bash
exit
```

## Find your EC2 IP

AWS Console:

1. Open AWS Console.
2. Go to EC2.
3. Click Instances.
4. Click your NetCoin instance.
5. Copy Public IPv4 address.

From inside EC2:

```bash
curl -4 https://checkip.amazonaws.com
```

From your laptop:

```bash
dig wallet.netcoin.online +short
```

## DNS records

For the one-server setup, create A records:

```text
wallet      A      YOUR_EC2_PUBLIC_IP
explorer    A      YOUR_EC2_PUBLIC_IP
pay         A      YOUR_EC2_PUBLIC_IP
merchant    A      YOUR_EC2_PUBLIC_IP
faucet      A      YOUR_EC2_PUBLIC_IP
community   A      YOUR_EC2_PUBLIC_IP
markets     A      YOUR_EC2_PUBLIC_IP
docs        A      YOUR_EC2_PUBLIC_IP
api         A      YOUR_EC2_PUBLIC_IP
status      A      YOUR_EC2_PUBLIC_IP
```

Do not type `http://` or `https://` in DNS values.

Verify from your laptop:

```bash
for d in wallet explorer pay merchant faucet community markets docs api status; do
  echo "$d.netcoin.online -> $(dig +short $d.netcoin.online | tail -n1)"
done
```

## Deploy site files

Run this on your laptop:

```bash
cd ~/Downloads
rm -rf netcoin-deploy
unzip netcoin-main-responsive-desktop-ec2.zip -d netcoin-deploy
cd netcoin-deploy/netcoin-main
chmod +x deploy/deploy_multisite_ec2.sh
./deploy/deploy_multisite_ec2.sh ubuntu@YOUR_EC2_PUBLIC_IP
```

With a `.pem` key:

```bash
./deploy/deploy_multisite_ec2.sh ubuntu@YOUR_EC2_PUBLIC_IP ~/Downloads/YOUR_KEY_NAME.pem
```

## Test Nginx from EC2

SSH in:

```bash
ssh ubuntu@YOUR_EC2_PUBLIC_IP
```

Run:

```bash
sudo nginx -t
ls -la /etc/nginx/sites-enabled
```

Only one active NetCoin config should be present:

```text
netcoin.conf -> /etc/nginx/sites-available/netcoin.conf
```

Test pages:

```bash
curl -s -H "Host: wallet.netcoin.online" https://127.0.0.1/ -k | grep -i "<title"
curl -s -H "Host: explorer.netcoin.online" https://127.0.0.1/ -k | grep -i "<title"
curl -s -H "Host: merchant.netcoin.online" https://127.0.0.1/ -k | grep -i "<title"
curl -s -H "Host: pay.netcoin.online" https://127.0.0.1/ -k | grep -i "<title"
```

Test API:

```bash
curl -s -H "Host: pay.netcoin.online" https://127.0.0.1/api/latest -k | head
curl -s -H "Host: wallet.netcoin.online" https://127.0.0.1/api/fee-estimates -k | head
```

## Install HTTPS

Only include domains that already point to the EC2 IP.

```bash
sudo apt update
sudo apt install -y snapd
sudo snap install core
sudo snap refresh core
sudo apt remove -y certbot python3-certbot-nginx 2>/dev/null || true
sudo snap install --classic certbot
sudo ln -sf /snap/bin/certbot /usr/local/bin/certbot
```

Request certificates:

```bash
sudo certbot --nginx \
  -d wallet.netcoin.online \
  -d explorer.netcoin.online \
  -d pay.netcoin.online \
  -d merchant.netcoin.online \
  -d faucet.netcoin.online \
  -d community.netcoin.online \
  -d markets.netcoin.online \
  -d docs.netcoin.online \
  -d api.netcoin.online \
  -d status.netcoin.online
```

Test:

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo ss -ltnp | grep ':443'
curl -I https://wallet.netcoin.online
curl -I https://explorer.netcoin.online
curl -I https://merchant.netcoin.online
curl -I https://pay.netcoin.online
sudo certbot renew --dry-run
```

## Troubleshooting

### `Permission denied (publickey)`

You are using the wrong SSH key, or you are already inside EC2 and tried to SSH
into the same server again.

### Browser shows HTTPS error

Use HTTPS after Certbot is installed:

```text
https://wallet.netcoin.online
```

Before Certbot, only HTTP works. The wallet needs HTTPS for browser crypto.

### Wallet says `importKey` is undefined

The wallet is running on HTTP or another non-secure context. Use HTTPS.

### Pay says `Final Trading Terminal`

Nginx is proxying `/api/*` to the wrong port. NetCoin should proxy to:

```text
127.0.0.1:28444
```

not:

```text
127.0.0.1:3000
```

### Explorer or Merchant works when pasted but not when clicked

The browser may have cached old links. Open with a cache-buster:

```text
https://explorer.netcoin.online?v=300
https://merchant.netcoin.online?v=300
```

Then hard refresh.

### Duplicates in `/var/www`

The active site files should be in:

```text
/opt/netcoin/sites
```

Old `/var/www/netcoin*` folders should be archived in:

```text
/opt/netcoin/backups
```
