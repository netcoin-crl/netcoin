// Thin client for the NetCoin developer/app-layer API (/api/developer/*).
// Every reward/withdrawal write returns an *unsigned* payout plan for a
// human/wallet to review and sign — nothing here auto-broadcasts funds.
export class NetcoinDeveloperClient {
  constructor(baseUrl = "https://api.netcoin.online", { developerId = "", idempotencyKey = "" } = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.developerId = developerId;
    this.idempotencyKey = idempotencyKey;
  }

  async request(path, options = {}) {
    const res = await fetch(this.baseUrl + path, options);
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text };
    }
    if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  get(path) {
    return this.request(path);
  }

  post(path, body = {}, { idempotencyKey } = {}) {
    const headers = { "Content-Type": "application/json" };
    const key = idempotencyKey || this.idempotencyKey;
    if (key) headers["Idempotency-Key"] = key;
    const payload = this.developerId ? { developer_id: this.developerId, ...body } : body;
    return this.request(path, { method: "POST", headers, body: JSON.stringify(payload) });
  }

  // ---- Rewards ----
  sendReward({ playerId, address, amountSats, reason = "", metadata = {}, idempotencyKey } = {}) {
    return this.post(
      "/api/developer/rewards",
      { player_id: playerId, address, amount_sats: amountSats, reason, metadata },
      { idempotencyKey }
    );
  }

  sendBatchRewards({ rewards = [], reason = "", idempotencyKey } = {}) {
    return this.post("/api/developer/rewards/batch", { rewards, reason }, { idempotencyKey });
  }

  listRewards({ developerId } = {}) {
    const id = developerId || this.developerId;
    return this.get(`/api/developer/rewards${id ? `?developer_id=${encodeURIComponent(id)}` : ""}`);
  }

  // ---- Withdrawals ----
  requestWithdrawal({ playerId, address, amountSats, feeSats = 0, reason = "", idempotencyKey } = {}) {
    return this.post(
      "/api/developer/withdrawals",
      { player_id: playerId, address, amount_sats: amountSats, fee_sats: feeSats, reason },
      { idempotencyKey }
    );
  }

  listWithdrawals({ developerId } = {}) {
    const id = developerId || this.developerId;
    return this.get(`/api/developer/withdrawals${id ? `?developer_id=${encodeURIComponent(id)}` : ""}`);
  }

  // ---- Funding policy (spend limits) ----
  getFundingPolicy({ developerId } = {}) {
    const id = developerId || this.developerId;
    return this.get(`/api/developer/funding-policy${id ? `?developer_id=${encodeURIComponent(id)}` : ""}`);
  }

  setFundingPolicy({ dailyCapSats, perUserCapSats, allowlistedAddresses, paused } = {}) {
    const body = {};
    if (dailyCapSats !== undefined) body.daily_cap_sats = dailyCapSats;
    if (perUserCapSats !== undefined) body.per_user_cap_sats = perUserCapSats;
    if (allowlistedAddresses !== undefined) body.allowlisted_addresses = allowlistedAddresses;
    if (paused !== undefined) body.paused = paused;
    return this.post("/api/developer/funding-policy", body);
  }

  // ---- Payment links / checkout ----
  createPaymentLink({ address, amount, title = "" } = {}) {
    return this.post("/api/developer/payment-links", { address, amount, title });
  }

  // ---- Watch addresses / deposit detection ----
  watchAddress({ address, label = "" } = {}) {
    return this.post("/api/developer/watch-addresses", { address, label });
  }

  listDeposits({ developerId } = {}) {
    const id = developerId || this.developerId;
    return this.get(`/api/developer/deposits${id ? `?developer_id=${encodeURIComponent(id)}` : ""}`);
  }

  // ---- Webhooks ----
  registerWebhook({ url, events = ["payment.confirmed", "payment.pending", "payment.expired"], secret = "" } = {}) {
    return this.post("/api/developer/webhooks", { url, events, secret });
  }

  queueWebhookEvent({ event, payload = {} } = {}) {
    return this.post("/api/developer/webhook-events", { event, payload });
  }

  deliverWebhookEvents() {
    return this.post("/api/developer/webhook-events/deliver", {});
  }

  listDeadLetterWebhookEvents({ developerId } = {}) {
    const id = developerId || this.developerId;
    return this.get(`/api/developer/webhook-events/dead-letters${id ? `?developer_id=${encodeURIComponent(id)}` : ""}`);
  }

  retryWebhookEvent({ eventId } = {}) {
    return this.post("/api/developer/webhook-events/deliver", { event_id: eventId });
  }

  getWebhookVerifiers() {
    return this.get("/api/developer/webhook-verifiers");
  }

  // ---- Transactions / simulation ----
  buildUnsignedTransaction(payload = {}) {
    return this.post("/api/developer/transactions/build", payload);
  }

  simulateRewards(payload = {}) {
    return this.post("/api/developer/simulate/rewards", payload);
  }

  // ---- Dashboard ----
  getDashboard({ developerId } = {}) {
    const id = developerId || this.developerId;
    return this.get(`/api/developer/dashboard${id ? `?developer_id=${encodeURIComponent(id)}` : ""}`);
  }

  getConsole({ developerId } = {}) {
    const id = developerId || this.developerId;
    return this.get(`/api/developer/console${id ? `?developer_id=${encodeURIComponent(id)}` : ""}`);
  }
}

// HMAC-SHA256 webhook signature verification (Node.js only — uses node:crypto).
// Browsers should verify server-side; this helper is for a developer's own
// backend receiving NetCoin webhook deliveries.
export async function verifyNetcoinWebhook(rawBody, signatureHeader, secret) {
  const { createHmac, timingSafeEqual } = await import("node:crypto");
  const expected = "sha256=" + createHmac("sha256", secret).update(rawBody).digest("hex");
  const a = Buffer.from(String(signatureHeader || ""));
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}
