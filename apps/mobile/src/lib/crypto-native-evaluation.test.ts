import { ed25519 } from "@noble/curves/ed25519.js";
import { describe, expect, it, vi } from "vitest";

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn(() => Promise.resolve(null)),
  setItemAsync: vi.fn(() => Promise.resolve()),
  deleteItemAsync: vi.fn(() => Promise.resolve()),
}));

import {
  buildEvaluationV2Payload,
  buildEvaluationReadPayload,
  hexToBytes,
  signEvaluationRead,
  signEvaluationV2,
} from "./crypto-native";

describe("evaluation v2 signatures", () => {
  const scores = [
    { question_id: 8, score: 5 },
    { question_id: 2, score: -3 },
  ];

  it("matches the backend golden vector regardless of score order", () => {
    expect(buildEvaluationV2Payload(
      "ADA-ΕΛ-1",
      "a".repeat(64),
      1787999123456,
      scores,
    )).toBe(
      `evaluate:v2:["ADA-ΕΛ-1","${"a".repeat(64)}",1787999123456,[[2,-3],[8,5]]]`,
    );
  });

  it("binds the complete canonical payload to the signature", () => {
    const privateKeyHex = "01".repeat(32);
    const publicKey = ed25519.getPublicKey(hexToBytes(privateKeyHex));
    const payload = buildEvaluationV2Payload("ADA-1", "b".repeat(64), 123456, scores);
    const signature = signEvaluationV2(
      privateKeyHex,
      "ADA-1",
      "b".repeat(64),
      123456,
      scores,
    );

    expect(ed25519.verify(
      hexToBytes(signature),
      new TextEncoder().encode(payload),
      publicKey,
    )).toBe(true);
    expect(ed25519.verify(
      hexToBytes(signature),
      new TextEncoder().encode(buildEvaluationV2Payload(
        "ADA-1",
        "b".repeat(64),
        123456,
        [{ question_id: 2, score: -2 }, { question_id: 8, score: 5 }],
      )),
      publicKey,
    )).toBe(false);
  });

  it("rejects ambiguous duplicate question IDs", () => {
    expect(() => buildEvaluationV2Payload(
      "ADA-1",
      "c".repeat(64),
      123456,
      [{ question_id: 2, score: -3 }, { question_id: 2, score: 5 }],
    )).toThrow("Evaluation question IDs must be unique.");
  });
});

describe("personal evaluation read signatures", () => {
  const nullifier = "a".repeat(64);
  const timestamp = 1788000000000;

  it.each(["ADA-ΕΛ-1", null])("matches the backend golden vector for %s", (ada) => {
    expect(buildEvaluationReadPayload(ada, nullifier, timestamp)).toBe(
      `evaluation-read:v1:[${ada === null ? "null" : `"${ada}"`},"${nullifier}",${timestamp}]`,
    );
  });

  it.each(["ADA-ΕΛ-1", null])("binds target, owner, time and operation for %s", (ada) => {
    const privateKey = "01".repeat(32);
    const publicKey = ed25519.getPublicKey(hexToBytes(privateKey));
    const signature = hexToBytes(signEvaluationRead(privateKey, ada, nullifier, timestamp));
    const valid = buildEvaluationReadPayload(ada, nullifier, timestamp);
    expect(ed25519.verify(signature, new TextEncoder().encode(valid), publicKey)).toBe(true);
    for (const changed of [
      buildEvaluationReadPayload(ada === null ? "ADA-ΕΛ-1" : null, nullifier, timestamp),
      buildEvaluationReadPayload("ADA-OTHER", nullifier, timestamp),
      buildEvaluationReadPayload(ada, "b".repeat(64), timestamp),
      buildEvaluationReadPayload(ada, nullifier, timestamp + 1),
      `evaluate:${ada}:${nullifier}`,
    ]) {
      expect(ed25519.verify(signature, new TextEncoder().encode(changed), publicKey)).toBe(false);
    }
  });

  it.each([-1, 1.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1])(
    "rejects unsafe timestamps: %s", (timestampMs) => {
      expect(() => buildEvaluationReadPayload(null, nullifier, timestampMs)).toThrow();
    },
  );
});
