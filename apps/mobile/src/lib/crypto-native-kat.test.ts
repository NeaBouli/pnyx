/**
 * EKA-22 mobile adapter for the shared known-answer fixture
 * packages/crypto/tests/vectors/eka22_kat_v1.json (T-490).
 *
 * Hop: fixture -> this adapter -> apps/mobile/src/lib/crypto-native.ts -> expected bytes/hex/verdicts.
 * Test-only; the same fixture is read by the API, web and packages/crypto adapters.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { ed25519 } from "@noble/curves/ed25519.js";
import { afterEach, describe, expect, it, vi } from "vitest";

const secureStore = vi.hoisted(() => new Map<string, string>());

vi.mock("expo-secure-store", () => ({
  getItemAsync: vi.fn((k: string) => Promise.resolve(secureStore.get(k) ?? null)),
  setItemAsync: vi.fn((k: string, v: string) => {
    secureStore.set(k, v);
    return Promise.resolve();
  }),
  deleteItemAsync: vi.fn((k: string) => {
    secureStore.delete(k);
    return Promise.resolve();
  }),
}));

import {
  buildEvaluationReadPayload,
  buildEvaluationV2Payload,
  buildSignedPayload,
  buildVoteStatusReadPayload,
  bytesToHex,
  deriveEphemeralKeypair,
  deriveIdentityCommitment,
  deriveLinkageTag,
  deriveNullifierRoot,
  derivePolisKey,
  deriveVoteNullifier,
  hexToBytes,
  signEvaluationRead,
  signEvaluationV2,
  signVote,
  signVoteEphemeral,
  signVoteStatusRead,
  signZkOptInPayload,
  storeKeypair,
  storeNullifier,
  verifyVote,
} from "./crypto-native";

type KatCase = {
  id: string;
  class: "identical" | "validatable" | "implementation_specific";
  kind: string;
  impls: string[];
  key?: string;
  root?: string;
  input?: Record<string, unknown>;
  expect: Record<string, unknown>;
  impl_error?: Record<string, string>;
};

type KdfEntry = {
  id: string;
  impl: string;
  version: string;
  params: Record<string, unknown>;
  input: { phone: string };
  expect: { normalized: string; root_hex: string };
};

type Fixture = {
  schema: string;
  version: number;
  keys: { id: string; seed_hex: string; pk_hex: string }[];
  roots: { id: string; root_hex: string }[];
  cases: KatCase[];
  kdf_inventory: { class: string; gate: string; compare: string; entries: KdfEntry[] };
};

const FIXTURE: Fixture = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../../../packages/crypto/tests/vectors/eka22_kat_v1.json", import.meta.url).href),
    "utf8",
  ),
);
const KEYS = new Map(FIXTURE.keys.map((k) => [k.id, k]));
const ROOTS = new Map(FIXTURE.roots.map((r) => [r.id, r.root_hex]));
const MOBILE = FIXTURE.cases.filter((c) => c.impls.includes("mobile"));
const byKind = (kind: string) => MOBILE.filter((c) => c.kind === kind);
const caseById = (id: string) => FIXTURE.cases.find((c) => c.id === id)!;
const key = (c: KatCase) => KEYS.get(c.key!)!;
const root = (c: KatCase) => hexToBytes(ROOTS.get(c.root!)!);
const utf8 = (s: string) => new TextEncoder().encode(s);

type VoteInput = { bill_id: string; vote: string; nullifier_hash: string };
type Scores = { question_id: number; score: number }[];
type ChainBill = {
  bill_id: string;
  vote_nullifier_hex: string;
  ephemeral_pk_hex: string;
  linkage_tag_hex: string;
};

const HANDLED = [
  "ed25519_rfc8032",
  "legacy_vote",
  "hmac_chain",
  "tier1_signed_payload",
  "evaluation_v2",
  "evaluation_read",
  "vote_status_read",
  "zk_opt_in",
  "domain_separation",
  "legacy_vote_verify",
  "evaluation_v2_error",
  "lowercase_vote_divergence",
  "mobile_polis_key",
];

afterEach(() => {
  vi.useRealTimers();
  secureStore.clear();
});

describe("EKA-22 KAT fixture (mobile)", () => {
  it("is schema v1 and every mobile case has a handler", () => {
    expect(FIXTURE.schema).toBe("ekklesia-kat");
    expect(FIXTURE.version).toBe(1);
    expect(MOBILE.length).toBeGreaterThan(0);
    for (const c of MOBILE) expect(HANDLED, c.id).toContain(c.kind);
  });
});

describe("identical", () => {
  it.each(byKind("ed25519_rfc8032"))("$id: RFC 8032 key and signature", (c) => {
    const seed = hexToBytes(key(c).seed_hex);
    const message = hexToBytes(c.expect.message_hex as string);
    expect(bytesToHex(ed25519.getPublicKey(seed))).toBe(c.expect.pk_hex);
    expect(bytesToHex(ed25519.sign(message, seed))).toBe(c.expect.sig_hex);
  });

  it.each(byKind("legacy_vote"))("$id: legacy vote signature", (c) => {
    const input = c.input as VoteInput;
    expect(signVote(key(c).seed_hex, input)).toBe(c.expect.sig_hex);
    expect(verifyVote(key(c).pk_hex, input, c.expect.sig_hex as string)).toBe(true);
    expect(
      ed25519.verify(hexToBytes(c.expect.sig_hex as string), hexToBytes(c.expect.message_hex as string),
        hexToBytes(key(c).pk_hex)),
    ).toBe(true);
  });

  it.each(byKind("hmac_chain"))("$id: HMAC chain from fixed test root", (c) => {
    const r = root(c);
    expect(deriveIdentityCommitment(r)).toBe(c.expect.identity_commitment_hex);
    for (const bill of c.expect.bills as ChainBill[]) {
      expect(deriveVoteNullifier(r, bill.bill_id)).toBe(bill.vote_nullifier_hex);
      expect(bytesToHex(deriveEphemeralKeypair(r, bill.bill_id).publicKey)).toBe(bill.ephemeral_pk_hex);
      expect(deriveLinkageTag(r, bill.bill_id)).toBe(bill.linkage_tag_hex);
    }
  });

  it.each(byKind("tier1_signed_payload"))("$id: Tier-1 canonical bytes and signature", (c) => {
    const i = c.input as {
      bill_id: string;
      choice: "YES" | "NO" | "ABSTAIN";
      pk_eph_hex: string;
      vote_nullifier_hex: string;
      linkage_tag_hex: string;
      timestamp_ms: number;
    };
    const payload = buildSignedPayload(
      i.bill_id,
      i.choice,
      hexToBytes(i.pk_eph_hex),
      hexToBytes(i.vote_nullifier_hex),
      hexToBytes(i.linkage_tag_hex),
      i.timestamp_ms,
    );
    expect(bytesToHex(payload)).toBe(c.expect.payload_hex);

    vi.useFakeTimers();
    vi.setSystemTime(i.timestamp_ms);
    const signed = signVoteEphemeral(root(c), i.bill_id, i.choice);
    expect(signed).toEqual({
      signature: c.expect.sig_hex,
      pk_eph: i.pk_eph_hex,
      vote_nullifier: i.vote_nullifier_hex,
      linkage_tag: i.linkage_tag_hex,
      timestamp_ms: i.timestamp_ms,
    });
  });

  it.each([...byKind("evaluation_v2"), ...byKind("evaluation_read"), ...byKind("vote_status_read")])(
    "$id: JSON integrity payload and signature",
    (c) => {
      const i = c.input as {
        ada_number: string | null;
        bill_id: string;
        nullifier_hash: string;
        timestamp_ms: number;
        scores: Scores;
      };
      const seed = key(c).seed_hex;
      let payload: string;
      let sig: string;
      if (c.kind === "evaluation_v2") {
        payload = buildEvaluationV2Payload(i.ada_number!, i.nullifier_hash, i.timestamp_ms, i.scores);
        sig = signEvaluationV2(seed, i.ada_number!, i.nullifier_hash, i.timestamp_ms, i.scores);
      } else if (c.kind === "evaluation_read") {
        payload = buildEvaluationReadPayload(i.ada_number, i.nullifier_hash, i.timestamp_ms);
        sig = signEvaluationRead(seed, i.ada_number, i.nullifier_hash, i.timestamp_ms);
      } else {
        payload = buildVoteStatusReadPayload(i.bill_id, i.nullifier_hash, i.timestamp_ms);
        sig = signVoteStatusRead(seed, i.bill_id, i.nullifier_hash, i.timestamp_ms);
      }
      expect(payload).toBe(c.expect.payload_utf8);
      expect(bytesToHex(utf8(payload))).toBe(c.expect.payload_hex);
      expect(sig).toBe(c.expect.sig_hex);
    },
  );

  it.each(byKind("zk_opt_in"))("$id: zk_opt_in scope string signature", async (c) => {
    const i = c.input as { bill_id: string; commitment: string; nullifier_hash: string };
    await storeKeypair(key(c).seed_hex, key(c).pk_hex);
    await storeNullifier(i.nullifier_hash);
    const result = await signZkOptInPayload(i.bill_id, i.commitment);
    expect(result).toEqual({ nullifierHash: i.nullifier_hash, signatureHex: c.expect.sig_hex });
    expect(
      ed25519.verify(hexToBytes(result.signatureHex), utf8(c.expect.message_utf8 as string),
        hexToBytes(key(c).pk_hex)),
    ).toBe(true);
  });

  it.each(byKind("domain_separation"))("$id: per-bill outputs are distinct", (c) => {
    const r = root(c);
    const bills = (c.input as { bills: string[] }).bills;
    const outputs = bills.flatMap((b) => [
      deriveVoteNullifier(r, b),
      deriveLinkageTag(r, b),
      bytesToHex(deriveEphemeralKeypair(r, b).publicKey),
    ]);
    outputs.push(deriveIdentityCommitment(r), bytesToHex(derivePolisKey(r).publicKey));
    expect(new Set(outputs).size).toBe(outputs.length);
  });
});

describe("validatable", () => {
  it.each(byKind("legacy_vote_verify"))("$id: rejected (false or throw)", (c) => {
    const { pk_hex, sig_hex, ...params } = c.input as VoteInput & { pk_hex: string; sig_hex: string };
    const allowed = c.impl_error!.mobile.split("|");
    let verdict: string;
    try {
      verdict = String(verifyVote(pk_hex, params, sig_hex));
    } catch {
      verdict = "throw";
    }
    expect(allowed).toContain(verdict);
  });

  it.each(byKind("evaluation_v2_error"))("$id: duplicate question_id throws", (c) => {
    expect(c.impl_error?.mobile).toBe("throw");
    const i = c.input as { ada_number: string; nullifier_hash: string; timestamp_ms: number; scores: Scores };
    expect(() =>
      buildEvaluationV2Payload(i.ada_number, i.nullifier_hash, i.timestamp_ms, i.scores),
    ).toThrow();
  });
});

describe("implementation_specific: known divergences and pins", () => {
  it.each(byKind("lowercase_vote_divergence"))("$id: mobile signs lowercase raw", (c) => {
    const canonical = caseById(c.expect.canonical_case as string);
    const input = c.input as VoteInput;
    const sig = signVote(key(c).seed_hex, input);
    expect(sig).toBe(c.expect.mobile_sig_hex);
    expect(sig).not.toBe(canonical.expect.sig_hex);
    expect(
      ed25519.verify(hexToBytes(sig), utf8(c.expect.mobile_message_utf8 as string), hexToBytes(key(c).pk_hex)),
    ).toBe(true);
    // The API verifies over the uppercase message; the mobile lowercase signature fails there.
    expect(verifyVote(key(c).pk_hex, canonical.input as VoteInput, sig)).toBe(false);
  });

  it.each(byKind("mobile_polis_key"))("$id: POLIS key pinned for mobile only", (c) => {
    expect(bytesToHex(derivePolisKey(root(c)).publicKey)).toBe(c.expect.polis_pk_hex);
  });

  it("KDF mobile-pbkdf2-v1 (PBKDF2-SHA256 c=100000) pinned within mobile only", async () => {
    const entries = FIXTURE.kdf_inventory.entries.filter((e) => e.impl === "mobile");
    expect(FIXTURE.kdf_inventory.compare).toBe("within_impl_only");
    expect(entries.map((e) => e.version)).toEqual(["mobile-pbkdf2-v1"]);
    const [entry] = entries;
    expect(entry.params).toMatchObject({ alg: "PBKDF2-HMAC-SHA256", c: 100000, len: 32 });
    expect(bytesToHex(await deriveNullifierRoot(entry.input.phone))).toBe(entry.expect.root_hex);
  });
});
