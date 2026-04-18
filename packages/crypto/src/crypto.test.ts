/**
 * @file crypto.test.ts
 * @description Tests for packages/crypto/src/nullifier.ts and polis.ts
 *
 * Run with: npx vitest run
 * (or jest if configured)
 *
 * Note: deriveNullifierRoot() is async (Argon2id) and intentionally slow.
 * Tests use a pre-derived root constant to keep suite fast.
 */

import { describe, it, expect, beforeAll } from "vitest";
import { ed25519 }  from "@noble/curves/ed25519";
import { sha256 }   from "@noble/hashes/sha256";
import { hmac }     from "@noble/hashes/hmac";
import { bytesToHex, hexToBytes, utf8ToBytes } from "@noble/hashes/utils";

import {
  deriveIdentityCommitment,
  deriveVoteNullifier,
  deriveLinkageTag,
  deriveEphemeralKeypair,
  buildSignedPayload,
  buildVotePayload,
  verifyReceipt,
} from "../src/nullifier.js";

import {
  derivePolisKeypair,
  deriveTicketNullifier,
  deriveTicketVoteNullifier,
  buildPolisTicketPayload,
  buildPolisVotePayload,
  hashContent,
  getPolisShortHandle,
} from "../src/polis.js";

import {
  DOMAIN,
  PROTO_VERSION,
  type VoteReceipt,
} from "../src/types.js";

// ─── Test constants ───────────────────────────────────────────────────────────

/**
 * Pre-derived nullifier root for fast testing.
 * In production this comes from deriveNullifierRoot(phone).
 */
const TEST_ROOT       = new Uint8Array(32).fill(0xab);
const TEST_BILL_ID    = "GR-2026-0042";
const TEST_TICKET_ID  = "TICKET-001";

// Server signing key for receipt tests
const SERVER_SK = ed25519.utils.randomPrivateKey();
const SERVER_PK = ed25519.getPublicKey(SERVER_SK);

// ─── nullifier.ts tests ───────────────────────────────────────────────────────

describe("deriveIdentityCommitment", () => {
  it("returns 64-char hex string", () => {
    const commitment = deriveIdentityCommitment(TEST_ROOT);
    expect(commitment).toHaveLength(64);
    expect(commitment).toMatch(/^[0-9a-f]+$/);
  });

  it("is deterministic", () => {
    expect(deriveIdentityCommitment(TEST_ROOT))
      .toBe(deriveIdentityCommitment(TEST_ROOT));
  });

  it("differs for different roots", () => {
    const root2 = new Uint8Array(32).fill(0xcd);
    expect(deriveIdentityCommitment(TEST_ROOT))
      .not.toBe(deriveIdentityCommitment(root2));
  });

  it("is domain-separated from vote nullifier", () => {
    const commitment = deriveIdentityCommitment(TEST_ROOT);
    const nullifier  = deriveVoteNullifier(TEST_ROOT, TEST_BILL_ID);
    expect(commitment).not.toBe(nullifier);
  });
});

describe("deriveVoteNullifier", () => {
  it("returns 64-char hex", () => {
    const n = deriveVoteNullifier(TEST_ROOT, TEST_BILL_ID);
    expect(n).toHaveLength(64);
    expect(n).toMatch(/^[0-9a-f]+$/);
  });

  it("is deterministic", () => {
    expect(deriveVoteNullifier(TEST_ROOT, TEST_BILL_ID))
      .toBe(deriveVoteNullifier(TEST_ROOT, TEST_BILL_ID));
  });

  it("differs per bill", () => {
    const n1 = deriveVoteNullifier(TEST_ROOT, "GR-2026-0001");
    const n2 = deriveVoteNullifier(TEST_ROOT, "GR-2026-0002");
    expect(n1).not.toBe(n2);
  });

  it("differs per root", () => {
    const root2 = new Uint8Array(32).fill(0xcd);
    const n1 = deriveVoteNullifier(TEST_ROOT, TEST_BILL_ID);
    const n2 = deriveVoteNullifier(root2,    TEST_BILL_ID);
    expect(n1).not.toBe(n2);
  });

  it("is domain-separated from linkage tag", () => {
    const nullifier = deriveVoteNullifier(TEST_ROOT, TEST_BILL_ID);
    const linkage   = deriveLinkageTag(TEST_ROOT,   TEST_BILL_ID);
    expect(nullifier).not.toBe(linkage);
  });
});

describe("deriveLinkageTag", () => {
  it("returns 64-char hex", () => {
    const tag = deriveLinkageTag(TEST_ROOT, TEST_BILL_ID);
    expect(tag).toHaveLength(64);
  });

  it("is deterministic", () => {
    expect(deriveLinkageTag(TEST_ROOT, TEST_BILL_ID))
      .toBe(deriveLinkageTag(TEST_ROOT, TEST_BILL_ID));
  });

  it("differs per bill", () => {
    const t1 = deriveLinkageTag(TEST_ROOT, "GR-2026-0001");
    const t2 = deriveLinkageTag(TEST_ROOT, "GR-2026-0002");
    expect(t1).not.toBe(t2);
  });
});

describe("deriveEphemeralKeypair", () => {
  it("returns valid Ed25519 keys", () => {
    const { sk, pk } = deriveEphemeralKeypair(TEST_ROOT, TEST_BILL_ID);
    expect(sk).toHaveLength(32);
    expect(pk).toHaveLength(32);
  });

  it("is deterministic per (root × bill)", () => {
    const k1 = deriveEphemeralKeypair(TEST_ROOT, TEST_BILL_ID);
    const k2 = deriveEphemeralKeypair(TEST_ROOT, TEST_BILL_ID);
    expect(bytesToHex(k1.pk)).toBe(bytesToHex(k2.pk));
  });

  it("differs per bill (ephemeral isolation)", () => {
    const k1 = deriveEphemeralKeypair(TEST_ROOT, "GR-2026-0001");
    const k2 = deriveEphemeralKeypair(TEST_ROOT, "GR-2026-0002");
    expect(bytesToHex(k1.pk)).not.toBe(bytesToHex(k2.pk));
  });

  it("differs per root", () => {
    const root2 = new Uint8Array(32).fill(0xcd);
    const k1 = deriveEphemeralKeypair(TEST_ROOT, TEST_BILL_ID);
    const k2 = deriveEphemeralKeypair(root2,     TEST_BILL_ID);
    expect(bytesToHex(k1.pk)).not.toBe(bytesToHex(k2.pk));
  });

  it("signs and verifies correctly", () => {
    const { sk, pk } = deriveEphemeralKeypair(TEST_ROOT, TEST_BILL_ID);
    const msg = utf8ToBytes("test message");
    const sig = ed25519.sign(msg, sk);
    expect(ed25519.verify(sig, msg, pk)).toBe(true);
  });
});

describe("buildVotePayload", () => {
  it("produces a valid signed payload", () => {
    const payload = buildVotePayload(TEST_ROOT, TEST_BILL_ID, "YES");

    expect(payload.bill_id).toBe(TEST_BILL_ID);
    expect(payload.choice).toBe("YES");
    expect(payload.version).toBe(PROTO_VERSION);
    expect(payload.pk_eph).toHaveLength(64);
    expect(payload.vote_nullifier).toHaveLength(64);
    expect(payload.linkage_tag).toHaveLength(64);
    expect(payload.signature).toHaveLength(128);
  });

  it("signature verifies against ephemeral pk", () => {
    const payload = buildVotePayload(TEST_ROOT, TEST_BILL_ID, "NO");

    const pkEph    = hexToBytes(payload.pk_eph);
    const sig      = hexToBytes(payload.signature);
    const msgBytes = buildSignedPayload(
      payload.bill_id,
      payload.choice,
      pkEph,
      hexToBytes(payload.vote_nullifier),
      hexToBytes(payload.linkage_tag),
      payload.timestamp_ms,
    );

    expect(ed25519.verify(sig, msgBytes, pkEph)).toBe(true);
  });

  it("different choices produce different signatures", () => {
    const p1 = buildVotePayload(TEST_ROOT, TEST_BILL_ID, "YES");
    const p2 = buildVotePayload(TEST_ROOT, TEST_BILL_ID, "NO");
    expect(p1.signature).not.toBe(p2.signature);
  });

  it("same (root × bill) always produces same nullifier", () => {
    const p1 = buildVotePayload(TEST_ROOT, TEST_BILL_ID, "YES");
    const p2 = buildVotePayload(TEST_ROOT, TEST_BILL_ID, "ABSTAIN");
    expect(p1.vote_nullifier).toBe(p2.vote_nullifier);
  });

  it("pk_eph differs across bills (ephemeral isolation)", () => {
    const p1 = buildVotePayload(TEST_ROOT, "GR-2026-0001", "YES");
    const p2 = buildVotePayload(TEST_ROOT, "GR-2026-0002", "YES");
    expect(p1.pk_eph).not.toBe(p2.pk_eph);
  });
});

describe("verifyReceipt", () => {
  function makeReceipt(billId: string, nullifier: string): VoteReceipt {
    const ts = Date.now();
    const tsBuf = new ArrayBuffer(8);
    new DataView(tsBuf).setBigUint64(0, BigInt(ts), false);

    const receiptBytes = new Uint8Array([
      ...utf8ToBytes(billId),
      ...hexToBytes(nullifier),
      ...new Uint8Array(tsBuf),
    ]);
    const sig = ed25519.sign(receiptBytes, SERVER_SK);

    return {
      bill_id:             billId,
      vote_nullifier:      nullifier,
      server_timestamp_ms: ts,
      server_signature:    bytesToHex(sig),
      server_pk:           bytesToHex(SERVER_PK),
    };
  }

  it("accepts valid receipt", () => {
    const nullifier = "aa".repeat(32);
    const receipt   = makeReceipt(TEST_BILL_ID, nullifier);
    expect(verifyReceipt(receipt, nullifier)).toBe(true);
  });

  it("rejects tampered nullifier", () => {
    const nullifier = "aa".repeat(32);
    const receipt   = makeReceipt(TEST_BILL_ID, nullifier);
    expect(verifyReceipt(receipt, "bb".repeat(32))).toBe(false);
  });

  it("rejects tampered signature", () => {
    const nullifier = "aa".repeat(32);
    const receipt   = { ...makeReceipt(TEST_BILL_ID, nullifier), server_signature: "ff".repeat(64) };
    expect(verifyReceipt(receipt, nullifier)).toBe(false);
  });
});

// ─── polis.ts tests ───────────────────────────────────────────────────────────

describe("derivePolisKeypair", () => {
  it("returns valid keys", () => {
    const { sk_polis, pk_polis, polis_key } = derivePolisKeypair(TEST_ROOT);
    expect(sk_polis).toHaveLength(32);
    expect(pk_polis).toHaveLength(32);
    expect(polis_key).toHaveLength(32);
  });

  it("is deterministic", () => {
    const k1 = derivePolisKeypair(TEST_ROOT);
    const k2 = derivePolisKeypair(TEST_ROOT);
    expect(bytesToHex(k1.pk_polis)).toBe(bytesToHex(k2.pk_polis));
  });

  it("is isolated from voting keys", () => {
    const { pk_polis }  = derivePolisKeypair(TEST_ROOT);
    const { pk: pk_eph } = deriveEphemeralKeypair(TEST_ROOT, TEST_BILL_ID);
    expect(bytesToHex(pk_polis)).not.toBe(bytesToHex(pk_eph));
  });

  it("polis key differs from identity commitment", () => {
    const { pk_polis } = derivePolisKeypair(TEST_ROOT);
    const commitment   = deriveIdentityCommitment(TEST_ROOT);
    expect(bytesToHex(pk_polis)).not.toBe(commitment);
  });
});

describe("deriveTicketNullifier", () => {
  it("returns 64-char hex", () => {
    const { polis_key } = derivePolisKeypair(TEST_ROOT);
    const n = deriveTicketNullifier(polis_key, hashContent("some content"));
    expect(n).toHaveLength(64);
  });

  it("same content → same nullifier", () => {
    const { polis_key } = derivePolisKeypair(TEST_ROOT);
    const ch = hashContent("same content");
    expect(deriveTicketNullifier(polis_key, ch))
      .toBe(deriveTicketNullifier(polis_key, ch));
  });

  it("different content → different nullifier", () => {
    const { polis_key } = derivePolisKeypair(TEST_ROOT);
    const n1 = deriveTicketNullifier(polis_key, hashContent("content A"));
    const n2 = deriveTicketNullifier(polis_key, hashContent("content B"));
    expect(n1).not.toBe(n2);
  });
});

describe("deriveTicketVoteNullifier", () => {
  it("differs from ticket nullifier (domain separation)", () => {
    const { polis_key } = derivePolisKeypair(TEST_ROOT);
    const tn = deriveTicketNullifier(polis_key, hashContent("content"));
    const vn = deriveTicketVoteNullifier(polis_key, TEST_TICKET_ID);
    expect(tn).not.toBe(vn);
  });

  it("differs per ticket", () => {
    const { polis_key } = derivePolisKeypair(TEST_ROOT);
    const n1 = deriveTicketVoteNullifier(polis_key, "TICKET-001");
    const n2 = deriveTicketVoteNullifier(polis_key, "TICKET-002");
    expect(n1).not.toBe(n2);
  });
});

describe("buildPolisTicketPayload", () => {
  it("produces a valid signed payload", () => {
    const payload = buildPolisTicketPayload(TEST_ROOT, "Please add dark mode", "proposal");
    expect(payload.version).toBe(PROTO_VERSION);
    expect(payload.pk_polis).toHaveLength(64);
    expect(payload.ticket_nullifier).toHaveLength(64);
    expect(payload.signature).toHaveLength(128);
  });

  it("signature verifies against pk_polis", () => {
    const content = "Fix the login bug";
    const payload = buildPolisTicketPayload(TEST_ROOT, content, "bug");

    const ch       = hashContent(content);
    const pkBytes  = hexToBytes(payload.pk_polis);
    const sigBytes = hexToBytes(payload.signature);

    const { polis_key } = derivePolisKeypair(TEST_ROOT);
    const { sk_polis }  = derivePolisKeypair(TEST_ROOT);

    // Re-build signed bytes to verify
    const catBytes  = utf8ToBytes(payload.category);
    const chBytes   = hexToBytes(ch);
    const tsBuf     = new ArrayBuffer(8);
    new DataView(tsBuf).setBigUint64(0, BigInt(payload.timestamp_ms), false);

    const signedBytes = new Uint8Array([
      0x01,
      catBytes.length,
      ...catBytes,
      ...chBytes,
      ...pkBytes,
      ...hexToBytes(payload.ticket_nullifier),
      ...new Uint8Array(tsBuf),
    ]);

    expect(ed25519.verify(sigBytes, signedBytes, pkBytes)).toBe(true);
  });

  it("throws for content > 2000 chars", () => {
    expect(() =>
      buildPolisTicketPayload(TEST_ROOT, "x".repeat(2001), "bug")
    ).toThrow();
  });

  it("same content produces same nullifier (idempotent)", () => {
    const p1 = buildPolisTicketPayload(TEST_ROOT, "same content", "bug");
    const p2 = buildPolisTicketPayload(TEST_ROOT, "same content", "bug");
    expect(p1.ticket_nullifier).toBe(p2.ticket_nullifier);
  });
});

describe("buildPolisVotePayload", () => {
  it("produces a valid signed payload", () => {
    const payload = buildPolisVotePayload(TEST_ROOT, TEST_TICKET_ID, "up");
    expect(payload.version).toBe(PROTO_VERSION);
    expect(payload.vote).toBe("up");
    expect(payload.pk_polis).toHaveLength(64);
    expect(payload.vote_nullifier).toHaveLength(64);
    expect(payload.signature).toHaveLength(128);
  });

  it("up and down produce different signatures", () => {
    const p1 = buildPolisVotePayload(TEST_ROOT, TEST_TICKET_ID, "up");
    const p2 = buildPolisVotePayload(TEST_ROOT, TEST_TICKET_ID, "down");
    expect(p1.signature).not.toBe(p2.signature);
  });

  it("same (root × ticket) → same vote nullifier", () => {
    const p1 = buildPolisVotePayload(TEST_ROOT, TEST_TICKET_ID, "up");
    const p2 = buildPolisVotePayload(TEST_ROOT, TEST_TICKET_ID, "down");
    expect(p1.vote_nullifier).toBe(p2.vote_nullifier);
  });
});

describe("getPolisShortHandle", () => {
  it("returns 8-char string", () => {
    const handle = getPolisShortHandle(TEST_ROOT);
    expect(handle).toHaveLength(8);
  });

  it("is deterministic", () => {
    expect(getPolisShortHandle(TEST_ROOT)).toBe(getPolisShortHandle(TEST_ROOT));
  });

  it("differs per root", () => {
    const root2 = new Uint8Array(32).fill(0xcd);
    expect(getPolisShortHandle(TEST_ROOT)).not.toBe(getPolisShortHandle(root2));
  });
});

describe("hashContent", () => {
  it("returns 64-char hex", () => {
    expect(hashContent("test")).toHaveLength(64);
  });

  it("is deterministic", () => {
    expect(hashContent("hello")).toBe(hashContent("hello"));
  });

  it("differs for different content", () => {
    expect(hashContent("a")).not.toBe(hashContent("b"));
  });
});
