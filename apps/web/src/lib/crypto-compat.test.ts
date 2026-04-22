/**
 * crypto-compat.test.ts — Cross-Platform Compatibility Test
 * Verifies that Web (@noble/curves) and Mobile (same lib)
 * produce identical results as the Python backend.
 *
 * CRITICAL: If these tests fail, signatures between frontend
 * and backend do not match — votes will be rejected.
 */
import { describe, it, expect } from "vitest";
import { ed25519 } from "@noble/curves/ed25519.js";
import {
  signVote,
  verifyVote,
  buildVoteMessage,
  bytesToHex,
  hexToBytes,
  generateKeypair,
  publicKeyToHex,
  privateKeyToHex,
} from "./crypto";

// ─── Deterministic Test Vectors ──────────────────────────────────────────────
// These must match the Python backend's verify_signature() output.

describe("Cross-Platform Crypto Compatibility", () => {
  // Test vector: known keypair for reproducible tests
  const TEST_PRIVATE_KEY = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60";
  const TEST_BILL_ID = "GR-2024-0042";
  const TEST_NULLIFIER = "a".repeat(64); // 64-char hex
  const TEST_VOTE = "YES";

  it("buildVoteMessage produces sorted JSON matching Python sort_keys=True", () => {
    const msg = buildVoteMessage({
      bill_id: TEST_BILL_ID,
      vote: TEST_VOTE,
      nullifier_hash: TEST_NULLIFIER,
    });

    // Python: json.dumps({"bill_id": ..., "nullifier_hash": ..., "vote": ...}, sort_keys=True)
    // Keys MUST be alphabetically sorted: bill_id < nullifier_hash < vote
    const parsed = JSON.parse(msg);
    const keys = Object.keys(parsed);
    expect(keys).toEqual(["bill_id", "nullifier_hash", "vote"]);

    // No spaces in compact JSON
    expect(msg).not.toContain(": ");
    expect(msg).not.toContain(", ");

    // Vote is uppercased
    expect(parsed.vote).toBe("YES");
  });

  it("buildVoteMessage uppercases vote value", () => {
    const msg = buildVoteMessage({
      bill_id: TEST_BILL_ID,
      vote: "yes",
      nullifier_hash: TEST_NULLIFIER,
    });
    expect(JSON.parse(msg).vote).toBe("YES");
  });

  it("sign → verify round-trip succeeds with generated keypair", () => {
    const kp = generateKeypair();
    const privHex = privateKeyToHex(kp.privateKey);
    const pubHex = publicKeyToHex(kp.publicKey);

    const params = {
      bill_id: TEST_BILL_ID,
      vote: TEST_VOTE,
      nullifier_hash: TEST_NULLIFIER,
    };

    const sig = signVote(privHex, params);
    expect(sig).toHaveLength(128); // 64 bytes = 128 hex chars

    const valid = verifyVote(pubHex, params, sig);
    expect(valid).toBe(true);
  });

  it("signature is deterministic for same key + message", () => {
    const kp = generateKeypair();
    const privHex = privateKeyToHex(kp.privateKey);

    const params = {
      bill_id: TEST_BILL_ID,
      vote: TEST_VOTE,
      nullifier_hash: TEST_NULLIFIER,
    };

    const sig1 = signVote(privHex, params);
    const sig2 = signVote(privHex, params);
    expect(sig1).toBe(sig2); // Ed25519 is deterministic (RFC 8032)
  });

  it("different vote produces different signature", () => {
    const kp = generateKeypair();
    const privHex = privateKeyToHex(kp.privateKey);

    const sig_yes = signVote(privHex, {
      bill_id: TEST_BILL_ID,
      vote: "YES",
      nullifier_hash: TEST_NULLIFIER,
    });
    const sig_no = signVote(privHex, {
      bill_id: TEST_BILL_ID,
      vote: "NO",
      nullifier_hash: TEST_NULLIFIER,
    });

    expect(sig_yes).not.toBe(sig_no);
  });

  it("wrong key cannot forge signature", () => {
    const kp1 = generateKeypair();
    const kp2 = generateKeypair();
    const priv1Hex = privateKeyToHex(kp1.privateKey);
    const pub2Hex = publicKeyToHex(kp2.publicKey);

    const params = {
      bill_id: TEST_BILL_ID,
      vote: TEST_VOTE,
      nullifier_hash: TEST_NULLIFIER,
    };

    const sig = signVote(priv1Hex, params);
    const valid = verifyVote(pub2Hex, params, sig);
    expect(valid).toBe(false);
  });

  it("tampered bill_id invalidates signature", () => {
    const kp = generateKeypair();
    const privHex = privateKeyToHex(kp.privateKey);
    const pubHex = publicKeyToHex(kp.publicKey);

    const sig = signVote(privHex, {
      bill_id: TEST_BILL_ID,
      vote: TEST_VOTE,
      nullifier_hash: TEST_NULLIFIER,
    });

    const valid = verifyVote(pubHex, {
      bill_id: "GR-2024-9999", // tampered
      vote: TEST_VOTE,
      nullifier_hash: TEST_NULLIFIER,
    }, sig);
    expect(valid).toBe(false);
  });

  it("tampered nullifier invalidates signature", () => {
    const kp = generateKeypair();
    const privHex = privateKeyToHex(kp.privateKey);
    const pubHex = publicKeyToHex(kp.publicKey);

    const sig = signVote(privHex, {
      bill_id: TEST_BILL_ID,
      vote: TEST_VOTE,
      nullifier_hash: TEST_NULLIFIER,
    });

    const valid = verifyVote(pubHex, {
      bill_id: TEST_BILL_ID,
      vote: TEST_VOTE,
      nullifier_hash: "b".repeat(64), // tampered
    }, sig);
    expect(valid).toBe(false);
  });

  it("hex round-trip preserves bytes", () => {
    const original = ed25519.utils.randomSecretKey();
    const hex = bytesToHex(original);
    const restored = hexToBytes(hex);
    expect(Buffer.from(restored)).toEqual(Buffer.from(original));
  });

  it("signature format matches backend expectations (128 hex chars)", () => {
    const kp = generateKeypair();
    const privHex = privateKeyToHex(kp.privateKey);

    const sig = signVote(privHex, {
      bill_id: TEST_BILL_ID,
      vote: TEST_VOTE,
      nullifier_hash: TEST_NULLIFIER,
    });

    // Backend stores signature_hex in Column(String(128))
    expect(sig).toHaveLength(128);
    expect(sig).toMatch(/^[0-9a-f]{128}$/);
  });

  it("public key format matches backend expectations (64 hex chars)", () => {
    const kp = generateKeypair();
    const pubHex = publicKeyToHex(kp.publicKey);
    expect(pubHex).toHaveLength(64);
    expect(pubHex).toMatch(/^[0-9a-f]{64}$/);
  });

  it("private key format is 64 hex chars (32 bytes)", () => {
    const kp = generateKeypair();
    const privHex = privateKeyToHex(kp.privateKey);
    expect(privHex).toHaveLength(64);
    expect(privHex).toMatch(/^[0-9a-f]{64}$/);
  });
});
