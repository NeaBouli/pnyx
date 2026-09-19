import { ed25519 } from "@noble/curves/ed25519.js";
import { describe, expect, it, vi } from "vitest";

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(() => Promise.resolve(null)),
  setItemAsync: vi.fn(() => Promise.resolve()),
  deleteItemAsync: vi.fn(() => Promise.resolve()),
}));

import {
  buildVoteStatusReadPayload,
  hexToBytes,
  signVoteStatusRead,
} from "./crypto-native";

describe("vote status read signatures", () => {
  const billId = "GR-0490a766";
  const nullifier = "a".repeat(64);
  const timestamp = 1788000000000;

  it("matches the backend golden vector", () => {
    expect(buildVoteStatusReadPayload(billId, nullifier, timestamp)).toBe(
      `vote-status-read:v1:["${billId}","${nullifier}",${timestamp}]`,
    );
    expect(buildVoteStatusReadPayload("ADA-ΕΛ-1", nullifier, timestamp)).toBe(
      `vote-status-read:v1:["ADA-ΕΛ-1","${nullifier}",${timestamp}]`,
    );
  });

  it("binds target, owner, time and operation", () => {
    const privateKey = "01".repeat(32);
    const publicKey = ed25519.getPublicKey(hexToBytes(privateKey));
    const signature = hexToBytes(signVoteStatusRead(privateKey, billId, nullifier, timestamp));
    const valid = buildVoteStatusReadPayload(billId, nullifier, timestamp);
    expect(ed25519.verify(signature, new TextEncoder().encode(valid), publicKey)).toBe(true);
    for (const changed of [
      buildVoteStatusReadPayload("GR-OTHER", nullifier, timestamp),
      buildVoteStatusReadPayload(billId, "b".repeat(64), timestamp),
      buildVoteStatusReadPayload(billId, nullifier, timestamp + 1),
      `flag:v1:${JSON.stringify([billId, nullifier, timestamp])}`,
      `evaluation-read:v1:${JSON.stringify([billId, nullifier, timestamp])}`,
    ]) {
      expect(ed25519.verify(signature, new TextEncoder().encode(changed), publicKey)).toBe(false);
    }
  });

  it.each([-1, 1.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1])(
    "rejects unsafe timestamps: %s",
    (timestampMs) => {
      expect(() => buildVoteStatusReadPayload(billId, nullifier, timestampMs)).toThrow();
    },
  );
});
