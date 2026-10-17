/**
 * EVA-003 PR5/PR6 — browser key custody and fresh device-key rotation.
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
 * Feature flags gate starting a fresh rotation; journal recovery is independent
 * of them. Strict IDB completion precedes server mutation and journal cleanup.
 */
import { ed25519 } from "@noble/curves/ed25519.js";

import { bytesToHex, hexToBytes, loadKeypair, loadNullifier, signPayload } from "./crypto";
import { reencryptLegacyCompassBlob } from "./compass/storage";
import { REQUEST_TIMEOUT_MS, withRequestDeadline } from "./request-deadline";

export const LEGACY_PRIVATE_KEY = "ekklesia_private_key";
export const LEGACY_PUBLIC_KEY = "ekklesia_public_key";
/** Set once the identity key is held in WebCrypto; lets sync UI checks see a signer. */
export const KEY_CUSTODY_MARKER = "ekklesia_key_custody";

const IDENTITY_RECORD = "identity";
const PENDING_IDENTITY_RECORD = "identity_pending";
const PENDING_ROTATION_RECORD = "pending-rotation";
/** Exclusive for migration/rotation/Compass writes; shared for signed requests. */
export const KEYSTORE_LOCK = "ekklesia-keystore";
const COMPASS_RECORD = "compass";
const PKCS8_ED25519_PREFIX = "302e020100300506032b657004220420";
const HEX32 = /^[0-9a-f]{64}$/;

// ─── Storage backend (IndexedDB; injectable for tests) ──────────────────────

export interface KeyRecordStore {
  get<T>(id: string): Promise<T | undefined>;
  put<T>(id: string, value: T): Promise<void>;
  delete(id: string): Promise<void>;
}

interface IdentityRecord {
  privateKey: CryptoKey;
  publicKeyHex: string;
  nullifier: string;
  /** Set only after a fresh, browser-generated key was confirmed by the API. */
  origin?: "device";
}

interface PendingRotation extends IdentityRecord {
  oldPublicKeyHex: string;
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
        const tx = mode === "readwrite"
          ? db.transaction("keys", mode, { durability: "strict" })
          : db.transaction("keys", mode);
        // Older engines may accept but ignore transaction options. Fail closed:
        // keep the old key/journal and never mutate the server without a flush.
        if (mode === "readwrite" && tx.durability !== "strict") {
          tx.abort();
          reject(new Error("Strict IndexedDB durability unavailable"));
          return;
        }
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
    delete: async (id: string) => {
      await run("readwrite", (s) => s.delete(id));
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

type LockManagerLike = { request<T>(name: string, options: { mode: "shared" | "exclusive"; signal?: AbortSignal }, cb: () => Promise<T>): Promise<T> };
let lockOverride: LockManagerLike | null | undefined;

function lockManager(): LockManagerLike | null {
  if (lockOverride !== undefined) return lockOverride;
  const locks = (globalThis.navigator as { locks?: LockManagerLike } | undefined)?.locks;
  return locks && typeof locks.request === "function" ? locks : null;
}

export function setLockManagerForTests(next: LockManagerLike | null | undefined): void {
  lockOverride = next;
}

/**
 * Run fn under the cross-tab keystore lock. Returns null if the browser has no
 * Web Locks (callers then keep the legacy behaviour).
 */
export async function withKeystoreLock<T>(fn: () => Promise<T>): Promise<{ value: T } | null> {
  const locks = lockManager();
  if (!locks) return null;
  return locks.request(KEYSTORE_LOCK, { mode: "exclusive" }, async () => ({ value: await fn() }));
}

let persistenceRequest: Promise<void> | undefined;

/** Best effort, once per page after finding a key; record only the outcome. */
function requestPersistentStorage(): void {
  persistenceRequest ??= (async () => {
    let outcome: "granted" | "denied" | "unsupported" | "error" = "unsupported";
    try {
      const storage = globalThis.navigator?.storage;
      if (typeof storage?.persist === "function") outcome = await storage.persist() ? "granted" : "denied";
    } catch {
      outcome = "error";
    }
    try { localStorage.setItem("ekklesia_storage_persistence", outcome); } catch { /* best effort */ }
  })();
}

// ─── Signing ────────────────────────────────────────────────────────────────

export interface WebSigner {
  publicKeyHex: string;
  /** Needed for votes/relevance; SSO signs with the key pair alone. */
  nullifier: string | null;
  custody: "webcrypto" | "legacy";
  sign(payload: string): Promise<string>;
}

async function webCryptoSign(key: CryptoKey, payload: string): Promise<string> {
  const sig = await crypto.subtle.sign({ name: "Ed25519" }, key, new TextEncoder().encode(payload));
  return bytesToHex(new Uint8Array(sig));
}

async function loadIdentityRecord(id: string = IDENTITY_RECORD): Promise<IdentityRecord | null> {
  if (typeof indexedDB === "undefined" && backend === null) return null;
  try {
    const rec = await store().get<IdentityRecord>(id);
    if (!rec || !(rec.privateKey instanceof CryptoKey) || !HEX32.test(rec.publicKeyHex) || !rec.nullifier) return null;
    return rec;
  } catch {
    return null;
  }
}

/** The signer for this browser: WebCrypto custody first, legacy plaintext as fallback. */
function readLegacy(strict = false): { keypair: ReturnType<typeof loadKeypair>; nullifier: string | null } {
  try {
    return { keypair: loadKeypair(), nullifier: loadNullifier() };
  } catch (error) {
    if (strict) throw error;
    return { keypair: null, nullifier: null }; // storage blocked
  }
}

/** Key snapshot. Application requests must use withSigner through submission. */
export async function getSigner(): Promise<WebSigner | null> {
  const rec = await loadIdentityRecord();
  if (rec) {
    requestPersistentStorage();
    return {
      publicKeyHex: rec.publicKeyHex,
      nullifier: rec.nullifier,
      custody: "webcrypto",
      sign: async (payload) => {
        try {
          return await webCryptoSign(rec.privateKey, payload);
        } catch (error) {
          // A still-present legacy copy of the SAME key keeps signing working.
          const legacy = readLegacy().keypair;
          if (legacy && legacy.publicKeyHex === rec.publicKeyHex) return signPayload(legacy.privateKeyHex, payload);
          throw error;
        }
      },
    };
  }
  const { keypair: legacy, nullifier } = readLegacy();
  if (!legacy) return null;
  requestPersistentStorage();
  const privateKeyHex = legacy.privateKeyHex;
  return {
    publicKeyHex: legacy.publicKeyHex,
    nullifier,
    custody: "legacy",
    sign: async (payload) => signPayload(privateKeyHex, payload),
  };
}

/**
 * Acquire, sign and submit inside this callback; never retain its signer.
 * The signal cancels queued acquisition; submit must bound its network I/O.
 */
export async function withSigner<T>(submit: (signer: WebSigner | null) => Promise<T>, signal?: AbortSignal): Promise<T> {
  signal?.throwIfAborted();
  const run = async () => {
    signal?.throwIfAborted();
    const signer = await getSigner();
    signal?.throwIfAborted();
    return submit(signer);
  };
  const locks = lockManager();
  // Rotation/migration cannot run without Web Locks, so legacy signing is safe.
  return locks ? locks.request(KEYSTORE_LOCK, { mode: "shared", signal }, run) : run();
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
  try {
    return await readCompassKeyStrict();
  } catch {
    return null;
  }
}

/** Like getCompassKey, but a failed read THROWS instead of looking like "absent". */
export async function readCompassKeyStrict(): Promise<CryptoKey | null> {
  if (typeof indexedDB === "undefined" && backend === null) return null;
  const key = await store().get<CryptoKey>(COMPASS_RECORD);
  return key instanceof CryptoKey ? key : null;
}

/** Legacy key access stays inside the keystore; migrated Compass uses its own AES key. */
export async function readCompassKeys(): Promise<import("./compass/storage").CompassKeys> {
  const aesKey = await readCompassKeyStrict(); // never hide an operational read failure
  return { aesKey, legacyPrivateKeyHex: readLegacy().keypair?.privateKeyHex ?? null };
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
  timeoutMs: REQUEST_TIMEOUT_MS,
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

async function fetchJson(deps: MigrationDeps, url: string, init?: RequestInit): Promise<{ status: number; body: unknown; headers: Headers }> {
  return withRequestDeadline(async (signal) => {
    const res = await deps.fetchImpl(url, { ...init, signal });
    const text = await res.text();
    let body: unknown = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = null;
    }
    return { status: res.status, body, headers: res.headers };
  }, { timeoutMs: deps.timeoutMs });
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
    if (res.status === 404) {
      // Signed vote status verifies the ACTIVE identity key independently of
      // identity feature flags. Discover a real public bill; never trust a 404
      // (which could equally mean the verification route itself is disabled).
      const bills = await fetchJson(deps, `${deps.apiUrl}/api/v1/bills?limit=1`, { cache: "no-store" });
      const billId = bills.status === 200 && Array.isArray(bills.body) ? bills.body[0]?.id : null;
      if (typeof billId !== "string" || !billId) return "unavailable";
      const timestamp = deps.now();
      const sig = await webCryptoSign(key, `vote-status-read:v1:${JSON.stringify([billId, nullifier, timestamp])}`);
      const status = await fetchJson(deps, `${deps.apiUrl}/api/v1/vote/${encodeURIComponent(billId)}/status`, {
        method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nullifier_hash: nullifier, timestamp_ms: timestamp, signature_hex: sig }),
      });
      if (status.status === 200 && status.headers.get("X-Vote-Read-Integrity") === "signed"
        && (status.body as { bill_id?: unknown } | null)?.bill_id === billId) return "ok";
    }
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

/**
 * Idempotent; never concurrent within a page, and serialised across tabs by
 * the Web Lock (state is re-read inside it). Safe to call on every page load.
 */
export function migrateLegacyWebKey(deps: MigrationDeps = DEFAULT_DEPS): Promise<MigrationResult> {
  migrationInFlight ??= (async () => {
    if (typeof window === "undefined") return "not_needed" as const;
    const locked = await withKeystoreLock(() => migrate(deps));
    if (locked) return locked.value;
    if ((typeof indexedDB !== "undefined" || backend !== null)
      && await readRotationIdentityStrict(PENDING_ROTATION_RECORD)) return "retry_later" as const;
    return "unsupported" as const; // no Web Locks: stay on legacy
  })()
    .catch(() => "retry_later" as const)
    .finally(() => {
      migrationInFlight = null;
    });
  return migrationInFlight;
}

async function migrate(deps: MigrationDeps): Promise<MigrationResult> {
  // Runs under KEYSTORE_LOCK: another tab may have finished meanwhile.
  const { keypair: legacy, nullifier } = readLegacy(true);
  if (!legacy) {
    // Operational failures/corrupt records must reach the retry_later boundary.
    const current = await readRotationIdentityStrict(IDENTITY_RECORD);
    const pending = await readRotationIdentityStrict(PENDING_ROTATION_RECORD);
    if (current || pending) { requestPersistentStorage(); return "not_needed"; }
    return "no_legacy";
  }
  requestPersistentStorage();
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

  // 2. Compass key: get-or-create under the lock, non-extractable. A failed
  //    read aborts (it must never be mistaken for "absent" and overwritten).
  let compassKey: CryptoKey | null;
  try {
    compassKey = await readCompassKeyStrict();
  } catch {
    return "retry_later";
  }
  if (!compassKey) {
    await store().put(COMPASS_RECORD, await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]));
    compassKey = await getCompassKey();
    if (!compassKey) return "retry_later";
  }

  // 3. Persist as PENDING and read it back; signers never see it.
  const record: IdentityRecord = { privateKey: key, publicKeyHex: legacy.publicKeyHex, nullifier };
  await store().put<IdentityRecord>(PENDING_IDENTITY_RECORD, record);
  const pending = await loadIdentityRecord(PENDING_IDENTITY_RECORD);
  if (!pending || pending.publicKeyHex !== legacy.publicKeyHex || pending.nullifier !== nullifier) return "retry_later";
  if (pending.privateKey.extractable || !(await selfTest(pending.privateKey, legacy.publicKeyHex))) return "retry_later";

  // 4. The server confirms that the re-read key is the identity's current key.
  const confirmed = await serverConfirmsKey(deps, pending.privateKey, nullifier, legacy.publicKeyHex);
  if (confirmed === "mismatch") return "key_not_current"; // keep everything; the server holds another key
  if (confirmed !== "ok") return "retry_later";

  // 5. Publish the validated key, re-read and re-test; roll back on failure.
  await store().put<IdentityRecord>(IDENTITY_RECORD, { ...record, privateKey: pending.privateKey });
  const published = await loadIdentityRecord();
  if (!published || published.publicKeyHex !== legacy.publicKeyHex || !(await selfTest(published.privateKey, legacy.publicKeyHex))) {
    await store().delete(IDENTITY_RECORD).catch(() => undefined);
    return "retry_later";
  }
  await store().delete(PENDING_IDENTITY_RECORD).catch(() => undefined);

  // 6. Compass ciphertext moves to the new key (only replaced on success).
  if (!(await reencryptLegacyCompassBlob(legacy.privateKeyHex, compassKey))) return "retry_later";

  // 7. Only now: drop the plaintext private key (public key + nullifier stay).
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

// ─── Fresh device key rotation (EVA-003 PR6) ────────────────────────────────

export type RotationResult = "rotated" | "already_rotated" | "not_needed" | "unsupported" | "conflict" | "retry_later";

export function identityRotateMessage(nullifier: string, oldPublicKeyHex: string, newPublicKeyHex: string, timestampMs: number): string {
  return `ekklesia:identity-rotate:v1:${nullifier}:${oldPublicKeyHex}:${newPublicKeyHex}:${timestampMs}`;
}

/** Rotation must distinguish an absent slot from an unreadable/corrupt one. */
async function readRotationIdentityStrict(id: string): Promise<IdentityRecord | undefined> {
  const rec = await store().get<IdentityRecord>(id);
  if (rec === undefined) return undefined;
  if (!rec || !(rec.privateKey instanceof CryptoKey) || rec.privateKey.extractable
    || rec.privateKey.type !== "private" || rec.privateKey.algorithm.name !== "Ed25519"
    || !HEX32.test(rec.publicKeyHex) || !HEX32.test(rec.nullifier)) {
    throw new Error("Invalid identity record");
  }
  return rec;
}

async function promoteRotation(deps: MigrationDeps, staged: PendingRotation): Promise<RotationResult> {
  // key-check proves both possession and ACTIVE status using the staged key.
  const confirmed = await serverConfirmsKey(deps, staged.privateKey, staged.nullifier, staged.publicKeyHex);
  if (confirmed !== "ok") return confirmed === "mismatch" ? "conflict" : "retry_later";

  return publishRotation(staged);
}

async function publishRotation(staged: PendingRotation): Promise<RotationResult> {
  // One IDB transaction replaces the active record (and therefore the old
  // private key). The journal survives until re-read/self-test + hint cleanup.
  await store().put<IdentityRecord>(IDENTITY_RECORD, {
    privateKey: staged.privateKey,
    publicKeyHex: staged.publicKeyHex,
    nullifier: staged.nullifier,
    origin: "device",
  });
  const published = await readRotationIdentityStrict(IDENTITY_RECORD);
  if (!published || published.publicKeyHex !== staged.publicKeyHex || published.nullifier !== staged.nullifier
    || published.origin !== "device" || !(await selfTest(published.privateKey, published.publicKeyHex))) return "retry_later";

  // An interrupted PR5 cleanup may have left another copy of the old key.
  const migrationPending = await readRotationIdentityStrict(PENDING_IDENTITY_RECORD);
  if (migrationPending?.nullifier === staged.nullifier && migrationPending.publicKeyHex === staged.oldPublicKeyHex) {
    await store().delete(PENDING_IDENTITY_RECORD);
  }
  localStorage.setItem(LEGACY_PUBLIC_KEY, published.publicKeyHex);
  localStorage.setItem(KEY_CUSTODY_MARKER, "webcrypto");
  await store().delete(PENDING_ROTATION_RECORD); // last: any earlier interruption rolls forward
  return "rotated";
}

async function rotateMigratedKey(deps: MigrationDeps): Promise<RotationResult> {
  // All reads, staging, API calls and promotion run inside KEYSTORE_LOCK.
  const pending = await readRotationIdentityStrict(PENDING_ROTATION_RECORD) as PendingRotation | undefined;
  const current = await readRotationIdentityStrict(IDENTITY_RECORD);
  if (current || pending) requestPersistentStorage();
  if (pending && (!HEX32.test(pending.oldPublicKeyHex)
    || pending.publicKeyHex === pending.oldPublicKeyHex
    || (current && (pending.nullifier !== current.nullifier
      || (pending.oldPublicKeyHex !== current.publicKeyHex && pending.publicKeyHex !== current.publicKeyHex))))) return "conflict";
  if (pending) {
    if (!(await selfTest(pending.privateKey, pending.publicKeyHex)) || !(await readCompassKeyStrict())) return "retry_later";
    // Recovery is a read + local commit, regardless of feature flags/version
    // availability. A lost rotate response never requires another server swap.
    const confirmed = await serverConfirmsKey(deps, pending.privateKey, pending.nullifier, pending.publicKeyHex);
    if (confirmed === "ok") {
      const result = await publishRotation(pending);
      return result === "rotated" ? "already_rotated" : result;
    }
    if (confirmed === "unavailable" || pending.publicKeyHex === current?.publicKeyHex) return "retry_later";
  }
  if (!current) return pending ? "retry_later" : "not_needed";
  if (!pending && current.origin === "device") return "not_needed";
  const version = await fetchJson(deps, `${deps.apiUrl}/api/v1/app/version`);
  if (version.status !== 200) return "retry_later";
  const features = (version.body as { features?: { identity_rotate?: unknown; identity_key_check?: unknown } } | null)?.features;
  if (features?.identity_rotate !== true || features.identity_key_check !== true) return pending ? "retry_later" : "unsupported";
  // A partial custody migration still needs the plaintext for legacy Compass.
  if (localStorage.getItem(LEGACY_PRIVATE_KEY) !== null) return "retry_later";
  // This key is independent of Ed25519 and is NEVER replaced by rotation.
  // Missing/unreadable AES state aborts instead of risking unreadable Compass.
  if (!(await readCompassKeyStrict())) return "retry_later";

  if (!(await selfTest(current.privateKey, current.publicKeyHex))) return "retry_later";

  if (!pending) {
    const pair = await crypto.subtle.generateKey({ name: "Ed25519" }, false, ["sign", "verify"]) as CryptoKeyPair;
    const publicKeyHex = bytesToHex(new Uint8Array(await crypto.subtle.exportKey("raw", pair.publicKey)));
    if (pair.privateKey.extractable || publicKeyHex === current.publicKeyHex) return "retry_later";
    await store().put<PendingRotation>(PENDING_ROTATION_RECORD, {
      privateKey: pair.privateKey, publicKeyHex, nullifier: current.nullifier, oldPublicKeyHex: current.publicKeyHex,
    });
  } else {
    // Journals written by an older client may have used relaxed durability.
    // Flush the same staged key strictly before retrying any server mutation.
    await store().put(PENDING_ROTATION_RECORD, pending);
  }
  // put resolves only after a STRICT transaction completes. Re-read before
  // any server mutation. A failed read never replaces an uncertain staged key.
  const staged = await readRotationIdentityStrict(PENDING_ROTATION_RECORD) as PendingRotation | undefined;
  if (!staged || staged.nullifier !== current.nullifier || staged.oldPublicKeyHex !== current.publicKeyHex
    || staged.publicKeyHex === current.publicKeyHex || !(await selfTest(staged.privateKey, staged.publicKeyHex))) return "retry_later";

  const ts = deps.now();
  const message = identityRotateMessage(current.nullifier, current.publicKeyHex, staged.publicKeyHex, ts);
  const res = await fetchJson(deps, `${deps.apiUrl}/api/v2/identity/rotate-key`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      nullifier_hash: current.nullifier, old_public_key_hex: current.publicKeyHex, new_public_key_hex: staged.publicKeyHex,
      timestamp_ms: ts, old_signature_hex: await webCryptoSign(current.privateKey, message),
      new_signature_hex: await webCryptoSign(staged.privateKey, message),
    }),
  });
  // Every uncertain response retains BOTH slots. Retrying the same old/new
  // pair is idempotent at the API, including a lost successful response.
  if (res.status !== 200) return res.status === 409 ? "conflict" : "retry_later";
  const body = res.body as { success?: unknown; public_key_hex?: unknown; already_rotated?: unknown } | null;
  if (body?.success !== true || body.public_key_hex !== staged.publicKeyHex) return "retry_later";
  const result = await promoteRotation(deps, staged);
  return result === "rotated" && body.already_rotated === true ? "already_rotated" : result;
}

/** Call after migrateLegacyWebKey succeeds, and on later visits to recover. */
export async function rotateMigratedWebKey(deps: MigrationDeps = DEFAULT_DEPS): Promise<RotationResult> {
  try {
    if (typeof window === "undefined") return "not_needed";
    const locked = await withKeystoreLock(() => rotateMigratedKey(deps));
    if (locked) return locked.value;
    // Without coordination we cannot promote, but an existing journal still
    // needs retries if Web Locks become available again.
    return await readRotationIdentityStrict(PENDING_ROTATION_RECORD) ? "retry_later" : "unsupported";
  } catch {
    return "retry_later"; // never log exceptions, request bodies, signatures or key material
  }
}
