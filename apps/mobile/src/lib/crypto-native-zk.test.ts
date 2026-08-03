import { ed25519 } from "@noble/curves/ed25519.js";
import { beforeEach, describe, expect, it, vi } from "vitest";

const secureStore = vi.hoisted(() => new Map<string, string>());

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn((key: string) => Promise.resolve(secureStore.get(key) ?? null)),
  setItemAsync: vi.fn((key: string, value: string) => {
    secureStore.set(key, value);
    return Promise.resolve();
  }),
  deleteItemAsync: vi.fn((key: string) => {
    secureStore.delete(key);
    return Promise.resolve();
  }),
}));

import {
  bytesToHex,
  hexToBytes,
  signProfileLocation,
  signZkOptInPayload,
  storeKeypair,
  storeNullifier,
} from "./crypto-native";

describe("signProfileLocation", () => {
  it("signs the exact backend canonical geography payload", () => {
    const privateKeyHex = "02".repeat(32);
    const publicKey = ed25519.getPublicKey(hexToBytes(privateKeyHex));
    const nullifier = "n".repeat(64);
    const signature = signProfileLocation(privateKeyHex, 6, 22, nullifier);

    expect(ed25519.verify(
      hexToBytes(signature),
      new TextEncoder().encode(`profile-location:6:22:${nullifier}`),
      publicKey,
    )).toBe(true);
  });
});

describe("signZkOptInPayload", () => {
  beforeEach(() => {
    secureStore.clear();
  });

  it("signs the backend canonical opt-in payload with the existing Tier-1 key", async () => {
    const privateKeyHex = "01".repeat(32);
    const publicKeyHex = bytesToHex(ed25519.getPublicKey(hexToBytes(privateKeyHex)));
    await storeKeypair(privateKeyHex, publicKeyHex);
    await storeNullifier("nullifier-hash-1");

    const result = await signZkOptInPayload("ZK-CANARY-001", "123456789");

    expect(result.nullifierHash).toBe("nullifier-hash-1");
    expect(ed25519.verify(
      hexToBytes(result.signatureHex),
      new TextEncoder().encode("zk_opt_in:ZK-CANARY-001:123456789:nullifier-hash-1"),
      hexToBytes(publicKeyHex),
    )).toBe(true);
  });

  it("fails closed when the verified Tier-1 identity is missing", async () => {
    await expect(signZkOptInPayload("ZK-CANARY-001", "123456789"))
      .rejects.toThrow("No verified identity key available for ZK opt-in.");
  });
});
