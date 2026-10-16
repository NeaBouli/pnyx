// @vitest-environment jsdom
import { webcrypto } from "node:crypto";
import { MessageChannel, receiveMessageOnPort } from "node:worker_threads";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ed25519 } from "@noble/curves/ed25519.js";
import { createEmptyProfile } from "./compass/engine";
import { loadProfile, saveProfile } from "./compass/storage";
import { submitSignedVote, voteRelevance, api as voteApi } from "./api";
import { REQUEST_TIMEOUT_MS, RequestTimeoutError } from "./request-deadline";
import { memoryLocks } from "./test-utils/web-locks";
import {
  KEY_CUSTODY_MARKER, getSigner, identityKeyCheckMessage, identityRotateMessage,
  migrateLegacyWebKey, readCompassKeyStrict, readCompassKeys, rotateMigratedWebKey,
  setKeyRecordStoreForTests, setLockManagerForTests, withKeystoreLock, withSigner,
  type KeyRecordStore, type MigrationDeps,
} from "./keystore";

const hex = (b: Uint8Array) => Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
const bytes = (h: string) => Uint8Array.from(h.match(/../g)!.map((x) => parseInt(x, 16)));
const seed = Uint8Array.from({ length: 32 }, (_, i) => i + 7);
const PRIV = hex(seed);
const PUB = hex(ed25519.getPublicKey(seed));
const NULLIFIER = "1".repeat(64);
const STAGING = "pending-rotation";
type Record = { privateKey: CryptoKey; publicKeyHex: string; nullifier: string; oldPublicKeyHex?: string; origin?: string };
type RotateBody = {
  nullifier_hash: string; old_public_key_hex: string; new_public_key_hex: string; timestamp_ms: number;
  old_signature_hex: string; new_signature_hex: string;
};

class MemoryStore implements KeyRecordStore {
  data = new Map<string, unknown>();
  failGet: string | null = null;
  failPut: string | null = null;
  failDelete: string | null = null;
  afterPut: ((id: string) => void) | null = null;
  async get<T>(id: string): Promise<T | undefined> {
    if (id === this.failGet) throw new Error("IDB unavailable");
    return this.data.get(id) as T | undefined;
  }
  async put<T>(id: string, value: T) {
    if (id === this.failPut) throw new Error("IDB unavailable");
    // Exercise CryptoKey structured cloning as IDB does (jsdom has no IDB).
    const { port1, port2 } = new MessageChannel();
    try {
      port1.postMessage(value);
      this.data.set(id, receiveMessageOnPort(port2)!.message);
    } finally {
      port1.close();
      port2.close();
    }
    this.afterPut?.(id);
  }
  async delete(id: string) {
    if (id === this.failDelete) throw new Error("IDB unavailable");
    this.data.delete(id);
  }
  record(id = "identity") { return this.data.get(id) as Record; }
}

const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

/** Minimal IDB transaction boundary so these tests use the production backend. */
function useIndexedDb(support: "strict" | "ignored" | "throws" = "strict", pauseStage = false) {
  const staged = deferred<() => void>();
  const writes: Array<{ id: string; durability: IDBTransactionDurability | undefined }> = [];
  const db = {
    close() {},
    transaction(_name: string, mode: IDBTransactionMode, options?: IDBTransactionOptions) {
      if (mode === "readwrite" && support === "throws") throw new TypeError("No transaction options");
      const tx = {
        durability: support === "ignored" ? "default" : options?.durability,
        oncomplete: null as (() => void) | null,
        abort() {},
        objectStore: () => ({
          get(id: string) {
            const req = { result: store.data.get(id) };
            queueMicrotask(() => tx.oncomplete?.());
            return req;
          },
          put(value: unknown, id: string) {
            writes.push({ id, durability: options?.durability });
            const complete = () => { store.data.set(id, value); tx.oncomplete?.(); };
            if (pauseStage && id === STAGING) staged.resolve(complete);
            else queueMicrotask(complete);
            return { result: id };
          },
          delete(id: string) {
            queueMicrotask(() => { store.data.delete(id); tx.oncomplete?.(); });
            return { result: undefined };
          },
        }),
      };
      return tx;
    },
  };
  vi.stubGlobal("indexedDB", {
    open() {
      const req = { result: db, onsuccess: null as (() => void) | null };
      queueMicrotask(() => req.onsuccess?.());
      return req;
    },
  });
  setKeyRecordStoreForTests(null);
  return { staged, writes };
}
let store: MemoryStore;
let locks: ReturnType<typeof memoryLocks>;
let api: MigrationDeps;
let serverKey: string;
let rotateFeature: unknown;
let checkFeature: boolean;
let rotateStatus: number;
let checkStatus: number;
let loseResponse: boolean;
let malformedSuccess: boolean;
let rotations: RotateBody[];
let checks: string[];
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(async () => {
  vi.stubGlobal("crypto", webcrypto);
  const realmKey = await webcrypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
  vi.stubGlobal("CryptoKey", realmKey.constructor);
  // jsdom ArrayBuffers are from another realm; pass typed arrays to Node crypto.
  const importKey = webcrypto.subtle.importKey.bind(webcrypto.subtle) as (...args: unknown[]) => Promise<CryptoKey>;
  vi.spyOn(webcrypto.subtle, "importKey").mockImplementation(((format: unknown, data: unknown, ...rest: unknown[]) =>
    importKey(format, Object.prototype.toString.call(data) === "[object ArrayBuffer]"
      ? new Uint8Array(data as ArrayBuffer) : data, ...rest)) as typeof webcrypto.subtle.importKey);
  localStorage.clear();
  store = new MemoryStore();
  locks = memoryLocks();
  setKeyRecordStoreForTests(store);
  setLockManagerForTests(locks);
  serverKey = PUB;
  rotateFeature = true;
  checkFeature = true;
  rotateStatus = checkStatus = 200;
  loseResponse = malformedSuccess = false;
  rotations = [];
  checks = [];
  fetchMock = vi.fn(async (url: string, init?: RequestInit): Promise<Response> => {
    if (url.endsWith("/app/version")) return response({ features: { identity_rotate: rotateFeature, identity_key_check: checkFeature } });
    if (url.endsWith("/rotate-key")) {
      const body = JSON.parse(String(init!.body)) as RotateBody;
      rotations.push(body);
      const staged = store.record(STAGING);
      expect(staged.publicKeyHex).toBe(body.new_public_key_hex); // durable before POST
      expect(staged.privateKey.extractable).toBe(false);
      const message = new TextEncoder().encode(identityRotateMessage(body.nullifier_hash, body.old_public_key_hex, body.new_public_key_hex, body.timestamp_ms));
      expect(body.nullifier_hash).toBe(NULLIFIER);
      expect(ed25519.verify(bytes(body.old_signature_hex), message, bytes(body.old_public_key_hex))).toBe(true);
      expect(ed25519.verify(bytes(body.new_signature_hex), message, bytes(body.new_public_key_hex))).toBe(true);
      if (rotateStatus !== 200) return response({}, rotateStatus);
      const already = serverKey === body.new_public_key_hex;
      if (!already && serverKey !== body.old_public_key_hex) return response({}, 409);
      serverKey = body.new_public_key_hex;
      if (loseResponse) throw new Error("connection lost after commit");
      return response(malformedSuccess ? { success: true, public_key_hex: PUB } : {
        success: true, public_key_hex: serverKey, already_rotated: already,
      });
    }
    if (url.endsWith("/key-check")) {
      const body = JSON.parse(String(init!.body));
      checks.push(body.public_key_hex);
      const message = new TextEncoder().encode(identityKeyCheckMessage(body.nullifier_hash, body.public_key_hex, body.timestamp_ms));
      expect(ed25519.verify(bytes(body.signature_hex), message, bytes(body.public_key_hex))).toBe(true);
      if (checkStatus !== 200) return response({}, checkStatus);
      return response({ ok: true }, body.public_key_hex === serverKey ? 200 : 409);
    }
    if (url.endsWith("/bills?limit=1")) return response([{ id: "GR-status-probe" }]);
    if (url.endsWith("/vote/GR-status-probe/status")) {
      const body = JSON.parse(String(init!.body));
      const message = `vote-status-read:v1:${JSON.stringify(["GR-status-probe", body.nullifier_hash, body.timestamp_ms])}`;
      const verified = ed25519.verify(bytes(body.signature_hex), new TextEncoder().encode(message), bytes(serverKey));
      return new Response(JSON.stringify({ bill_id: "GR-status-probe", has_voted: false }), {
        status: verified ? 200 : 401, headers: { "X-Vote-Read-Integrity": "signed" },
      });
    }
    throw new Error("Unexpected endpoint");
  });
  api = { apiUrl: "https://api.test", fetchImpl: fetchMock as typeof fetch, now: () => Date.now(), timeoutMs: 500 };
  localStorage.setItem("ekklesia_private_key", PRIV);
  localStorage.setItem("ekklesia_public_key", PUB);
  localStorage.setItem("ekklesia_nullifier_hash", NULLIFIER);
  await saveProfile({ ...createEmptyProfile(), selectedModel: "left-right" }, PRIV);
  expect(await migrateLegacyWebKey(api)).toBe("migrated");
  fetchMock.mockClear();
  locks.requested.mockClear();
  checks = [];
});

afterEach(() => {
  setKeyRecordStoreForTests(null);
  setLockManagerForTests(undefined);
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("fresh browser identity rotation", () => {
  it("waits for strict staging completion before server mutation and strictly commits promotion", async () => {
    const idb = useIndexedDb("strict", true);
    const rotation = rotateMigratedWebKey(api);
    const complete = await idb.staged.promise;
    expect(rotations).toHaveLength(0);
    expect(store.data.has(STAGING)).toBe(false);
    complete();
    expect(await rotation).toBe("rotated");
    expect(idb.writes).toEqual([
      { id: STAGING, durability: "strict" }, { id: "identity", durability: "strict" },
    ]);
  });

  it.each(["ignored", "throws"] as const)("keeps the old key and never rotates when strict durability is %s", async (support) => {
    useIndexedDb(support);
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    expect(rotations).toHaveLength(0);
    expect(store.record().publicKeyHex).toBe(PUB);
    expect(store.data.has(STAGING)).toBe(false);
  });

  it("keeps the journal when strict promotion is unavailable after a committed swap", async () => {
    loseResponse = true;
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    useIndexedDb("ignored");
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    expect(store.data.has(STAGING)).toBe(true);
    expect(store.record().publicKeyHex).toBe(PUB);
  });

  it("rotates with both signatures, checks the new key, promotes and removes every persisted old key", async () => {
    store.data.set("identity_pending", store.record()); // PR5 cleanup previously interrupted
    expect(await rotateMigratedWebKey(api)).toBe("rotated");
    const current = store.record();
    expect(current.publicKeyHex).not.toBe(PUB);
    expect(current.publicKeyHex).toBe(serverKey);
    expect(current.origin).toBe("device");
    expect(current.privateKey.extractable).toBe(false);
    await expect(crypto.subtle.exportKey("pkcs8", current.privateKey)).rejects.toThrow();
    expect(rotations).toHaveLength(1);
    expect(checks).toEqual([serverKey]);
    expect(store.data.has(STAGING)).toBe(false);
    expect(store.data.has("identity_pending")).toBe(false);
    expect(localStorage.getItem("ekklesia_private_key")).toBeNull();
    expect(localStorage.getItem("ekklesia_public_key")).toBe(serverKey);
    expect(localStorage.getItem(KEY_CUSTODY_MARKER)).toBe("webcrypto");
    const signer = (await getSigner())!;
    expect(signer.nullifier).toBe(NULLIFIER);
    expect(ed25519.verify(bytes(await signer.sign("vote")), new TextEncoder().encode("vote"), bytes(serverKey))).toBe(true);
    expect(await rotateMigratedWebKey(api)).toBe("not_needed");
    expect(rotations).toHaveLength(1);
  });

  it("recovers a crash after server success before promotion with the same staged key", async () => {
    store.failPut = "identity";
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    const staged = store.record(STAGING);
    expect(serverKey).toBe(staged.publicKeyHex);
    expect(store.record().publicKeyHex).toBe(PUB);
    expect((await getSigner())!.publicKeyHex).toBe(PUB);
    store.failPut = null;
    vi.resetModules(); // simulate a restarted page; only persistent slots survive
    const restarted = await import("./keystore");
    restarted.setKeyRecordStoreForTests(store);
    restarted.setLockManagerForTests(locks);
    expect(await restarted.rotateMigratedWebKey(api)).toBe("already_rotated");
    expect(rotations.map((r) => r.new_public_key_hex)).toEqual([staged.publicKeyHex]);
    expect((await restarted.getSigner())!.publicKeyHex).toBe(serverKey);
    expect(store.data.has(STAGING)).toBe(false);
  });

  it("recovers a lost successful response without generating another key", async () => {
    loseResponse = true;
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    const staged = store.record(STAGING);
    loseResponse = false;
    const generate = vi.spyOn(crypto.subtle, "generateKey");
    expect(await rotateMigratedWebKey(api)).toBe("already_rotated");
    expect(generate).not.toHaveBeenCalled();
    expect(store.record().publicKeyHex).toBe(staged.publicKeyHex);
  });

  it.each(["active write", "public hint", "old key cleanup", "staging deletion"])("rolls forward after a crash at %s", async (step) => {
    if (step === "active write") store.afterPut = (id) => { if (id === "identity") throw new Error("crash"); };
    if (step === "staging deletion") store.failDelete = STAGING;
    if (step === "old key cleanup") {
      store.data.set("identity_pending", store.record());
      store.failDelete = "identity_pending";
    }
    if (step === "public hint") vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota"); });
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    expect(store.record().publicKeyHex).toBe(serverKey);
    expect(store.data.has(STAGING)).toBe(true);
    store.afterPut = null;
    store.failDelete = null;
    vi.restoreAllMocks();
    expect(await rotateMigratedWebKey(api)).toBe("already_rotated");
    expect(rotations).toHaveLength(1); // old key no longer needed after atomic promotion
    expect(localStorage.getItem("ekklesia_public_key")).toBe(serverKey);
    expect(store.data.has(STAGING)).toBe(false);
    expect(store.data.has("identity_pending")).toBe(false);
  });

  it.each([400, 404, 429, 500, 503, 409])("keeps the old signer and staging on server error %s", async (status) => {
    rotateStatus = status;
    expect(await rotateMigratedWebKey(api)).toBe(status === 409 ? "conflict" : "retry_later");
    expect(store.record().publicKeyHex).toBe(PUB);
    const staged = store.record(STAGING);
    expect(staged.publicKeyHex).not.toBe(PUB);
    expect(checks).toHaveLength(0);
    rotateStatus = 200;
    expect(await rotateMigratedWebKey(api)).toBe("rotated");
    expect(store.record().publicKeyHex).toBe(staged.publicKeyHex);
  });

  it.each([409, 500])("does not promote until the new key passes key-check (%s)", async (status) => {
    checkStatus = status;
    expect(await rotateMigratedWebKey(api)).toBe(status === 409 ? "conflict" : "retry_later");
    expect(store.record().publicKeyHex).toBe(PUB);
    expect(store.record(STAGING).publicKeyHex).toBe(serverKey);
    checkStatus = 200;
    expect(await rotateMigratedWebKey(api)).toBe("already_rotated");
  });

  it("does not trust a malformed successful rotate response", async () => {
    malformedSuccess = true;
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    expect(store.record().publicKeyHex).toBe(PUB);
    expect(checks).toHaveLength(0);
    malformedSuccess = false;
    expect(await rotateMigratedWebKey(api)).toBe("already_rotated");
  });

  it.each([false, undefined, "true"])("does nothing when identity_rotate is not explicitly true (%s)", async (flag) => {
    rotateFeature = flag;
    const generate = vi.spyOn(crypto.subtle, "generateKey");
    const before = new Map(store.data);
    expect(await rotateMigratedWebKey(api)).toBe("unsupported");
    expect(store.data).toEqual(before);
    expect(generate).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(rotations).toHaveLength(0);
  });

  it("also requires the key-check flag and Web Locks", async () => {
    checkFeature = false;
    expect(await rotateMigratedWebKey(api)).toBe("unsupported");
    setLockManagerForTests(null);
    checkFeature = true;
    fetchMock.mockClear();
    expect(await rotateMigratedWebKey(api)).toBe("unsupported");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(store.data.has(STAGING)).toBe(false);
  });

  it.each(["rotate", "key-check", "both"])("recovers a committed swap with %s feature disabled", async (flag) => {
    loseResponse = true;
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    const staged = store.record(STAGING);
    if (flag !== "key-check") rotateFeature = false;
    if (flag !== "rotate") { checkFeature = false; checkStatus = 404; }
    fetchMock.mockClear();
    expect(await rotateMigratedWebKey(api)).toBe("already_rotated");
    expect(store.record().publicKeyHex).toBe(staged.publicKeyHex);
    expect(store.data.has(STAGING)).toBe(false);
    expect(rotations).toHaveLength(1);
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/app/version"))).toBe(false);
    expect((await getSigner())!.publicKeyHex).toBe(serverKey);
  });

  it("keeps an uncommitted staged key retryable when rotation is disabled", async () => {
    rotateStatus = 500;
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    const before = new Map(store.data);
    rotateFeature = false;
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    expect(store.data).toEqual(before);
    expect(rotations).toHaveLength(1);
  });

  it("keeps retrying when key-check and signed status are both unavailable", async () => {
    loseResponse = true;
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    checkStatus = 404;
    rotateFeature = checkFeature = false;
    const realFetch = api.fetchImpl;
    api.fetchImpl = (async (url: string, init?: RequestInit) => url.endsWith("/status")
      ? response({}, 404) : realFetch(url, init)) as typeof fetch;
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    expect(store.data.has(STAGING)).toBe(true);
    api.fetchImpl = realFetch;
    expect(await rotateMigratedWebKey(api)).toBe("already_rotated");
  });

  it("serializes independent tabs under the shared Web Lock", async () => {
    vi.resetModules();
    const a = await import("./keystore");
    vi.resetModules();
    const b = await import("./keystore");
    for (const tab of [a, b]) {
      tab.setKeyRecordStoreForTests(store);
      tab.setLockManagerForTests(locks);
    }
    const results = await Promise.all([a.rotateMigratedWebKey(api), b.rotateMigratedWebKey(api)]);
    expect(results.sort()).toEqual(["not_needed", "rotated"]);
    expect(rotations).toHaveLength(1);
    expect(locks.requested).toHaveBeenCalledTimes(2);
    expect((await a.getSigner())!.publicKeyHex).toBe((await b.getSigner())!.publicKeyHex);
  });

  it("keeps Compass readable with its independent AES key and permits writes waiting on the lock", async () => {
    const aes = (await readCompassKeyStrict())!;
    const ciphertext = localStorage.getItem("ekklesia_compass_encrypted");
    const rotation = rotateMigratedWebKey(api);
    const read = withKeystoreLock(async () => loadProfile(await readCompassKeys()));
    expect(await rotation).toBe("rotated");
    expect((await read)!.value.selectedModel).toBe("left-right");
    expect(await readCompassKeyStrict()).toBe(aes);
    expect(localStorage.getItem("ekklesia_compass_encrypted")).toBe(ciphertext);
    await withKeystoreLock(async () => saveProfile({ ...createEmptyProfile(), selectedModel: "party-match" }, await readCompassKeys()));
    expect((await loadProfile({ aesKey: aes })).selectedModel).toBe("party-match");
    expect((await readCompassKeys()).legacyPrivateKeyHex).toBeNull();
  });

  it("holds the signing lock from acquisition through submission before allowing rotation", async () => {
    const acquired = deferred<void>();
    const submit = deferred<void>();
    const signing = withSigner(async (signer) => {
      expect(signer!.publicKeyHex).toBe(PUB);
      acquired.resolve();
      await submit.promise;
      const signature = await signer!.sign("discourse_sso:nonce:" + signer!.publicKeyHex);
      expect(ed25519.verify(bytes(signature), new TextEncoder().encode("discourse_sso:nonce:" + signer!.publicKeyHex), bytes(serverKey))).toBe(true);
    });
    await acquired.promise;
    const rotation = rotateMigratedWebKey(api);
    await Promise.resolve();
    expect(rotations).toHaveLength(0);
    expect(locks.requested.mock.calls.map(([, options]) => options.mode)).toEqual(["shared", "exclusive"]);
    submit.resolve();
    await signing;
    expect(await rotation).toBe("rotated");
  });

  it.each(["status fetch", "status body", "status error body", "vote fetch", "vote body"])(
    "releases a stalled %s at the deadline so queued rotation and signers proceed", async (stage) => {
      vi.useFakeTimers();
      const stalled = deferred<void>();
      const lateResponse = deferred<Response>();
      let requestSignal: AbortSignal | undefined;
      const voteFetch = vi.fn((_url: string, init: RequestInit) => {
        requestSignal = init.signal!;
        const isStatus = voteFetch.mock.calls.length === 1;
        if (isStatus && stage.startsWith("vote")) {
          return Promise.resolve(response({ status: "ACTIVE", has_voted: false, vote: null }));
        }
        stalled.resolve();
        // Deliberately ignore abort to exercise the hard deadline.
        return stage.endsWith("fetch") ? lateResponse.promise : Promise.resolve(new Response(
          new ReadableStream(), { status: stage === "status error body" ? 503 : 200 },
        ));
      });
      vi.stubGlobal("fetch", voteFetch);
      const voting = withSigner(async (signer) => submitSignedVote("GR-timeout", "YES", {
        ...signer!, nullifier: signer!.nullifier!,
      })).catch((error: unknown) => error);
      await stalled.promise;
      const rotation = rotateMigratedWebKey(api);
      const nextSigner = vi.fn(async (signer: { publicKeyHex: string } | null) => signer!.publicKeyHex);
      const signing = withSigner(nextSigner);
      await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS - 1);
      expect(rotations).toHaveLength(0);
      expect(nextSigner).not.toHaveBeenCalled();
      expect(requestSignal!.aborted).toBe(false);
      await vi.advanceTimersByTimeAsync(1);
      expect(await voting).toBeInstanceOf(RequestTimeoutError);
      expect(requestSignal!.aborted).toBe(true);
      expect(await rotation).toBe("rotated");
      expect(await signing).toBe(serverKey);
      expect(serverKey).not.toBe(PUB);
      // A late status response must never start a vote with the retired key.
      lateResponse.resolve(response({ status: "ACTIVE", has_voted: false, vote: null }));
      await vi.advanceTimersByTimeAsync(0);
      expect(voteFetch).toHaveBeenCalledTimes(stage.startsWith("vote") ? 2 : 1);
      expect(vi.getTimerCount()).toBe(0);
    },
  );

  it("bounds relevance submission while holding the signing lock", async () => {
    vi.useFakeTimers();
    const stalled = deferred<void>();
    let signal: AbortSignal | undefined;
    vi.spyOn(voteApi, "post").mockImplementation((_url, _body, options) => {
      signal = options?.signal as AbortSignal;
      stalled.resolve();
      return new Promise(() => {});
    });
    const voting = withSigner(async () => voteRelevance("GR-timeout", 1, NULLIFIER, "signature"))
      .catch((error: unknown) => error);
    await stalled.promise;
    const rotation = rotateMigratedWebKey(api);
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS);
    expect(await voting).toBeInstanceOf(RequestTimeoutError);
    expect(signal!.aborted).toBe(true);
    expect(await rotation).toBe("rotated");
  });

  it("rejects an already aborted signer request even without Web Locks", async () => {
    setLockManagerForTests(null);
    const controller = new AbortController();
    controller.abort(new RequestTimeoutError());
    const submit = vi.fn();
    await expect(withSigner(submit, controller.signal)).rejects.toBeInstanceOf(RequestTimeoutError);
    expect(submit).not.toHaveBeenCalled();
  });

  it("a signing request made during rotation acquires the promoted key after the swap", async () => {
    const rotating = deferred<void>();
    const commit = deferred<void>();
    const realFetch = api.fetchImpl;
    api.fetchImpl = (async (url: string, init?: RequestInit) => {
      if (url.endsWith("/rotate-key")) { rotating.resolve(); await commit.promise; }
      return realFetch(url, init);
    }) as typeof fetch;
    const rotation = rotateMigratedWebKey(api);
    await rotating.promise;
    const sign = vi.fn();
    const signing = withSigner(async (signer) => {
      sign();
      expect(signer!.publicKeyHex).toBe(serverKey);
      const signature = await signer!.sign("vote");
      expect(ed25519.verify(bytes(signature), new TextEncoder().encode("vote"), bytes(serverKey))).toBe(true);
    });
    await Promise.resolve();
    expect(sign).not.toHaveBeenCalled();
    commit.resolve();
    expect(await rotation).toBe("rotated");
    await signing;
    expect(sign).toHaveBeenCalledTimes(1);
  });

  it.each(["identity", STAGING, "compass"])("preserves all slots on an unreadable %s slot", async (slot) => {
    rotateStatus = 500;
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    const before = new Map(store.data);
    rotations = [];
    store.failGet = slot;
    rotateStatus = 200;
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    expect(store.data).toEqual(before);
    expect(rotations).toHaveLength(0);
  });

  it("stages before any mutation and reuses staging after a crash immediately after the IDB write", async () => {
    store.afterPut = (id) => { if (id === STAGING) throw new Error("crash"); };
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    expect(rotations).toHaveLength(0);
    const staged = store.record(STAGING);
    store.afterPut = null;
    expect(await rotateMigratedWebKey(api)).toBe("rotated");
    expect(store.record().publicKeyHex).toBe(staged.publicKeyHex);
  });

  it("does not contact rotate-key when staging cannot be persisted or read back", async () => {
    store.failPut = STAGING;
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    expect(rotations).toHaveLength(0);
    expect(store.data.has(STAGING)).toBe(false);
    store.failPut = null;
    store.afterPut = (id) => { if (id === STAGING) store.failGet = STAGING; };
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    expect(rotations).toHaveLength(0);
    expect(store.data.has(STAGING)).toBe(true);
    store.failGet = null;
    store.afterPut = null;
    expect(await rotateMigratedWebKey(api)).toBe("rotated");
  });

  it("never overwrites staging bound to another identity", async () => {
    rotateStatus = 500;
    await rotateMigratedWebKey(api);
    const staged = store.record(STAGING);
    staged.nullifier = "2".repeat(64);
    rotateStatus = 200;
    rotations = [];
    expect(await rotateMigratedWebKey(api)).toBe("conflict");
    expect(store.record(STAGING)).toBe(staged);
    expect(store.record().publicKeyHex).toBe(PUB);
    expect(rotations).toHaveLength(0);
  });

  it("does not rotate a partially completed custody migration", async () => {
    localStorage.setItem("ekklesia_private_key", PRIV);
    expect(await rotateMigratedWebKey(api)).toBe("retry_later");
    expect(store.data.has(STAGING)).toBe(false);
    expect(rotations).toHaveLength(0);
  });

  it.each(["fetch", "body"])("bounds a stalled rotation %s without discarding staging", async (stage) => {
    vi.useFakeTimers();
    const realFetch = api.fetchImpl;
    const stalled = deferred<void>();
    let signal: AbortSignal | undefined;
    api.timeoutMs = 20;
    api.fetchImpl = (async (url: string, init?: RequestInit) => {
      if (!url.endsWith("/rotate-key")) return realFetch(url, init);
      signal = init?.signal as AbortSignal;
      stalled.resolve();
      return stage === "fetch" ? new Promise(() => {}) : { status: 200, text: () => new Promise(() => {}) };
    }) as typeof fetch;
    const rotation = rotateMigratedWebKey(api);
    await stalled.promise;
    const write = vi.fn(async () => undefined);
    const compass = withKeystoreLock(write);
    expect(write).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(api.timeoutMs);
    expect(await rotation).toBe("retry_later");
    await compass;
    expect(signal!.aborted).toBe(true);
    expect(write).toHaveBeenCalledTimes(1);
    expect(store.record().publicKeyHex).toBe(PUB);
    expect(store.data.has(STAGING)).toBe(true);
    api.fetchImpl = realFetch;
    expect(await rotateMigratedWebKey(api)).toBe("rotated");
  });
});
