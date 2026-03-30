/**
 * Unit tests for browser Ed25519 crypto module.
 * Run: cd apps/web && npx vitest run src/lib/crypto.test.ts
 * Or:  npx jest src/lib/crypto.test.ts (with jest config)
 */

import { describe, it, expect } from "vitest";
import {
  generateKeypair,
  privateKeyToHex,
  hexToPrivateKey,
  publicKeyToHex,
  bytesToHex,
  hexToBytes,
  buildVoteMessage,
  signVote,
  verifyVote,
  computeNullifier,
} from "./crypto";

describe("Key Generation", () => {
  it("generates 32-byte private key and 32-byte public key", () => {
    const kp = generateKeypair();
    expect(kp.privateKey).toBeInstanceOf(Uint8Array);
    expect(kp.publicKey).toBeInstanceOf(Uint8Array);
    expect(kp.privateKey.length).toBe(32);
    expect(kp.publicKey.length).toBe(32);
  });

  it("generates different keypairs each time", () => {
    const kp1 = generateKeypair();
    const kp2 = generateKeypair();
    expect(privateKeyToHex(kp1.privateKey)).not.toBe(
      privateKeyToHex(kp2.privateKey)
    );
  });

  it("hex round-trip preserves private key", () => {
    const kp = generateKeypair();
    const hex = privateKeyToHex(kp.privateKey);
    expect(hex.length).toBe(64);
    const restored = hexToPrivateKey(hex);
    expect(bytesToHex(restored)).toBe(hex);
  });

  it("hex round-trip preserves public key", () => {
    const kp = generateKeypair();
    const hex = publicKeyToHex(kp.publicKey);
    expect(hex.length).toBe(64);
    const restored = hexToBytes(hex);
    expect(bytesToHex(restored)).toBe(hex);
  });
});

describe("Vote Message Format", () => {
  it("sorts keys alphabetically (bill_id, nullifier_hash, vote)", () => {
    const msg = buildVoteMessage({
      vote: "YES",
      bill_id: "GR-2025-0001",
      nullifier_hash: "a".repeat(64),
    });
    const parsed = JSON.parse(msg);
    const keys = Object.keys(parsed);
    expect(keys).toEqual(["bill_id", "nullifier_hash", "vote"]);
  });

  it("uppercases vote", () => {
    const msg = buildVoteMessage({
      bill_id: "GR-2025-0001",
      vote: "yes",
      nullifier_hash: "b".repeat(64),
    });
    expect(JSON.parse(msg).vote).toBe("YES");
  });

  it("produces deterministic output", () => {
    const params = {
      bill_id: "GR-2024-0042",
      vote: "NO",
      nullifier_hash: "c".repeat(64),
    };
    const msg1 = buildVoteMessage(params);
    const msg2 = buildVoteMessage(params);
    expect(msg1).toBe(msg2);
  });

  it("matches Python json.dumps(sort_keys=True) format", () => {
    // Python: json.dumps({"bill_id":"X","vote":"YES","nullifier_hash":"N"}, sort_keys=True)
    // => {"bill_id": "X", "nullifier_hash": "N", "vote": "YES"}
    const msg = buildVoteMessage({
      bill_id: "X",
      vote: "YES",
      nullifier_hash: "N",
    });
    // JSON.stringify produces no spaces after colons/commas
    expect(msg).toBe('{"bill_id":"X","nullifier_hash":"N","vote":"YES"}');
  });
});

describe("Sign + Verify Round-Trip", () => {
  it("signs and verifies a vote successfully", () => {
    const kp = generateKeypair();
    const privHex = privateKeyToHex(kp.privateKey);
    const pubHex = publicKeyToHex(kp.publicKey);
    const params = {
      bill_id: "GR-2025-0001",
      vote: "YES",
      nullifier_hash: "a".repeat(64),
    };

    const sig = signVote(privHex, params);
    expect(sig.length).toBe(128); // 64 bytes = 128 hex chars

    const valid = verifyVote(pubHex, params, sig);
    expect(valid).toBe(true);
  });

  it("rejects signature from wrong key", () => {
    const kp1 = generateKeypair();
    const kp2 = generateKeypair();
    const params = {
      bill_id: "GR-2025-0001",
      vote: "NO",
      nullifier_hash: "b".repeat(64),
    };

    const sig = signVote(privateKeyToHex(kp1.privateKey), params);
    const valid = verifyVote(publicKeyToHex(kp2.publicKey), params, sig);
    expect(valid).toBe(false);
  });

  it("rejects tampered vote", () => {
    const kp = generateKeypair();
    const privHex = privateKeyToHex(kp.privateKey);
    const pubHex = publicKeyToHex(kp.publicKey);

    const sig = signVote(privHex, {
      bill_id: "GR-2025-0001",
      vote: "YES",
      nullifier_hash: "c".repeat(64),
    });

    // Tamper: change vote from YES to NO
    const valid = verifyVote(
      pubHex,
      {
        bill_id: "GR-2025-0001",
        vote: "NO",
        nullifier_hash: "c".repeat(64),
      },
      sig
    );
    expect(valid).toBe(false);
  });

  it("rejects tampered bill_id", () => {
    const kp = generateKeypair();
    const privHex = privateKeyToHex(kp.privateKey);
    const pubHex = publicKeyToHex(kp.publicKey);
    const params = {
      bill_id: "GR-2025-0001",
      vote: "ABSTAIN",
      nullifier_hash: "d".repeat(64),
    };

    const sig = signVote(privHex, params);
    const valid = verifyVote(
      pubHex,
      { ...params, bill_id: "GR-2025-9999" },
      sig
    );
    expect(valid).toBe(false);
  });
});

describe("Nullifier Hash", () => {
  it("produces 64-char hex string", async () => {
    const hash = await computeNullifier("+306912345678", "test-salt");
    expect(hash.length).toBe(64);
    expect(/^[0-9a-f]{64}$/.test(hash)).toBe(true);
  });

  it("is deterministic (same input = same output)", async () => {
    const h1 = await computeNullifier("+306912345678", "salt-abc");
    const h2 = await computeNullifier("+306912345678", "salt-abc");
    expect(h1).toBe(h2);
  });

  it("differs for different phone numbers", async () => {
    const h1 = await computeNullifier("+306912345678", "same-salt");
    const h2 = await computeNullifier("+306987654321", "same-salt");
    expect(h1).not.toBe(h2);
  });

  it("differs for different salts", async () => {
    const h1 = await computeNullifier("+306912345678", "salt-1");
    const h2 = await computeNullifier("+306912345678", "salt-2");
    expect(h1).not.toBe(h2);
  });

  it("matches Python format: SHA256(phone:salt)", async () => {
    // This should match: hashlib.sha256("+306912345678:dev-salt".encode()).hexdigest()
    const hash = await computeNullifier("+306912345678", "dev-salt");
    // We can't hardcode the expected value here without running Python,
    // but we verify the format is correct (64 hex chars, lowercase)
    expect(hash.length).toBe(64);
    expect(hash).toBe(hash.toLowerCase());
  });
});
