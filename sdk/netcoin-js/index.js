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
  buildPaymentURI(address, { amount = "", label = "", message = "" } = {}) {
    const qs = new URLSearchParams();
    if (amount) qs.set("amount", amount);
    if (label) qs.set("label", label);
    if (message) qs.set("message", message);
    return `netcoin:${address}${qs.toString() ? "?" + qs.toString() : ""}`;
  }
}
