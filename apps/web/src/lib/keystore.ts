/**
 * EVA-003 PR5 — browser key custody without a plaintext private key.
 *
 * The identity key lives as a NON-EXTRACTABLE WebCrypto Ed25519 CryptoKey in
 * IndexedDB; page scripts (including an XSS) can use it to sign while the page
 * is open but can never read or exfiltrate the key bytes. Compass gets its own
 * non-extractable AES-GCM key instead of deriving one from the identity key.
 *
 * Legacy users (plaintext hex in localStorage) are migrated in place. The
 * plaintext copy is removed ONLY after: import → local sign/verify self-test →
 * persist → re-read from IndexedDB → server-side signature check that the
 * re-read key is the identity's current ACTIVE key → Compass re-encrypted.
 * Any failure keeps the legacy key and the migration is retried on a later
 * visit, so a user's identity is never lost. Browsers without Ed25519
 * WebCrypto keep the legacy path (D2: QR/app login remains available).
 */
import { ed25519 } from "@noble/curves/ed25519.js";

import { bytesToHex, hexToBytes, loadKeypair, loadNullifier, signPayload } from "./crypto";
import { reencryptLegacyCompassBlob } from "./compass/storage";

export const LEGACY_PRIVATE_KEY = "ekklesia_private_key";
export const LEGACY_PUBLIC_KEY = "ekklesia_public_key";
/** Set once the identity key is held in WebCrypto; lets sync UI checks see a signer. */
export const KEY_CUSTODY_MARKER = "ekklesia_key_custody";

const IDENTITY_RECORD = "identity";
const COMPASS_RECORD = "compass";
const PKCS8_ED25519_PREFIX = "302e020100300506032b657004220420";
const HEX32 = /^[0-9a-f]{64}$/;

// ─── Storage backend (IndexedDB; injectable for tests) ──────────────────────

export interface KeyRecordStore {
  get<T>(id: string): Promise<T | undefined>;
  put<T>(id: string, value: T): Promise<void>;
}

interface IdentityRecord {
  privateKey: CryptoKey;
  publicKeyHex: string;
  nullifier: string;
}

function indexedDbStore(): KeyRecordStore {
  const open = () =>
    new Promise<IDBDatabase>((resolve, reject) => {
      const req = indexedDB.open("ekklesia-keystore", 1);
      req.onupgradeneeded = () => req.result.createObjectStore("keys");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  const run = async <T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest): Promise<T> => {
    const db = await open();
    try {
      return await new Promise<T>((resolve, reject) => {
        const tx = db.transaction("keys", mode);
        const req = fn(tx.objectStore("keys"));
        tx.oncomplete = () => resolve(req.result as T);
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error);
      });
    } finally {
      db.close();
    }
  };
  return {
    get: <T>(id: string) => run<T | undefined>("readonly", (s) => s.get(id)),
    put: async <T>(id: string, value: T) => {
      await run("readwrite", (s) => s.put(value, id));
    },
  };
}

let backend: KeyRecordStore | null = null;
function store(): KeyRecordStore {
  backend ??= indexedDbStore();
  return backend;
}

export function setKeyRecordStoreForTests(next: KeyRecordStore | null): void {
  backend = next;
}

// ─── Signing ────────────────────────────────────────────────────────────────

export interface WebSigner {
  publicKeyHex: string;
  nullifier: string;
  custody: "webcrypto" | "legacy";
  sign(payload: string): Promise<string>;
}

async function webCryptoSign(key: CryptoKey, payload: string): Promise<string> {
  const sig = await crypto.subtle.sign({ name: "Ed25519" }, key, new TextEncoder().encode(payload));
  return bytesToHex(new Uint8Array(sig));
}

async function loadIdentityRecord(): Promise<IdentityRecord | null> {
  if (typeof indexedDB === "undefined" && backend === null) return null;
  try {
    const rec = await store().get<IdentityRecord>(IDENTITY_RECORD);
    if (!rec || !(rec.privateKey instanceof CryptoKey) || !HEX32.test(rec.publicKeyHex) || !rec.nullifier) return null;
    return rec;
  } catch {
    return null;
  }
}

/** The signer for this browser: WebCrypto custody first, legacy plaintext as fallback. */
export async function getSigner(): Promise<WebSigner | null> {
  const rec = await loadIdentityRecord();
  if (rec) {
    return {
      publicKeyHex: rec.publicKeyHex,
      nullifier: rec.nullifier,
      custody: "webcrypto",
      sign: (payload) => webCryptoSign(rec.privateKey, payload),
    };
  }
  let legacy: ReturnType<typeof loadKeypair> = null;
  let nullifier: string | null = null;
  try {
    legacy = loadKeypair();
    nullifier = loadNullifier();
  } catch {
    return null; // storage blocked
  }
  if (!legacy || !nullifier) return null;
  const privateKeyHex = legacy.privateKeyHex;
  return {
    publicKeyHex: legacy.publicKeyHex,
    nullifier,
    custody: "legacy",
    sign: async (payload) => signPayload(privateKeyHex, payload),
  };
}

/** Synchronous hint for UI state: a key (legacy or WebCrypto) is present. */
export function hasLocalSignerHint(): boolean {
  try {
    return Boolean(localStorage.getItem(LEGACY_PUBLIC_KEY))
      && (Boolean(localStorage.getItem(LEGACY_PRIVATE_KEY)) || localStorage.getItem(KEY_CUSTODY_MARKER) === "webcrypto");
  } catch {
    return false;
  }
}

/** Compass AES key (non-extractable), present once the identity is migrated. */
export async function getCompassKey(): Promise<CryptoKey | null> {
  if (typeof indexedDB === "undefined" && backend === null) return null;
  try {
    const key = await store().get<CryptoKey>(COMPASS_RECORD);
    return key instanceof CryptoKey ? key : null;
  } catch {
    return null;
  }
}

// ─── Migration ──────────────────────────────────────────────────────────────

export type MigrationResult =
  | "migrated"
  | "not_needed"
  | "no_legacy"
  | "unsupported"
  | "key_not_current"
  | "retry_later";

export interface MigrationDeps {
  apiUrl: string;
  fetchImpl: typeof fetch;
  now: () => number;
  timeoutMs: number;
}

const DEFAULT_DEPS: MigrationDeps = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL || "https://api.ekklesia.gr",
  fetchImpl: (...args) => fetch(...args),
  now: () => Date.now(),
  timeoutMs: 15_000,
};

export function identityKeyCheckMessage(nullifierHash: string, publicKeyHex: string, timestampMs: number): string {
  // Must match apps/api/routers/identity.py::identity_key_check_message.
  return `ekklesia:identity-key-check:v1:${nullifierHash}:${publicKeyHex}:${timestampMs}`;
}

export async function supportsNonExtractableEd25519(): Promise<boolean> {
  try {
    if (!globalThis.crypto?.subtle) return false;
    const pair = (await crypto.subtle.generateKey({ name: "Ed25519" }, false, ["sign", "verify"])) as CryptoKeyPair;
    return pair.privateKey.extractable === false;
  } catch {
    return false;
  }
}

async function fetchJson(deps: MigrationDeps, url: string, init?: RequestInit): Promise<{ status: number; body: unknown }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), deps.timeoutMs);
  try {
    const res = await deps.fetchImpl(url, { ...init, signal: controller.signal });
    const text = await res.text();
    let body: unknown = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = null;
    }
    return { status: res.status, body };
  } finally {
    clearTimeout(timer);
  }
}

async function serverConfirmsKey(
  deps: MigrationDeps,
  key: CryptoKey,
  nullifier: string,
  publicKeyHex: string,
): Promise<"ok" | "mismatch" | "unavailable"> {
  try {
    const ts = deps.now();
    const signature = await webCryptoSign(key, identityKeyCheckMessage(nullifier, publicKeyHex, ts));
    const res = await fetchJson(deps, `${deps.apiUrl}/api/v2/identity/key-check`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nullifier_hash: nullifier, public_key_hex: publicKeyHex, timestamp_ms: ts, signature_hex: signature }),
    });
    if (res.status === 200 && (res.body as { ok?: unknown } | null)?.ok === true) return "ok";
    if (res.status === 409) return "mismatch";
    return "unavailable";
  } catch {
    return "unavailable";
  }
}

async function selfTest(key: CryptoKey, publicKeyHex: string): Promise<boolean> {
  try {
    const probe = `ekklesia:keystore-self-test:${crypto.getRandomValues(new Uint32Array(1))[0]}`;
    const sig = await webCryptoSign(key, probe);
    return ed25519.verify(hexToBytes(sig), new TextEncoder().encode(probe), hexToBytes(publicKeyHex));
  } catch {
    return false;
  }
}

async function serverSupportsKeyCheck(deps: MigrationDeps): Promise<boolean | null> {
  try {
    const res = await fetchJson(deps, `${deps.apiUrl}/api/v1/app/version`);
    if (res.status !== 200) return null;
    return (res.body as { features?: { identity_key_check?: unknown } } | null)?.features?.identity_key_check === true;
  } catch {
    return null;
  }
}

let migrationInFlight: Promise<MigrationResult> | null = null;

/** Idempotent; never concurrent within a page. Safe to call on every page load. */
export function migrateLegacyWebKey(deps: MigrationDeps = DEFAULT_DEPS): Promise<MigrationResult> {
  migrationInFlight ??= migrate(deps).catch(() => "retry_later" as const).finally(() => {
    migrationInFlight = null;
  });
  return migrationInFlight;
}

async function migrate(deps: MigrationDeps): Promise<MigrationResult> {
  if (typeof window === "undefined") return "not_needed";
  let legacy: ReturnType<typeof loadKeypair> = null;
  let nullifier: string | null = null;
  try {
    legacy = loadKeypair();
    nullifier = loadNullifier();
  } catch {
    return "retry_later";
  }
  if (!legacy) return (await loadIdentityRecord()) ? "not_needed" : "no_legacy";
  if (!nullifier || !HEX32.test(legacy.privateKeyHex) || !HEX32.test(legacy.publicKeyHex)) return "retry_later";
  if (!(await supportsNonExtractableEd25519())) return "unsupported";

  const supported = await serverSupportsKeyCheck(deps);
  if (supported === null) return "retry_later";
  if (!supported) return "unsupported";

  // 1. Import the legacy seed as a non-extractable key and self-test it.
  let key: CryptoKey;
  try {
    key = await crypto.subtle.importKey(
      "pkcs8",
      hexToBytes(PKCS8_ED25519_PREFIX + legacy.privateKeyHex).buffer as ArrayBuffer,
      { name: "Ed25519" },
      false,
      ["sign"],
    );
  } catch {
    return "unsupported";
  }
  if (key.extractable || !(await selfTest(key, legacy.publicKeyHex))) return "retry_later";

  // 2. Compass key: reuse (interrupted earlier run) or create, non-extractable.
  let compassKey = await getCompassKey();
  if (!compassKey) {
    compassKey = (await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"])) as CryptoKey;
    await store().put(COMPASS_RECORD, compassKey);
    compassKey = await getCompassKey();
    if (!compassKey) return "retry_later";
  }

  // 3. Persist the identity key and read it back (round-trip through IndexedDB).
  await store().put<IdentityRecord>(IDENTITY_RECORD, { privateKey: key, publicKeyHex: legacy.publicKeyHex, nullifier });
  const stored = await loadIdentityRecord();
  if (!stored || stored.publicKeyHex !== legacy.publicKeyHex || stored.nullifier !== nullifier) return "retry_later";
  if (stored.privateKey.extractable || !(await selfTest(stored.privateKey, legacy.publicKeyHex))) return "retry_later";

  // 4. The server confirms that the re-read key is the identity's current key.
  const confirmed = await serverConfirmsKey(deps, stored.privateKey, nullifier, legacy.publicKeyHex);
  if (confirmed === "mismatch") return "key_not_current"; // keep everything; the server holds another key
  if (confirmed !== "ok") return "retry_later";

  // 5. Compass ciphertext moves to the new key (only replaced on success).
  if (!(await reencryptLegacyCompassBlob(legacy.privateKeyHex, compassKey))) return "retry_later";

  // 6. Only now: drop the plaintext private key (public key + nullifier stay).
  try {
    localStorage.setItem(KEY_CUSTODY_MARKER, "webcrypto");
    if (localStorage.getItem(LEGACY_PRIVATE_KEY) === legacy.privateKeyHex) {
      localStorage.removeItem(LEGACY_PRIVATE_KEY);
    }
  } catch {
    return "retry_later";
  }
  return "migrated";
}
