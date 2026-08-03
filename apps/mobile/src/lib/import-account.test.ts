import { beforeEach, describe, expect, it, vi } from "vitest";
import { ed25519 } from "@noble/curves/ed25519.js";

const state = vi.hoisted(() => ({
  values: new Map<string, string>(),
  failOnceForKey: null as string | null,
  checkIdentityStatus: vi.fn(),
}));

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(async (key: string) => {
    if (key.includes(":")) throw new Error(`invalid SecureStore key: ${key}`);
    return state.values.get(key) ?? null;
  }),
  setItemAsync: vi.fn(async (key: string, value: string) => {
    if (state.failOnceForKey === key) {
      state.failOnceForKey = null;
      throw new Error(`write failed: ${key}`);
    }
    state.values.set(key, value);
  }),
  deleteItemAsync: vi.fn(async (key: string) => {
    if (key.includes(":")) throw new Error(`invalid SecureStore key: ${key}`);
    state.values.delete(key);
  }),
}));

vi.mock("./api", () => ({
  checkIdentityStatus: state.checkIdentityStatus,
  updateIdentityLocation: vi.fn(),
}));

vi.mock("./crypto-native", () => ({
  signProfileLocation: vi.fn(),
}));

import { importAccountCredentials } from "./import-account";

const PRIVATE_KEY = "01".repeat(32);
const PUBLIC_KEY = Array.from(
  ed25519.getPublicKey(Uint8Array.from({ length: 32 }, () => 1)),
  (byte) => byte.toString(16).padStart(2, "0"),
).join("");

const NEW_ACCOUNT = {
  privateKey: PRIVATE_KEY,
  publicKey: PUBLIC_KEY,
  nullifier: "3".repeat(64),
};

describe("importAccountCredentials", () => {
  beforeEach(() => {
    state.values.clear();
    state.failOnceForKey = null;
    vi.clearAllMocks();
    state.checkIdentityStatus.mockResolvedValue({
      status: "ACTIVE",
      created_at: null,
      region_locked: true,
      periferia_id: 6,
      dimos_id: 22,
    });
  });

  it("caches only the imported server scope without invalid legacy-key access", async () => {
    state.values.set("user_periferia_id", "7");
    state.values.set("user_dimos_id", "33");
    state.values.set("user_bill_scope_owner", "a".repeat(64));
    state.values.set("ekklesia_nullifier_root", "e".repeat(64));
    state.values.set("ekklesia_identity_commitment", "old-commitment");
    state.values.set("polis_registered", "old-polis-key");

    await importAccountCredentials(NEW_ACCOUNT);

    expect(state.checkIdentityStatus).toHaveBeenCalledWith(NEW_ACCOUNT.nullifier);
    expect(state.values.get("user_periferia_id")).toBe("6");
    expect(state.values.get("user_dimos_id")).toBe("22");
    expect(state.values.get("user_bill_scope_owner")).toBe(NEW_ACCOUNT.nullifier);
    expect(state.values.get("ekklesia_nullifier_root")).toBeUndefined();
    expect(state.values.get("ekklesia_identity_commitment")).toBeUndefined();
    expect(state.values.get("polis_registered")).toBeUndefined();
    expect(state.values.get("onboarding_completed")).toBe("true");
  });

  it("stays NATIONAL-only when the authoritative status request is offline", async () => {
    state.values.set("user_periferia_id", "7");
    state.values.set("user_dimos_id", "33");
    state.values.set("user_bill_scope_owner", "old-identity");
    state.checkIdentityStatus.mockRejectedValueOnce(new Error("offline"));

    await importAccountCredentials(NEW_ACCOUNT);

    expect(state.values.get("user_periferia_id")).toBeUndefined();
    expect(state.values.get("user_dimos_id")).toBeUndefined();
    expect(state.values.get("user_bill_scope_owner")).toBe(NEW_ACCOUNT.nullifier);
    expect(state.values.get("user_profile_completed")).toBe("true");
  });

  it("restores the complete previous account state after a partial write failure", async () => {
    const previous = new Map<string, string>([
      ["ekklesia_private_key", "a".repeat(64)],
      ["ekklesia_public_key", "b".repeat(64)],
      ["ekklesia_nullifier", "c".repeat(64)],
      ["ekklesia_nullifier_root", "e".repeat(64)],
      ["ekklesia_identity_commitment", "old-commitment"],
      ["polis_registered", "old-polis-key"],
      ["user_periferia_id", "7"],
      ["user_dimos_id", "33"],
      ["user_bill_scope_owner", "d".repeat(64)],
      ["pending_user_periferia_id", "8"],
      ["pending_user_dimos_id", "44"],
      ["onboarding_completed", "old"],
      ["user_profile_completed", "old"],
    ]);
    previous.forEach((value, key) => state.values.set(key, value));
    state.failOnceForKey = "user_profile_completed";

    await expect(importAccountCredentials(NEW_ACCOUNT))
      .rejects.toThrow("write failed: user_profile_completed");

    expect(state.values).toEqual(previous);
  });

  it("rejects malformed credentials before changing storage", async () => {
    state.values.set("ekklesia_nullifier", "f".repeat(64));
    const before = new Map(state.values);

    await expect(importAccountCredentials({
      ...NEW_ACCOUNT,
      publicKey: "not-hex",
    })).rejects.toThrow("Invalid public key");

    expect(state.values).toEqual(before);
    expect(state.checkIdentityStatus).not.toHaveBeenCalled();
  });

  it("rejects a well-formed public key that does not match the private key", async () => {
    await expect(importAccountCredentials({
      ...NEW_ACCOUNT,
      publicKey: "9".repeat(64),
    })).rejects.toThrow("Imported Ed25519 key pair does not match");

    expect(state.values.size).toBe(0);
    expect(state.checkIdentityStatus).not.toHaveBeenCalled();
  });
});
