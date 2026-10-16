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
  async get<T>(id: string) {
    // Simulates IndexedDB losing the identity record (the Compass key stays).
    return (this.forgetOnGet && id === "identity" ? undefined : this.data.get(id)) as T | undefined;
  }
  async put<T>(id: string, value: T) {
    if (this.failPut) throw new Error("idb down");
    this.data.set(id, value);
  }
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
