/**
 * EKA-22 web adapter for the shared known-answer fixture
 * packages/crypto/tests/vectors/eka22_kat_v1.json (T-490).
 *
 * Hop: fixture -> this adapter -> apps/web/src/lib/crypto.ts -> expected bytes/hex/verdicts.
 * Test-only; the same fixture is read by the API, mobile and packages/crypto adapters.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import {
  buildVoteMessage,
  bytesToHex,
  computeNullifier,
  signPayload,
  signVote,
  verifyVote,
} from "./crypto";

type KatCase = {
  id: string;
  class: "identical" | "validatable" | "implementation_specific";
  kind: string;
  impls: string[];
  key?: string;
  input?: Record<string, unknown>;
  expect: Record<string, unknown>;
  impl_error?: Record<string, string>;
};

type Fixture = {
  schema: string;
  version: number;
  keys: { id: string; seed_hex: string; pk_hex: string }[];
  cases: KatCase[];
};

const FIXTURE: Fixture = JSON.parse(
  readFileSync(
    new URL("../../../../packages/crypto/tests/vectors/eka22_kat_v1.json", import.meta.url),
    "utf8",
  ),
);
const KEYS = new Map(FIXTURE.keys.map((k) => [k.id, k]));
const WEB = FIXTURE.cases.filter((c) => c.impls.includes("web"));
const byKind = (kind: string) => WEB.filter((c) => c.kind === kind);
const caseById = (id: string) => FIXTURE.cases.find((c) => c.id === id)!;
const key = (c: KatCase) => KEYS.get(c.key!)!;

type VoteInput = { bill_id: string; vote: string; nullifier_hash: string };

function utf8FromHex(hex: string): string {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
}

const HANDLED = [
  "ed25519_rfc8032",
  "legacy_vote",
  "v1_nullifier",
  "legacy_vote_verify",
  "lowercase_vote_divergence",
];

describe("EKA-22 KAT fixture (web)", () => {
  it("is schema v1 and every web case has a handler", () => {
    expect(FIXTURE.schema).toBe("ekklesia-kat");
    expect(FIXTURE.version).toBe(1);
    expect(WEB.length).toBeGreaterThan(0);
    for (const c of WEB) expect(HANDLED, c.id).toContain(c.kind);
  });
});

describe("identical", () => {
  it.each(byKind("ed25519_rfc8032"))("$id: RFC 8032 signature", (c) => {
    const message = utf8FromHex(c.expect.message_hex as string);
    expect(signPayload(key(c).seed_hex, message)).toBe(c.expect.sig_hex);
  });

  it.each(byKind("legacy_vote"))("$id: legacy vote message and signature", (c) => {
    const input = c.input as VoteInput;
    const message = buildVoteMessage(input);
    expect(message).toBe(c.expect.message_utf8);
    expect(bytesToHex(new TextEncoder().encode(message))).toBe(c.expect.message_hex);
    expect(signVote(key(c).seed_hex, input)).toBe(c.expect.sig_hex);
    expect(verifyVote(key(c).pk_hex, input, c.expect.sig_hex as string)).toBe(true);
  });

  it.each(byKind("v1_nullifier"))("$id: SHA-256 v1 nullifier with synthetic salt", async (c) => {
    const input = c.input as { phone: string; salt: string };
    expect(await computeNullifier(input.phone, input.salt)).toBe(c.expect.nullifier_hex);
  });
});

describe("validatable", () => {
  it.each(byKind("legacy_vote_verify"))("$id: rejected", (c) => {
    expect(c.impl_error?.web).toBe("false");
    const { pk_hex, sig_hex, ...params } = c.input as VoteInput & { pk_hex: string; sig_hex: string };
    expect(verifyVote(pk_hex, params, sig_hex)).toBe(false);
  });
});

describe("implementation_specific: known divergences", () => {
  it.each(byKind("lowercase_vote_divergence"))("$id: web uppercases like the API", (c) => {
    const canonical = caseById(c.expect.canonical_case as string);
    const input = c.input as VoteInput;
    expect(buildVoteMessage(input)).toBe(canonical.expect.message_utf8);
    const sig = signVote(key(c).seed_hex, input);
    expect(sig).toBe(canonical.expect.sig_hex);
    expect(sig).not.toBe(c.expect.mobile_sig_hex);
  });
});
