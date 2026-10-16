import { beforeEach, describe, expect, it, vi } from "vitest";
import { ed25519 } from "@noble/curves/ed25519.js";

const state = vi.hoisted(() => ({
  values: new Map<string, string>(),
  demo: false,
}));

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(async (key: string) => state.values.get(key) ?? null),
  setItemAsync: vi.fn(async (key: string, value: string) => {
    state.values.set(key, value);
  }),
  deleteItemAsync: vi.fn(async (key: string) => {
    state.values.delete(key);
  }),
}));
vi.mock("expo-crypto", () => ({ getRandomBytes: vi.fn() }));
vi.mock("./demo", () => ({ isDemoMode: vi.fn(async () => state.demo) }));

import { getOrDerivePolisKey, resetKeyLifecycleForServerKey, storeKeypair } from "./crypto-native";
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

function deps(opts: { rotate?: number | Error; rotateBody?: unknown; feature?: boolean | "down" } = {}) {
  const calls: Call[] = [];
  const fetchImpl = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    if (url.endsWith("/api/v1/app/version")) {
      if (opts.feature === "down") throw new Error("offline");
      return new Response(JSON.stringify({ features: { identity_rotate: opts.feature ?? true } }), { status: 200 });
    }
    if (opts.rotate instanceof Error) throw opts.rotate;
    const status = opts.rotate ?? 200;
    const body = opts.rotateBody ?? (status === 200 ? { success: true, public_key_hex: NEW_PUB, already_rotated: false } : { detail: "x" });
    return new Response(JSON.stringify(body), { status });
  });
  const d: RotationDeps = { apiBase: API, fetchImpl: fetchImpl as unknown as typeof fetch, randomBytes: () => NEW_SEED.slice(), now: () => 1_700_000_000_000 };
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
    expect(state.values.get("ekklesia_key_origin")).toBe("device");
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
    ["device origin", () => { legacyUser(); state.values.set("ekklesia_key_origin", "device"); }, "not_needed"],
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

  it("finalises an interrupted local commit without calling the server", async () => {
    legacyUser();
    await rotateLegacyKeyIfNeeded(deps({ rotate: new Error("network") }).d);
    // Crash after the private key was written but before the public key.
    state.values.set("ekklesia_private_key", NEW_PRIV);
    const { d, calls } = deps();
    expect(await rotateLegacyKeyIfNeeded(d)).toBe("finalized");
    expect(calls).toHaveLength(0);
    expect(state.values.get("ekklesia_public_key")).toBe(NEW_PUB);
    expect(state.values.get("ekklesia_key_origin")).toBe("device");
  });

  it("ignores a corrupt staging slot", async () => {
    legacyUser();
    state.values.set("ekklesia_rotation_staging", JSON.stringify({ privateKeyHex: OLD_PRIV, publicKeyHex: NEW_PUB }));
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

describe("resetKeyLifecycleForServerKey (v1 re-verification)", () => {
  it("same identity: keeps pk_polis stable across a new server key and allows a later rotation", async () => {
    legacyUser();
    const polisBefore = (await getOrDerivePolisKey())!.pkPolisHex;
    expect(await rotateLegacyKeyIfNeeded(deps().d)).toBe("rotated");
    state.values.set("ekklesia_rotation_staging", "leftover");

    // Re-verification of the same number issues a new server key.
    await resetKeyLifecycleForServerKey(NULLIFIER);
    await storeKeypair("cd".repeat(32), hex(ed25519.getPublicKey(Uint8Array.from({ length: 32 }, () => 0xcd))));

    expect(state.values.has("ekklesia_key_origin")).toBe(false);
    expect(state.values.has("ekklesia_rotation_staging")).toBe(false);
    expect((await getOrDerivePolisKey())!.pkPolisHex).toBe(polisBefore);
  });

  it("same identity without a prior rotation: persists the seed of the key being replaced", async () => {
    legacyUser();
    const polisBefore = (await getOrDerivePolisKey())!.pkPolisHex;
    await resetKeyLifecycleForServerKey(NULLIFIER);
    await storeKeypair("cd".repeat(32), hex(ed25519.getPublicKey(Uint8Array.from({ length: 32 }, () => 0xcd))));
    expect((await getOrDerivePolisKey())!.pkPolisHex).toBe(polisBefore);
  });

  it("different identity: drops the previous POLIS seed", async () => {
    legacyUser();
    expect(await rotateLegacyKeyIfNeeded(deps().d)).toBe("rotated");
    await resetKeyLifecycleForServerKey("2".repeat(64));
    expect(state.values.has("ekklesia_polis_seed")).toBe(false);
    expect(state.values.has("ekklesia_key_origin")).toBe(false);
  });
});
