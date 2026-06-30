# Hosting a Public NetCoin Seed

A NetCoin node only needs the internet **outbound** to sync and mine — that works
anywhere with zero setup. You only need to be *publicly reachable* if you want
**other nodes to connect to you** (i.e. to be a seed they bootstrap from).

For a beginner copy/paste guide, start with [INSTRUCTIONS.md#become-a-public-seed](../INSTRUCTIONS.md#become-a-public-seed).

This guide shows four ways to make a node on your own hardware publicly reachable
**without touching your router** (they also work behind CGNAT), plus the simplest
option of all (a VPS). Commands are given for **macOS, Linux, and Windows**.

| Method | Cost | Your own domain? | Carries binary P2P (TCP 18447)? | Best when |
|---|---|---|---|---|
| Cloudflare Tunnel | free | yes (e.g. `seed.netcoin.online`) | no (HTTP only) | free, on your hardware, nice URL |
| Tailscale Funnel | free | no (`*.ts.net`) | no (HTTP only) | quickest free, CGNAT-proof |
| ngrok | free tier | paid only | yes (`tcp`) | quick tests |
| Reverse SSH via VPS | ~$4/mo relay | yes | **yes** (any TCP) | full transport, rock-solid |
| VPS running the node | ~$4/mo | yes | yes | simplest of all (no tunnel) |

> Throughout, the node runs locally on `127.0.0.1:28444` (HTTP API) and the tunnel
> exposes it publicly. Tell the network where you are with `--advertise <public-url>`.
> Start the node first, in its own terminal:
>
> ```bash
> python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444
> ```

---

## Option 1 — Cloudflare Tunnel (free, your own domain)

Exposes `http://localhost:28444` at a hostname you choose (e.g.
`seed.netcoin.online`). Requires the domain's DNS to be on Cloudflare (free); if
yours is at IONOS, either move the domain's nameservers to Cloudflare, or use the
**Quick Tunnel** below for a throwaway URL with no domain.

**Install `cloudflared`:**

```bash
# macOS
brew install cloudflared
# Linux (Debian/Ubuntu)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb && sudo dpkg -i cloudflared.deb
# Windows (PowerShell)
winget install --id Cloudflare.cloudflared
```

**Quick Tunnel (no account, no domain — great for a first test):**

```bash
cloudflared tunnel --url http://localhost:28444
# prints a public https://<random>.trycloudflare.com URL -> your node
```

**Named tunnel on your domain (persistent):**

```bash
cloudflared tunnel login                              # authorize your Cloudflare zone in the browser
cloudflared tunnel create netcoin-seed                # creates the tunnel + a credentials json
cloudflared tunnel route dns netcoin-seed seed.netcoin.online
```

Create `~/.cloudflared/config.yml` (on Windows: `%USERPROFILE%\.cloudflared\config.yml`):

```yaml
tunnel: netcoin-seed
ingress:
  - hostname: seed.netcoin.online
    service: http://localhost:28444
  - service: http_status:404
```

Run it (and on Linux you can `cloudflared service install` to run at boot):

```bash
cloudflared tunnel run netcoin-seed
```

Then advertise it:

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 \
  --advertise https://seed.netcoin.online
```

---

## Option 2 — Tailscale Funnel (free, `*.ts.net`)

Exposes your node at `https://<machine>.<tailnet>.ts.net`. No domain, no router.

**Install + sign in:**

```bash
# macOS
brew install --cask tailscale         # or the Mac App Store app
# Linux
curl -fsSL https://tailscale.com/install.sh | sh
# Windows
winget install --id Tailscale.Tailscale
```

```bash
tailscale up                           # log in; assigns <machine>.<tailnet>.ts.net
```

In the Tailscale **admin console**, enable **HTTPS** and **Funnel** for your
tailnet (Funnel is off by default and must be allowed in the ACL policy). Then:

```bash
tailscale funnel 28444                 # public https://<machine>.<tailnet>.ts.net -> localhost:28444
tailscale funnel status                # shows the public URL
```

Advertise it:

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 \
  --advertise https://<machine>.<tailnet>.ts.net
```

> Funnel serves HTTPS only on ports 443/8443/10000 — fine for the node API/sync,
> but it does not carry the raw binary P2P port.

---

## Option 3 — ngrok (quick tests)

**Install + add your authtoken (free account):**

```bash
# macOS
brew install ngrok
# Linux
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list && sudo apt update && sudo apt install ngrok
# Windows
winget install --id ngrok.ngrok
```

```bash
ngrok config add-authtoken <YOUR_TOKEN>
ngrok http 28444         # -> https://<random>.ngrok-free.app  (free)
# ngrok tcp 28444        # -> tcp://<host>:<port> (raw TCP; paid plan for a stable address)
```

Advertise the URL ngrok prints. The free tier gives a new random URL each run and
has session limits — good for testing, not a permanent seed.

---

## Option 4 — Reverse SSH tunnel via a cheap VPS (full transport)

The node stays on your hardware; a tiny VPS (any provider, ~$4/mo) is just a
public doorway. This is the only no-router option that also exposes the **binary
P2P** port.

**On the VPS once:** allow remote-bound forwards in `/etc/ssh/sshd_config`:

```
GatewayPorts yes
```

then `sudo systemctl restart ssh`, and open ports 28444 (+ 18447) in the VPS firewall.

**From your home machine** (macOS/Linux, or Windows with built-in OpenSSH):

```bash
ssh -N \
  -R 0.0.0.0:28444:localhost:28444 \
  -R 0.0.0.0:18447:localhost:18447 \
  user@YOUR_VPS_IP
```

Now `http://YOUR_VPS_IP:28444` and the binary P2P `YOUR_VPS_IP:18447` reach your
home node. Advertise the VPS:

```bash
python -m netcoin --data ~/.netcoin-testnet node --host 127.0.0.1 --port 28444 \
  --advertise http://YOUR_VPS_IP:28444
```

**Keep it alive** across drops/reboots with `autossh` (macOS/Linux):

```bash
autossh -M 0 -f -N -R 0.0.0.0:28444:localhost:28444 -R 0.0.0.0:18447:localhost:18447 user@YOUR_VPS_IP
```

(or a systemd/launchd service that runs the `ssh -R` command).

---

## Option 5 — VPS running the node directly (simplest, not your hardware)

If "on my own hardware" isn't a hard requirement, a $4 VPS needs **neither** a
tunnel **nor** port forwarding — it has a real public IP. Just run the node and
open the firewall:

```bash
# on the VPS
sudo ufw allow 28444/tcp && sudo ufw allow 18447/tcp
python -m netcoin --data ~/.netcoin-testnet node --host 0.0.0.0 --port 28444 \
  --advertise http://YOUR_VPS_IP:28444
```

This is how the official `seed1/2/3` run (cloud firewall rule opens the port).

---

## Confirm you're reachable

From any other machine (or ask a seed operator to curl you):

```bash
curl -s https://seed.netcoin.online/info        # tunnel URL, or http://YOUR_VPS_IP:28444/info
```

A JSON reply with `"version"` and your height means you're a live public seed.
Then point a fresh node at yourself to prove peers can sync from you:

```bash
python -m netcoin --data /tmp/test balance --node https://seed.netcoin.online --address <ANY_ADDRESS>
```

## Dynamic IPs

Home IPs change. Tunnels (Cloudflare/Tailscale/ngrok) handle this automatically —
the public URL is stable. With the VPS/reverse-SSH options the public IP is the
VPS's, which is static. Only a *bare* home IP (port forwarding) suffers from
changes — another reason the tunnel/VPS routes are preferred.
