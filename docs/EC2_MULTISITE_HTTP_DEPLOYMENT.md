# EC2 multisite HTTPS deployment

NetCoin uses one EC2 server and one IP address, with Nginx routing by host name.
For the full beginner copy/paste guide, see
[BEGINNER_EC2_DEPLOYMENT.md](BEGINNER_EC2_DEPLOYMENT.md).

Active server layout:

```text
/opt/netcoin/sites/wallet
/opt/netcoin/sites/explorer
/opt/netcoin/sites/pay
/opt/netcoin/sites/merchant
/opt/netcoin/sites/faucet
/opt/netcoin/sites/community
/opt/netcoin/sites/markets
/opt/netcoin/sites/docs
/opt/netcoin/sites/api
/opt/netcoin/sites/status
/opt/netcoin/nginx/netcoin.conf
/opt/netcoin/backups/
```

Nginx rules:

```text
/api/*          -> http://127.0.0.1:28444/
/faucet/status  -> http://127.0.0.1:8081/status
/faucet/history -> http://127.0.0.1:8081/history
/faucet/queue   -> http://127.0.0.1:8081/queue
/faucet         -> http://127.0.0.1:8081/faucet
```

Do not use port `3000` for NetCoin. Port `3000` may belong to another app.

Deploy site files only:

```bash
./deploy/deploy_multisite_ec2.sh ubuntu@18.220.89.128
```

Deploy site files and intentionally replace the Nginx config:

```bash
NETCOIN_DEPLOY_NGINX=1 ./deploy/deploy_multisite_ec2.sh ubuntu@18.220.89.128
```

The default deploy preserves the live Certbot HTTPS config. That is intentional.

Wallet encryption requires HTTPS because browser WebCrypto is only available in
secure contexts. HTTP is fine for page/routing tests, but not final wallet use.

Check active config:

```bash
ls -la /etc/nginx/sites-enabled
sudo grep -nE "root|map|server_name|proxy_pass|/opt/netcoin/sites|/var/www" /etc/nginx/sites-enabled/netcoin.conf
```

Test sites:

```bash
curl -s -H "Host: wallet.netcoin.online" https://127.0.0.1/ -k | grep -i "<title"
curl -s -H "Host: explorer.netcoin.online" https://127.0.0.1/ -k | grep -i "<title"
curl -s -H "Host: merchant.netcoin.online" https://127.0.0.1/ -k | grep -i "<title"
curl -s -H "Host: pay.netcoin.online" https://127.0.0.1/api/latest -k | head
```
