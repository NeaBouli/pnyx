// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ed25519 } from "@noble/curves/ed25519.js";

const ls = new Map<string, string>();
const lsFail = { key: null as string | null };
Object.assign(globalThis, {
  window: globalThis,
  localStorage: {
    getItem: (k: string) => ls.get(k) ?? null,
    setItem: (k: string, v: string) => {
      if (lsFail.key === k) throw new Error("quota");
      ls.set(k, v);
    },
    removeItem: (k: string) => void ls.delete(k),
  },
});

import { saveProfile } from "./compass/storage";
import { createEmptyProfile } from "./compass/engine";
import {
  KEY_CUSTODY_MARKER,
  setLockManagerForTests,
  withKeystoreLock,
  getCompassKey,
  getSigner,
  hasLocalSignerHint,
  identityKeyCheckMessage,
  migrateLegacyWebKey,
  setKeyRecordStoreForTests,
  type KeyRecordStore,
  type MigrationDeps,
} from "./keystore";

const hex = (b: Uint8Array) => Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
const bytes = (h: string) => Uint8Array.from(h.match(/../g)!.map((x) => parseInt(x, 16)));
const SEED = Uint8Array.from({ length: 32 }, (_, i) => i + 7);
const PRIV = hex(SEED);
const PUB = hex(ed25519.getPublicKey(SEED));
const NULLIFIER = "1".repeat(64);

class MemoryStore implements KeyRecordStore {
  data = new Map<string, unknown>();
  failPut = false;
  forgetOnGet = false;
  failGetOnce: string | null = null;
  async get<T>(id: string) {
    if (this.failGetOnce === id) {
      this.failGetOnce = null;
      throw new Error("idb read aborted");
    }
    // Simulates IndexedDB losing the identity record (the Compass key stays).
    return (this.forgetOnGet && id === "identity" ? undefined : this.data.get(id)) as T | undefined;
  }
  async put<T>(id: string, value: T) {
    if (this.failPut) throw new Error("idb down");
    this.data.set(id, value);
  }
  async delete(id: string) {
    this.data.delete(id);
  }
}

/** In-process stand-in for navigator.locks (exclusive, FIFO). */
function memoryLocks() {
  const queues = new Map<string, Promise<unknown>>();
  return {
    request<T>(name: string, cb: () => Promise<T>): Promise<T> {
      const prev = queues.get(name) ?? Promise.resolve();
      const run = prev.then(cb, cb);
      queues.set(name, run.then(() => undefined, () => undefined));
      return run;
    },
  };
}

let store: MemoryStore;
let serverKey = PUB;
let serverStatus: number | "down" = 200;
let feature = true;
const serverChecks: Array<{ verified: boolean }> = [];

function deps(): MigrationDeps {
  return {
    apiUrl: "https://api.test",
    now: () => Date.now(),
    timeoutMs: 5_000,
    fetchImpl: (async (url: string, init?: RequestInit) => {
      if (url.endsWith("/api/v1/app/version")) {
        return new Response(JSON.stringify({ features: { identity_key_check: feature } }), { status: 200 });
      }
      if (serverStatus === "down") throw new Error("offline");
      const body = JSON.parse(String(init!.body));
      // The fake server really verifies the signature, like the API.
      const msg = new TextEncoder().encode(identityKeyCheckMessage(body.nullifier_hash, body.public_key_hex, body.timestamp_ms));
      const verified = ed25519.verify(bytes(body.signature_hex), msg, bytes(body.public_key_hex));
      serverChecks.push({ verified });
      if (!verified) return new Response(JSON.stringify({ detail: "INVALID_SIGNATURE" }), { status: 400 });
      if (serverStatus !== 200) return new Response("{}", { status: serverStatus });
      if (body.public_key_hex !== serverKey) return new Response(JSON.stringify({ detail: "KEY_NOT_CURRENT" }), { status: 409 });
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }) as unknown as typeof fetch,
  };
}

function legacyBrowser() {
  ls.set("ekklesia_private_key", PRIV);
  ls.set("ekklesia_public_key", PUB);
  ls.set("ekklesia_nullifier_hash", NULLIFIER);
}

beforeEach(() => {
  ls.clear();
  lsFail.key = null;
  store = new MemoryStore();
  setKeyRecordStoreForTests(store);
  setLockManagerForTests(memoryLocks());
  serverKey = PUB;
  serverStatus = 200;
  feature = true;
  serverChecks.length = 0;
});
afterEach(() => vi.restoreAllMocks());

describe("migrateLegacyWebKey", () => {
  it("moves the key into non-extractable custody, re-encrypts Compass, then drops the plaintext", async () => {
    legacyBrowser();
    const profile = { ...createEmptyProfile(), selectedModel: "left-right" } as ReturnType<typeof createEmptyProfile>;
    await saveProfile(profile, PRIV); // Compass encrypted with the legacy HKDF key

    expect(await migrateLegacyWebKey(deps())).toBe("migrated");

    expect(ls.has("ekklesia_private_key")).toBe(false);
    expect(ls.get("ekklesia_public_key")).toBe(PUB);
    expect(ls.get("ekklesia_nullifier_hash")).toBe(NULLIFIER);
    expect(ls.get(KEY_CUSTODY_MARKER)).toBe("webcrypto");
    expect(serverChecks).toEqual([{ verified: true }]);

    const rec = store.data.get("identity") as { privateKey: CryptoKey };
    expect(rec.privateKey.extractable).toBe(false);
    await expect(crypto.subtle.exportKey("pkcs8", rec.privateKey)).rejects.toThrow();

    const signer = (await getSigner())!;
    expect(signer.custody).toBe("webcrypto");
    const sig = await signer.sign("GR-1:YES:" + NULLIFIER);
    expect(ed25519.verify(bytes(sig), new TextEncoder().encode("GR-1:YES:" + NULLIFIER), bytes(PUB))).toBe(true);
    expect(hasLocalSignerHint()).toBe(true);

    // Compass is readable with the new key only.
    const { loadProfile } = await import("./compass/storage");
    const compassKey = (await getCompassKey())!;
    expect(compassKey.extractable).toBe(false);
    expect((await loadProfile({ aesKey: compassKey })).selectedModel).toBe("left-right");
  });

  it.each([
    ["server holds another key", () => { serverKey = "ab".repeat(32); }, "key_not_current"],
    ["server unavailable", () => { serverStatus = "down"; }, "retry_later"],
    ["server error", () => { serverStatus = 500; }, "retry_later"],
    ["feature off", () => { feature = false; }, "unsupported"],
    ["IndexedDB write fails", () => { store.failPut = true; }, "retry_later"],
    ["IndexedDB loses the record", () => { store.forgetOnGet = true; }, "retry_later"],
  ])("keeps the legacy key when %s", async (_name, setup, expected) => {
    legacyBrowser();
    setup();
    expect(await migrateLegacyWebKey(deps())).toBe(expected);
    expect(ls.get("ekklesia_private_key")).toBe(PRIV);
    expect(ls.has(KEY_CUSTODY_MARKER)).toBe(false);
    const signer = (await getSigner())!;
    expect(signer.publicKeyHex).toBe(PUB); // the user can still sign
  });

  it("keeps the legacy key when Ed25519 WebCrypto is unavailable", async () => {
    legacyBrowser();
    vi.spyOn(crypto.subtle, "generateKey").mockRejectedValue(new Error("NotSupportedError"));
    expect(await migrateLegacyWebKey(deps())).toBe("unsupported");
    expect(ls.get("ekklesia_private_key")).toBe(PRIV);
    expect((await getSigner())!.custody).toBe("legacy");
  });

  it("keeps the legacy key if the Compass ciphertext cannot be rewritten, and succeeds on retry", async () => {
    legacyBrowser();
    await saveProfile(createEmptyProfile(), PRIV);
    lsFail.key = "ekklesia_compass_encrypted";
    expect(await migrateLegacyWebKey(deps())).toBe("retry_later");
    expect(ls.get("ekklesia_private_key")).toBe(PRIV);
    lsFail.key = null;
    expect(await migrateLegacyWebKey(deps())).toBe("migrated");
    expect(ls.has("ekklesia_private_key")).toBe(false);
  });

  it("is idempotent and does nothing without a legacy key", async () => {
    expect(await migrateLegacyWebKey(deps())).toBe("no_legacy");
    legacyBrowser();
    expect(await migrateLegacyWebKey(deps())).toBe("migrated");
    expect(await migrateLegacyWebKey(deps())).toBe("not_needed");
    expect(serverChecks).toHaveLength(1);
  });

  it("refuses an inconsistent legacy pair (never stores a key the server cannot verify)", async () => {
    legacyBrowser();
    ls.set("ekklesia_public_key", "cd".repeat(32));
    expect(await migrateLegacyWebKey(deps())).toBe("retry_later");
    expect(ls.get("ekklesia_private_key")).toBe(PRIV);
    expect(serverChecks).toHaveLength(0);
  });
});

describe("getSigner", () => {
  it("signs with the legacy key before migration", async () => {
    legacyBrowser();
    const signer = (await getSigner())!;
    expect(signer.custody).toBe("legacy");
    const sig = await signer.sign("x");
    expect(ed25519.verify(bytes(sig), new TextEncoder().encode("x"), bytes(PUB))).toBe(true);
  });

  it("returns null without any key", async () => {
    expect(await getSigner()).toBeNull();
    expect(hasLocalSignerHint()).toBe(false);
  });
});

describe("review round 1 (Codex)", () => {
  it("a failed migration never publishes a signer record (pending stays invisible)", async () => {
    legacyBrowser();
    serverKey = "ab".repeat(32); // server says: not the current key
    expect(await migrateLegacyWebKey(deps())).toBe("key_not_current");
    expect(store.data.has("identity")).toBe(false);
    expect((await getSigner())!.custody).toBe("legacy");
  });

  it("rolls back a published record that fails its re-test", async () => {
    legacyBrowser();
    const wrong = (await crypto.subtle.generateKey({ name: "Ed25519" }, false, ["sign", "verify"])) as CryptoKeyPair;
    const realGet = store.get.bind(store);
    store.get = async <T,>(id: string) => {
      const v = await realGet<T>(id);
      if (id === "identity" && v) return { ...(v as object), privateKey: wrong.privateKey } as T; // corrupted on read
      return v;
    };
    expect(await migrateLegacyWebKey(deps())).toBe("retry_later");
    expect(store.data.has("identity")).toBe(false);
    expect(ls.get("ekklesia_private_key")).toBe(PRIV);
  });

  it("signing falls back to the legacy copy of the same key if WebCrypto signing fails", async () => {
    legacyBrowser();
    const aes = (await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"])) as CryptoKey;
    store.data.set("identity", { privateKey: aes, publicKeyHex: PUB, nullifier: NULLIFIER }); // unusable for Ed25519
    const sig = await (await getSigner())!.sign("payload");
    expect(ed25519.verify(bytes(sig), new TextEncoder().encode("payload"), bytes(PUB))).toBe(true);
  });

  it("SSO can sign with a legacy pair that has no nullifier", async () => {
    ls.set("ekklesia_private_key", PRIV);
    ls.set("ekklesia_public_key", PUB);
    const signer = (await getSigner())!;
    expect(signer.nullifier).toBeNull();
    const sig = await signer.sign("discourse_sso:n:" + PUB);
    expect(ed25519.verify(bytes(sig), new TextEncoder().encode("discourse_sso:n:" + PUB), bytes(PUB))).toBe(true);
  });

  it("without Web Locks the browser stays on the legacy key", async () => {
    legacyBrowser();
    setLockManagerForTests(null);
    expect(await migrateLegacyWebKey(deps())).toBe("unsupported");
    expect(ls.get("ekklesia_private_key")).toBe(PRIV);
  });

  it("two tabs migrating at once end with one Compass key that decrypts the profile", async () => {
    legacyBrowser();
    await saveProfile({ ...createEmptyProfile(), selectedModel: "left-right" } as ReturnType<typeof createEmptyProfile>, PRIV);
    const locks = memoryLocks();
    setLockManagerForTests(locks);
    vi.resetModules();
    const tabA = await import("./keystore");
    vi.resetModules();
    const tabB = await import("./keystore");
    for (const tab of [tabA, tabB]) {
      tab.setKeyRecordStoreForTests(store);
      tab.setLockManagerForTests(locks);
    }
    const [a, b] = await Promise.all([tabA.migrateLegacyWebKey(deps()), tabB.migrateLegacyWebKey(deps())]);
    expect([a, b].sort()).toEqual(["migrated", "not_needed"]);
    const { loadProfile } = await import("./compass/storage");
    const key = (await tabB.getCompassKey())!;
    expect((await loadProfile({ aesKey: key })).selectedModel).toBe("left-right");
  });

  it("a Compass save waiting for the lock reads the keys only after the migration", async () => {
    legacyBrowser();
    await saveProfile(createEmptyProfile(), PRIV);
    let release!: () => void;
    const gate = new Promise<void>((r) => { release = r; });
    const d = deps();
    const realFetch = d.fetchImpl;
    d.fetchImpl = (async (url: string, init?: RequestInit) => {
      if (url.endsWith("/key-check")) await gate;
      return realFetch(url, init);
    }) as typeof fetch;
    // useCompass must see the same store and the same cross-tab lock.
    const locks = memoryLocks();
    setLockManagerForTests(locks);
    const keystoreForCompass = await import("./keystore");
    keystoreForCompass.setKeyRecordStoreForTests(store);
    keystoreForCompass.setLockManagerForTests(locks);
    const migration = migrateLegacyWebKey(d);
    await new Promise((r) => setTimeout(r, 10));
    const { readCompassKeysSafely, saveProfileSafely } = await import("./compass/useCompass");
    const save = withKeystoreLock(async () => saveProfileSafely({ ...createEmptyProfile(), selectedModel: "party-match" } as ReturnType<typeof createEmptyProfile>, await readCompassKeysSafely()));
    release();
    expect(await migration).toBe("migrated");
    await save;
    const { loadProfile } = await import("./compass/storage");
    expect((await loadProfile({ aesKey: (await getCompassKey())! })).selectedModel).toBe("party-match");
  });
});

describe("review round 2 (Codex)", () => {
  it("a failed Compass-key read aborts the migration instead of replacing the key", async () => {
    legacyBrowser();
    const k1 = (await crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"])) as CryptoKey;
    store.data.set("compass", k1);
    await saveProfile({ ...createEmptyProfile(), selectedModel: "left-right" } as ReturnType<typeof createEmptyProfile>, { aesKey: k1 });
    store.failGetOnce = "compass";
    expect(await migrateLegacyWebKey(deps())).toBe("retry_later");
    expect(store.data.get("compass")).toBe(k1);
    expect(ls.get("ekklesia_private_key")).toBe(PRIV);
    expect(await migrateLegacyWebKey(deps())).toBe("migrated");
    const { loadProfile } = await import("./compass/storage");
    expect((await loadProfile({ aesKey: (await getCompassKey())! })).selectedModel).toBe("left-right");
  });
});

describe("review round 3 (Codex)", () => {
  it("an operational HKDF failure keeps the legacy key instead of skipping Compass", async () => {
    legacyBrowser();
    await saveProfile({ ...createEmptyProfile(), selectedModel: "left-right" } as ReturnType<typeof createEmptyProfile>, PRIV);
    const realDerive = crypto.subtle.deriveKey.bind(crypto.subtle);
    let failed = false;
    vi.spyOn(crypto.subtle, "deriveKey").mockImplementation(((...args: Parameters<SubtleCrypto["deriveKey"]>) => {
      if (!failed) { failed = true; return Promise.reject(new Error("OperationError")); }
      return realDerive(...args);
    }) as SubtleCrypto["deriveKey"]);
    expect(await migrateLegacyWebKey(deps())).toBe("retry_later");
    expect(ls.get("ekklesia_private_key")).toBe(PRIV);
    expect(await migrateLegacyWebKey(deps())).toBe("migrated");
    const { loadProfile } = await import("./compass/storage");
    expect((await loadProfile({ aesKey: (await getCompassKey())! })).selectedModel).toBe("left-right");
  });
});
