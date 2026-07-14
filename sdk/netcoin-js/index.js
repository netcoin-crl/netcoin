// Signed-envelope helpers for sensitive app-layer writes.
export async function canonicalBodyHash(payload = {}) {
  const filtered = {};
  for (const [k, v] of Object.entries(payload || {})) {
    if (["signed_envelope", "signed_request", "api_key", "admin_token"].includes(k) || k.startsWith("__netcoin_")) continue;
    filtered[k] = v;
  }
  const ordered = JSON.stringify(Object.keys(filtered).sort().reduce((acc, k) => { acc[k] = filtered[k]; return acc; }, {}));
  const bytes = new TextEncoder().encode(ordered);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function signedEnvelopeMessage(address, method, path, bodyHash, timestamp, nonce) {
  return ["NetCoin signed request", "netcoin-signed-envelope-v1", address, method.toUpperCase(), path, bodyHash, String(timestamp), nonce].join("\n");
}

export async function buildSignedEnvelope({ address, method = "POST", path, payload = {}, signer }) {
  const timestamp = Math.floor(Date.now() / 1000);
  const nonceBytes = new Uint8Array(16);
  crypto.getRandomValues(nonceBytes);
  const nonce = Array.from(nonceBytes).map((b) => b.toString(16).padStart(2, "0")).join("");
  const body_hash = await canonicalBodyHash(payload);
  const message = signedEnvelopeMessage(address, method, path, body_hash, timestamp, nonce);
  const signature = await signer(message);
  return { version: "netcoin-signed-envelope-v1", address, method: method.toUpperCase(), path, body_hash, timestamp, nonce, signature };
}

// Minimal NetCoin app-layer SDK. Works in browsers and Node 18+.
export class NetcoinClient {
  constructor(baseUrl = "") { this.baseUrl = baseUrl.replace(/\/$/, ""); }
  async request(path, options = {}) {
    const res = await fetch(this.baseUrl + path, options);
    const text = await res.text();
    let data; try { data = JSON.parse(text); } catch { data = { error: text }; }
    if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }
  get(path) { return this.request(path); }
  post(path, body) { return this.request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) }); }
  async signedPost(path, body, { address, signer }) {
    const payload = { ...(body || {}) };
    payload.signed_envelope = await buildSignedEnvelope({ address, method: "POST", path, payload, signer });
    return this.post(path, payload);
  }
  validateAddress(address) { return this.get(`/api/validate-address?address=${encodeURIComponent(address)}`); }
  createInvoice({ address, amount, memo = "", label = "", orderId = "" }) { return this.post("/api/invoices", { address, amount, memo, label, order_id: orderId }); }
  getInvoice(id) { return this.get(`/api/invoices/${encodeURIComponent(id)}`); }
  receipt(txid) { return this.get(`/api/receipt/${encodeURIComponent(txid)}`); }
  resolveUsername(username) { return this.get(`/api/usernames/${encodeURIComponent(username)}`); }
  // NET-20 style app-layer tokens
  listTokens() { return this.get("/api/tokens"); }
  createToken({ symbol, creator, name = "", decimals = 8, initialSupply = "0", maxSupply = "0", mintable = true }) {
    return this.post("/api/tokens", { symbol, creator, name: name || symbol, decimals, initial_supply: initialSupply, max_supply: maxSupply, mintable });
  }
  tokenInfo(token) { return this.get(`/api/tokens/${encodeURIComponent(token)}`); }
  tokenBalance(token, account) { return this.get(`/api/tokens/${encodeURIComponent(token)}/balance/${encodeURIComponent(account)}`); }
  mintToken(token, { minter, amount, to = "" }) { return this.post(`/api/tokens/${encodeURIComponent(token)}/mint`, { minter, amount, to: to || minter }); }
  transferToken(token, { from, to, amount }) { return this.post(`/api/tokens/${encodeURIComponent(token)}/transfer`, { from, to, amount }); }
  burnToken(token, { from, amount }) { return this.post(`/api/tokens/${encodeURIComponent(token)}/burn`, { from, amount }); }
  // Stable node API v1 helpers
  nodeInfo() { return this.get("/v1/info"); }
  nodeHealth() { return this.get("/v1/health"); }
  blockTemplate(address = "") {
    const qs = new URLSearchParams();
    if (address) qs.set("address", address);
    return this.get(`/v1/blocktemplate${qs.toString() ? "?" + qs.toString() : ""}`);
  }
  broadcastTransaction(transaction, { privateRelay = false } = {}) {
    return this.post(`/v1/tx${privateRelay ? "?private=1" : ""}`, transaction);
  }
  buildPaymentURI(address, { amount = "", label = "", message = "" } = {}) {
    const qs = new URLSearchParams();
    if (amount) qs.set("amount", amount);
    if (label) qs.set("label", label);
    if (message) qs.set("message", message);
    return `netcoin:${address}${qs.toString() ? "?" + qs.toString() : ""}`;
  }
}
