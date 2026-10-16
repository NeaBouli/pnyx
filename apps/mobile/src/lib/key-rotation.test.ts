import { beforeEach, describe, expect, it, vi } from "vitest";
import { ed25519 } from "@noble/curves/ed25519.js";

const state = vi.hoisted(() => ({
  values: new Map<string, string>(),
  demo: false,
  failImport: false,
  failWrite: null as string | null,
  scopeGate: null as Promise<void> | null,
}));

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(async (key: string) => state.values.get(key) ?? null),
  setItemAsync: vi.fn(async (key: string, value: string) => {
    if (state.failWrite === key) {
      state.failWrite = null;
      throw new Error(`killed while writing ${key}`);
    }
    state.values.set(key, value);
  }),
  deleteItemAsync: vi.fn(async (key: string) => {
    state.values.delete(key);
  }),
}));
vi.mock("expo-crypto", () => ({ getRandomBytes: vi.fn() }));
vi.mock("./demo", () => ({ isDemoMode: vi.fn(async () => state.demo) }));
vi.mock("./profile-location", () => ({ storeProfileLocation: vi.fn(async () => {}) }));
vi.mock("./bill-scope-storage", () => ({ loadUserBillScope: vi.fn(async () => {
  if (state.scopeGate) await state.scopeGate;
  if (state.failImport) throw new Error("scope down");
}) }));

import {
  getOrDerivePolisKey,
  installServerIssuedCredentials,
  loadKeyOrigin,
  prepareForServerIssuedKey,
  recoverIdentityJournal,
  storeKeypair,
  withIdentityStateLock,
} from "./crypto-native";
import { importAccountCredentials } from "./import-account";
import { identityRotateMessage, rotateLegacyKeyIfNeeded, type RotationDeps } from "./key-rotation";

const hex = (b: Uint8Array) => Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
const OLD_SEED = Uint8Array.from({ length: 32 }, (_, i) => i + 1);
const OLD_PRIV = hex(OLD_SEED);
const OLD_PUB = hex(ed25519.getPublicKey(OLD_SEED));
const NEW_SEED = Uint8Array.from({ length: 32 }, (_, i) => 200 - i);
const NEW_PRIV = hex(NEW_SEED);
const NEW_PUB = hex(ed25519.getPublicKey(NEW_SEED));
const NULLIFIER = "1".repeat(64);
const API = "https://api.test";

type Call = { url: string; init?: RequestInit };

function deps(opts: { rotate?: number | Error; rotateBody?: unknown; feature?: boolean | "down"; gate?: Promise<void> } = {}) {
  const calls: Call[] = [];
  const fetchImpl = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    if (url.endsWith("/api/v1/app/version")) {
      if (opts.feature === "down") throw new Error("offline");
      return new Response(JSON.stringify({ features: { identity_rotate: opts.feature ?? true } }), { status: 200 });
    }
    if (opts.gate) await opts.gate;
    if (opts.rotate instanceof Error) throw opts.rotate;
    const status = opts.rotate ?? 200;
    const body = opts.rotateBody ?? (status === 200 ? { success: true, public_key_hex: NEW_PUB, already_rotated: false } : { detail: "x" });
    return new Response(JSON.stringify(body), { status });
  });
  const d: RotationDeps = { apiBase: API, fetchImpl: fetchImpl as unknown as typeof fetch, randomBytes: () => NEW_SEED.slice(), now: () => 1_700_000_000_000, timeoutMs: 5_000 };
  return { d, calls };
}

function legacyUser() {
  state.values.set("ekklesia_private_key", OLD_PRIV);
  state.values.set("ekklesia_public_key", OLD_PUB);
  state.values.set("ekklesia_nullifier", NULLIFIER);
}

const rotateCalls = (calls: Call[]) => calls.filter((c) => c.url.endsWith("/rotate-key"));

beforeEach(() => {
  state.values.clear();
  state.demo = false;
  state.failImport = false;
  state.failWrite = null;
  state.scopeGate = null;
});

describe("rotateLegacyKeyIfNeeded", () => {
  it("rotates a legacy key with both signatures and commits the device key", async () => {
    legacyUser();
    const polisBefore = (await getOrDerivePolisKey())!.pkPolisHex;
    const { d, calls } = deps();

    expect(await rotateLegacyKeyIfNeeded(d)).toBe("rotated");

    const [call] = rotateCalls(calls);
    expect(call.url).toBe(`${API}/api/v2/identity/rotate-key`);
    const body = JSON.parse(String(call.init!.body));
    expect(body).toMatchObject({ nullifier_hash: NULLIFIER, old_public_key_hex: OLD_PUB, new_public_key_hex: NEW_PUB, timestamp_ms: 1_700_000_000_000 });
    const msg = new TextEncoder().encode(identityRotateMessage(NULLIFIER, OLD_PUB, NEW_PUB, 1_700_000_000_000));
    const bytes = (h: string) => Uint8Array.from(h.match(/../g)!.map((x) => parseInt(x, 16)));
    expect(ed25519.verify(bytes(body.old_signature_hex), msg, bytes(OLD_PUB))).toBe(true);
    expect(ed25519.verify(bytes(body.new_signature_hex), msg, bytes(NEW_PUB))).toBe(true);
    expect(JSON.stringify(body)).not.toContain(NEW_PRIV);
    expect(JSON.stringify(body)).not.toContain(OLD_PRIV);

    expect(state.values.get("ekklesia_private_key")).toBe(NEW_PRIV);
    expect(state.values.get("ekklesia_public_key")).toBe(NEW_PUB);
    expect(state.values.get("ekklesia_key_origin")).toBe(NEW_PUB);
    expect(await loadKeyOrigin()).toBe("device");
    expect(state.values.has("ekklesia_rotation_staging")).toBe(false);
    // POLIS identity unchanged although the identity key changed.
    expect((await getOrDerivePolisKey())!.pkPolisHex).toBe(polisBefore);
  });

  it("does nothing when the server does not advertise rotation", async () => {
    legacyUser();
    const { d, calls } = deps({ feature: false });
    expect(await rotateLegacyKeyIfNeeded(d)).toBe("unsupported");
    expect(rotateCalls(calls)).toHaveLength(0);
    expect(state.values.get("ekklesia_private_key")).toBe(OLD_PRIV);
    expect(state.values.has("ekklesia_polis_seed")).toBe(false);
  });

  it("retries later when the capability check fails", async () => {
    legacyUser();
    const { d } = deps({ feature: "down" });
    expect(await rotateLegacyKeyIfNeeded(d)).toBe("retry_later");
    expect(state.values.get("ekklesia_private_key")).toBe(OLD_PRIV);
  });

  it.each([
    ["device origin", () => { legacyUser(); state.values.set("ekklesia_key_origin", OLD_PUB); }, "not_needed"],
    ["demo identity", () => { legacyUser(); state.demo = true; }, "skipped"],
    ["no identity", () => {}, "skipped"],
  ])("skips for %s", async (_name, setup, expected) => {
    setup();
    const { d, calls } = deps();
    expect(await rotateLegacyKeyIfNeeded(d)).toBe(expected);
    expect(rotateCalls(calls)).toHaveLength(0);
  });

  it("keeps the old key and the staged key on a network error, then succeeds idempotently", async () => {
    legacyUser();
    const first = deps({ rotate: new Error("network") });
    expect(await rotateLegacyKeyIfNeeded(first.d)).toBe("retry_later");
    expect(state.values.get("ekklesia_private_key")).toBe(OLD_PRIV);
    expect(state.values.has("ekklesia_rotation_staging")).toBe(true);

    // The server had applied it; the retry re-sends the SAME staged key.
    const second = deps({ rotateBody: { success: true, public_key_hex: NEW_PUB, already_rotated: true } });
    second.d.randomBytes = () => { throw new Error("must reuse the staged key"); };
    expect(await rotateLegacyKeyIfNeeded(second.d)).toBe("already_rotated");
    expect(JSON.parse(String(rotateCalls(second.calls)[0].init!.body)).new_public_key_hex).toBe(NEW_PUB);
    expect(state.values.get("ekklesia_private_key")).toBe(NEW_PRIV);
  });

  it.each([400, 404, 429, 500])("keeps the staged key on HTTP %i (server may already hold it)", async (status) => {
    legacyUser();
    const { d } = deps({ rotate: status });
    await rotateLegacyKeyIfNeeded(d);
    expect(state.values.get("ekklesia_private_key")).toBe(OLD_PRIV);
    expect(state.values.has("ekklesia_rotation_staging")).toBe(true);
  });

  it("drops the staged key only on 409 and keeps using the old key", async () => {
    legacyUser();
    const { d } = deps({ rotate: 409 });
    expect(await rotateLegacyKeyIfNeeded(d)).toBe("conflict");
    expect(state.values.get("ekklesia_private_key")).toBe(OLD_PRIV);
    expect(state.values.has("ekklesia_rotation_staging")).toBe(false);
    expect(state.values.has("ekklesia_key_origin")).toBe(false);
  });

  it("an interrupted local commit is rolled forward from the journal", async () => {
    legacyUser();
    state.failWrite = "ekklesia_public_key"; // killed between private and public key
    await expect(rotateLegacyKeyIfNeeded(deps().d)).rejects.toThrow("killed");
    expect(state.values.get("ekklesia_private_key")).toBe(NEW_PRIV);
    expect(state.values.get("ekklesia_public_key")).toBe(OLD_PUB); // mixed on disk

    expect(await recoverIdentityJournal()).toBe(true);
    expect(state.values.get("ekklesia_public_key")).toBe(NEW_PUB);
    expect(await loadKeyOrigin()).toBe("device");
    expect(state.values.has("ekklesia_rotation_staging")).toBe(false);
    expect(state.values.has("ekklesia_identity_journal")).toBe(false);
  });

  it("ignores a corrupt staging slot", async () => {
    legacyUser();
    state.values.set("ekklesia_rotation_staging", JSON.stringify({ nullifier: NULLIFIER, oldPublicKeyHex: OLD_PUB, privateKeyHex: OLD_PRIV, publicKeyHex: NEW_PUB }));
    const { d, calls } = deps();
    expect(await rotateLegacyKeyIfNeeded(d)).toBe("rotated");
    expect(JSON.parse(String(rotateCalls(calls)[0].init!.body)).new_public_key_hex).toBe(NEW_PUB);
  });

  it("does not persist a POLIS seed for users with a nullifier root", async () => {
    legacyUser();
    state.values.set("ekklesia_nullifier_root", "ab".repeat(32));
    const polisBefore = (await getOrDerivePolisKey())!.pkPolisHex;
    expect(await rotateLegacyKeyIfNeeded(deps().d)).toBe("rotated");
    expect(state.values.has("ekklesia_polis_seed")).toBe(false);
    expect((await getOrDerivePolisKey())!.pkPolisHex).toBe(polisBefore);
  });

  it("never writes to the read-only mirror", async () => {
    legacyUser();
    const { d, calls } = deps();
    await rotateLegacyKeyIfNeeded(d);
    expect(calls.every((c) => c.url.startsWith(API))).toBe(true);
  });
});

const C_SEED = Uint8Array.from({ length: 32 }, () => 0xcd);
const C_PRIV = hex(C_SEED);
const C_PUB = hex(ed25519.getPublicKey(C_SEED));
const C_NULLIFIER = "3".repeat(64);

describe("server-issued keys and import (Codex review scenarios)", () => {
  it("same-identity re-verification keeps pk_polis and makes the new server key rotatable", async () => {
    legacyUser();
    const polisBefore = (await getOrDerivePolisKey())!.pkPolisHex;
    expect(await rotateLegacyKeyIfNeeded(deps().d)).toBe("rotated");

    await prepareForServerIssuedKey(NULLIFIER);
    await storeKeypair(C_PRIV, C_PUB);

    expect(await loadKeyOrigin()).toBe("server"); // marker bound to the replaced key
    expect((await getOrDerivePolisKey())!.pkPolisHex).toBe(polisBefore);
  });

  it("same identity without a prior rotation persists the seed of the key being replaced", async () => {
    legacyUser();
    const polisBefore = (await getOrDerivePolisKey())!.pkPolisHex;
    await prepareForServerIssuedKey(NULLIFIER);
    await storeKeypair(C_PRIV, C_PUB);
    expect((await getOrDerivePolisKey())!.pkPolisHex).toBe(polisBefore);
  });

  it("verification of another number deletes no recovery material before the new key is durable", async () => {
    legacyUser();
    // A->B applied on the server, response lost: A installed, B staged.
    await rotateLegacyKeyIfNeeded(deps({ rotate: new Error("lost") }).d);
    const before = new Map(state.values);
    await prepareForServerIssuedKey(C_NULLIFIER);
    expect(state.values).toEqual(before);
    // Crash before the new credentials are written: the next start recovers B.
    expect(await rotateLegacyKeyIfNeeded(deps({ rotateBody: { success: true, public_key_hex: NEW_PUB, already_rotated: true } }).d)).toBe("already_rotated");
    expect(state.values.get("ekklesia_private_key")).toBe(NEW_PRIV);
  });

  it("a successful import of another identity does not inherit the old marker, seed or staging", async () => {
    legacyUser();
    expect(await rotateLegacyKeyIfNeeded(deps().d)).toBe("rotated");
    await importAccountCredentials({ privateKey: C_PRIV, publicKey: C_PUB, nullifier: C_NULLIFIER });

    expect(await loadKeyOrigin()).toBe("server");
    const cPolis = hex(ed25519.getPublicKey((await getOrDerivePolisKey())!.privateKey));
    const { d, calls } = deps();
    expect(await rotateLegacyKeyIfNeeded(d)).toBe("rotated");
    expect(JSON.parse(String(rotateCalls(calls)[0].init!.body))).toMatchObject({ nullifier_hash: C_NULLIFIER, old_public_key_hex: C_PUB });
    // C's POLIS key comes from C's own key, never from A's preserved seed.
    expect(cPolis).not.toBe("");
    const seed = JSON.parse(state.values.get("ekklesia_polis_seed")!);
    expect(seed.nullifier).toBe(C_NULLIFIER);
  });

  it("import waits for an in-flight rotation, so a rollback cannot drop the server's new key", async () => {
    legacyUser();
    let release!: () => void;
    const gate = new Promise<void>((r) => { release = r; });
    const order: string[] = [];
    const rotation = rotateLegacyKeyIfNeeded(deps({ gate }).d).then((r) => { order.push(`rotation:${r}`); return r; });
    state.failImport = true;
    const importing = importAccountCredentials({ privateKey: C_PRIV, publicKey: C_PUB, nullifier: C_NULLIFIER })
      .then(() => order.push("import:ok"), () => order.push("import:rolled_back"));
    await new Promise((r) => setTimeout(r, 20));
    expect(order).toEqual([]); // import is queued behind the rotation
    release();
    await Promise.all([rotation, importing]);
    expect(order).toEqual(["rotation:rotated", "import:rolled_back"]);
    // Rollback restored the post-rotation state: the server's key B is installed.
    expect(state.values.get("ekklesia_private_key")).toBe(NEW_PRIV);
    expect(await loadKeyOrigin()).toBe("device");
  });

  it("a rotation started during an import is skipped, not interleaved", async () => {
    legacyUser();
    let release!: () => void;
    state.scopeGate = new Promise<void>((r) => { release = r; });
    const importing = importAccountCredentials({ privateKey: C_PRIV, publicKey: C_PUB, nullifier: C_NULLIFIER });
    await new Promise((r) => setTimeout(r, 10));
    const { d, calls } = deps();
    expect(await rotateLegacyKeyIfNeeded(d)).toBe("retry_later");
    expect(calls).toHaveLength(0);
    release();
    await importing;
    expect(state.values.get("ekklesia_public_key")).toBe(C_PUB);
  });

  it("the import's network phase does not hold the identity lock", async () => {
    legacyUser();
    let release!: () => void;
    state.scopeGate = new Promise<void>((r) => { release = r; });
    const importing = importAccountCredentials({ privateKey: C_PRIV, publicKey: C_PUB, nullifier: C_NULLIFIER });
    await new Promise((r) => setTimeout(r, 10));
    // e.g. a verification install can proceed while the scope request hangs
    await expect(withIdentityStateLock(async () => "free")).resolves.toBe("free");
    release();
    await importing;
  });

  it("Codex P1: killed import (keys written, nullifier not) is completed, not misread", async () => {
    legacyUser();
    await rotateLegacyKeyIfNeeded(deps({ rotate: new Error("lost") }).d); // A installed, B staged
    state.failWrite = "ekklesia_nullifier";
    state.failImport = false;
    await importAccountCredentials({ privateKey: C_PRIV, publicKey: C_PUB, nullifier: C_NULLIFIER }).catch(() => {});
    // Simulated restart: the journal (if left) is rolled forward first.
    await recoverIdentityJournal();
    const installed = [state.values.get("ekklesia_private_key"), state.values.get("ekklesia_public_key"), state.values.get("ekklesia_nullifier")];
    // Either fully A (rollback ran) or fully C (rolled forward) — never mixed.
    expect([[OLD_PRIV, OLD_PUB, NULLIFIER], [C_PRIV, C_PUB, C_NULLIFIER]]).toContainEqual(installed);
    if (installed[2] === NULLIFIER) {
      // A restored: its staged B must still be there to recover the server key.
      expect(JSON.parse(state.values.get("ekklesia_rotation_staging")!).publicKeyHex).toBe(NEW_PUB);
    }
  });

  it("Codex P1 (hard kill, no rollback): the import journal is rolled forward, then stale staging is dropped", async () => {
    legacyUser();
    await rotateLegacyKeyIfNeeded(deps({ rotate: new Error("lost") }).d); // A installed, B staged
    // App killed after the import journal and the two keys, before the nullifier.
    state.values.set("ekklesia_identity_journal", JSON.stringify({
      ekklesia_private_key: C_PRIV, ekklesia_public_key: C_PUB, ekklesia_nullifier: C_NULLIFIER,
    }));
    state.values.set("ekklesia_private_key", C_PRIV);
    state.values.set("ekklesia_public_key", C_PUB);
    const freshSeed = Uint8Array.from({ length: 32 }, (_, i) => 70 + i);
    const { d, calls } = deps();
    d.randomBytes = () => freshSeed.slice();
    await withIdentityStateLock(async () => undefined); // app start: journal rolled forward
    expect(state.values.get("ekklesia_nullifier")).toBe(C_NULLIFIER);
    expect(await rotateLegacyKeyIfNeeded(d)).toBe("rotated");
    expect(JSON.parse(String(rotateCalls(calls)[0].init!.body))).toMatchObject({ nullifier_hash: C_NULLIFIER, old_public_key_hex: C_PUB });
  });

  it("Codex P1: an obsolete rotation is never finalised over a newer server key", async () => {
    legacyUser();
    state.failWrite = "ekklesia_key_origin"; // rotation commit killed before the marker
    await rotateLegacyKeyIfNeeded(deps().d).catch(() => {});
    await recoverIdentityJournal(); // restart: B committed (the server holds B)
    expect(await loadKeyOrigin()).toBe("device");
    // Same-number verification issues C; killed between private and public key.
    state.failWrite = "ekklesia_public_key";
    await withIdentityStateLock(() => installServerIssuedCredentials(C_PRIV, C_PUB, NULLIFIER)).catch(() => {});
    await recoverIdentityJournal();
    expect(state.values.get("ekklesia_private_key")).toBe(C_PRIV);
    expect(state.values.get("ekklesia_public_key")).toBe(C_PUB);
    expect(await loadKeyOrigin()).toBe("server");
    const freshSeed = Uint8Array.from({ length: 32 }, (_, i) => 50 + i);
    const { d, calls } = deps();
    d.randomBytes = () => freshSeed.slice();
    expect(await rotateLegacyKeyIfNeeded(d)).toBe("rotated");
    expect(JSON.parse(String(rotateCalls(calls)[0].init!.body)).old_public_key_hex).toBe(C_PUB);
  });

  it("Codex P2: a mixed key pair is neither trusted as device-origin nor rotated", async () => {
    legacyUser();
    state.values.set("ekklesia_private_key", C_PRIV); // legacy crash without journal: C private, A public
    state.values.set("ekklesia_key_origin", OLD_PUB);
    expect(await loadKeyOrigin()).toBe("server");
    const { d, calls } = deps();
    expect(await rotateLegacyKeyIfNeeded(d)).toBe("skipped");
    expect(calls).toHaveLength(0);
  });

  it("drops staging that belongs to credentials no longer installed", async () => {
    legacyUser();
    await rotateLegacyKeyIfNeeded(deps({ rotate: 500 }).d); // B staged for A
    await storeKeypair(C_PRIV, C_PUB); // v1 re-verification of the same number issued C
    const freshSeed = Uint8Array.from({ length: 32 }, (_, i) => 90 + i);
    const { d, calls } = deps();
    d.randomBytes = () => freshSeed.slice();
    expect(await rotateLegacyKeyIfNeeded(d)).toBe("rotated");
    const body = JSON.parse(String(rotateCalls(calls)[0].init!.body));
    expect(body.old_public_key_hex).toBe(C_PUB);
    // A fresh key, not the stale staging prepared for A.
    expect(body.new_public_key_hex).toBe(hex(ed25519.getPublicKey(freshSeed)));
  });
});
