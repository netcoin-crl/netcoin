/* NetCoin browser wallet vault. Centralizes encrypted profile and session storage. */
"use strict";
(function () {
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  const b64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)));
  const unb64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

  function emptyProfiles() { return { active: "Default", profiles: {} }; }
  function cleanProfileName(value, fallback = "Default") {
    const name = String(value || "").trim().replace(/[\n\r\t]/g, " ").slice(0, 40);
    return name || fallback;
  }
  function loadProfiles({ profileStore, legacyStore } = {}) {
    let data;
    try { data = JSON.parse(localStorage.getItem(profileStore || "ncw.profiles.v1") || "null"); } catch { data = null; }
    if (!data || typeof data !== "object" || !data.profiles || typeof data.profiles !== "object") data = emptyProfiles();
    if (legacyStore) {
      const legacy = localStorage.getItem(legacyStore);
      if (legacy && !data.profiles.Default) {
        try { data.profiles.Default = JSON.parse(legacy); data.active = data.active || "Default"; } catch { /* ignore invalid old store */ }
      }
    }
    if (!data.active || !data.profiles[data.active]) data.active = Object.keys(data.profiles)[0] || "Default";
    return data;
  }
  function saveProfiles(data, profileStore = "ncw.profiles.v1") {
    localStorage.setItem(profileStore, JSON.stringify({ active: data.active || "Default", profiles: data.profiles || {} }));
  }
  function saveEncryptedProfile(name, blob, options = {}) {
    const data = loadProfiles(options);
    const clean = cleanProfileName(name, Object.keys(data.profiles).length ? "Wallet" : "Default");
    data.profiles[clean] = blob;
    data.active = clean;
    saveProfiles(data, options.profileStore);
    return clean;
  }
  function encryptedProfile(name, options = {}) {
    const data = loadProfiles(options);
    return data.profiles[name || data.active];
  }
  function deleteProfile(name, options = {}) {
    const data = loadProfiles(options);
    delete data.profiles[name];
    data.active = Object.keys(data.profiles).sort()[0] || "Default";
    saveProfiles(data, options.profileStore);
    return data;
  }

  function rememberUnlocked(secretType, secretValue, profile, { store = "ncw.unlockedSession.v2", ttlMs = 0, force = false, shouldRemember = false } = {}) {
    if (!force && !shouldRemember) return false;
    sessionStorage.setItem(store, JSON.stringify({ type: secretType, value: secretValue, profile, expires: Date.now() + ttlMs }));
    return true;
  }
  function clearSession(store = "ncw.unlockedSession.v2") { sessionStorage.removeItem(store); }
  function resumeSession(store = "ncw.unlockedSession.v2") {
    const raw = sessionStorage.getItem(store);
    if (!raw) return null;
    const saved = JSON.parse(raw);
    if (!saved || Number(saved.expires || 0) < Date.now()) { clearSession(store); return null; }
    return saved;
  }

  async function deriveKey(password, salt) {
    const base = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
    return crypto.subtle.deriveKey(
      { name: "PBKDF2", salt, iterations: 200000, hash: "SHA-256" },
      base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
  }
  async function encryptWalletSecret(secretType, secretValue, password) {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await deriveKey(password, salt);
    const plain = JSON.stringify({ type: secretType, value: secretValue });
    const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(plain));
    return { version: 3, kdf: "PBKDF2-SHA256", cipher: "AES-256-GCM", type: secretType, salt: b64(salt), iv: b64(iv), ct: b64(ct) };
  }
  async function decryptWalletSecret(blob, password) {
    const key = await deriveKey(password, unb64(blob.salt));
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(blob.iv) }, key, unb64(blob.ct));
    const text = dec.decode(pt);
    if (blob && Number(blob.version || 1) >= 2) {
      const parsed = JSON.parse(text);
      return { type: parsed.type || "seed", value: parsed.value || "" };
    }
    return { type: "seed", value: text };
  }
  async function encryptText(text, password) {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await deriveKey(password, salt);
    const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(text));
    return JSON.stringify({ type: "netcoin-contacts-encrypted", version: 2, kdf: "PBKDF2-SHA256", cipher: "AES-256-GCM", salt: b64(salt), iv: b64(iv), ct: b64(ct) }, null, 2);
  }
  async function decryptText(blob, password) {
    const key = await deriveKey(password, unb64(blob.salt));
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(blob.iv) }, key, unb64(blob.ct));
    return dec.decode(pt);
  }

  window.NCWVault = {
    version: 1,
    emptyProfiles,
    cleanProfileName,
    loadProfiles,
    saveProfiles,
    saveEncryptedProfile,
    encryptedProfile,
    deleteProfile,
    rememberUnlocked,
    clearSession,
    resumeSession,
    deriveKey,
    encryptWalletSecret,
    decryptWalletSecret,
    encryptText,
    decryptText,
  };
}());
