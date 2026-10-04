/**
 * @file crypto-kat.test.ts
 * @description EKA-22 Tier-1 library adapter for the shared known-answer fixture
 * packages/crypto/tests/vectors/eka22_kat_v1.json (T-490).
 *
 * Hop: fixture -> this adapter -> packages/crypto/src/nullifier.ts -> expected bytes/hex.
 * Test-only; the same fixture is read by the API, web and mobile adapters.
 * K7 (length-prefixed payload) is pinned as an expected divergence, not fixed.
 */

import { describe, it, expect } from "vitest";
import { bytesToHex, hexToBytes } from "@noble/hashes/utils";

import {
  buildSignedPayload,
  deriveEphemeralKeypair,
  deriveIdentityCommitment,
  deriveLinkageTag,
  deriveNullifierRoot,
  deriveVoteNullifier,
} from "./nullifier.js";
import { ARGON2_PARAMS, DOMAIN, type VoteChoice } from "./types.js";

// ─── Fixture ──────────────────────────────────────────────────────────────────

type KatCase = {
  id: string;
  class: "identical" | "validatable" | "implementation_specific";
  kind: string;
  impls: string[];
  root?: string;
  input?: Record<string, unknown>;
  expect: Record<string, unknown>;
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
  roots: { id: string; root_hex: string }[];
  cases: KatCase[];
  kdf_inventory: { class: string; gate: string; compare: string; entries: KdfEntry[] };
};

// packages/crypto has no @types/node; load node:fs untyped instead of widening tsconfig.
const NODE_FS = "node:fs";
const fs: { readFileSync(path: URL, encoding: "utf8"): string } = await import(
  /* @vite-ignore */ NODE_FS
);
const FIXTURE: Fixture = JSON.parse(
  fs.readFileSync(new URL("../tests/vectors/eka22_kat_v1.json", import.meta.url), "utf8"),
);
const ROOTS  = new Map(FIXTURE.roots.map((r) => [r.id, r.root_hex]));
const TIER1  = FIXTURE.cases.filter((c) => c.impls.includes("tier1_lib"));
const byKind = (kind: string) => TIER1.filter((c) => c.kind === kind);
const root   = (c: KatCase) => hexToBytes(ROOTS.get(c.root!)!);

type ChainBill = {
  bill_id:            string;
  vote_nullifier_hex: string;
  ephemeral_pk_hex:   string;
  linkage_tag_hex:    string;
};

const HANDLED = ["hmac_chain", "domain_separation", "k7_payload_divergence"];

describe("EKA-22 KAT fixture (tier1_lib)", () => {
  it("is schema v1 and every tier1_lib case has a handler", () => {
    expect(FIXTURE.schema).toBe("ekklesia-kat");
    expect(FIXTURE.version).toBe(1);
    expect(TIER1.length).toBeGreaterThan(0);
    for (const c of TIER1) expect(HANDLED, c.id).toContain(c.kind);
  });
});

// ─── identical ────────────────────────────────────────────────────────────────

describe("identical", () => {
  it.each(byKind("hmac_chain"))("$id: HMAC chain from fixed test root", (c) => {
    const r = root(c);
    expect(deriveIdentityCommitment(r)).toBe(c.expect.identity_commitment_hex);
    for (const bill of c.expect.bills as ChainBill[]) {
      expect(deriveVoteNullifier(r, bill.bill_id)).toBe(bill.vote_nullifier_hex);
      expect(bytesToHex(deriveEphemeralKeypair(r, bill.bill_id).pk)).toBe(bill.ephemeral_pk_hex);
      expect(deriveLinkageTag(r, bill.bill_id)).toBe(bill.linkage_tag_hex);
    }
  });

  it.each(byKind("domain_separation"))("$id: domains match fixture and outputs are distinct", (c) => {
    const input = c.input as { domains: Record<string, string>; bills: string[] };
    for (const [name, value] of Object.entries(input.domains)) {
      expect(DOMAIN[name as keyof typeof DOMAIN], name).toBe(value);
    }
    const allDomains = Object.values(DOMAIN);
    expect(new Set(allDomains).size).toBe(allDomains.length);

    const r = root(c);
    const outputs = input.bills.flatMap((b) => [
      deriveVoteNullifier(r, b),
      deriveLinkageTag(r, b),
      bytesToHex(deriveEphemeralKeypair(r, b).pk),
    ]);
    outputs.push(deriveIdentityCommitment(r));
    expect(new Set(outputs).size).toBe(outputs.length);
  });
});

// ─── implementation_specific ──────────────────────────────────────────────────

describe("implementation_specific: known divergences", () => {
  it.each(byKind("k7_payload_divergence"))("$id: length-prefixed layout differs from API/mobile", (c) => {
    const i = c.input as {
      bill_id:            string;
      choice:             VoteChoice;
      pk_eph_hex:         string;
      vote_nullifier_hex: string;
      linkage_tag_hex:    string;
      timestamp_ms:       number;
    };
    const payload = bytesToHex(buildSignedPayload(
      i.bill_id,
      i.choice,
      hexToBytes(i.pk_eph_hex),
      hexToBytes(i.vote_nullifier_hex),
      hexToBytes(i.linkage_tag_hex),
      i.timestamp_ms,
    ));
    const reference = FIXTURE.cases.find((r) => r.id === c.expect.differs_from)!;
    expect(reference.impls).toEqual(["api", "mobile"]);
    expect(payload).toBe(c.expect.payload_hex);
    expect(payload).not.toBe(reference.expect.payload_hex);
  });

  it("KDF tier1-lib-v1 (Argon2id t=3) pinned within tier1_lib only", async () => {
    const entries = FIXTURE.kdf_inventory.entries.filter((e) => e.impl === "tier1_lib");
    expect(FIXTURE.kdf_inventory.compare).toBe("within_impl_only");
    expect(entries.map((e) => e.version)).toEqual(["tier1-lib-v1"]);
    const [entry] = entries;
    expect(entry.params).toMatchObject({
      alg: "Argon2id",
      t: ARGON2_PARAMS.iterations,
      m_kib: ARGON2_PARAMS.memorySize,
      p: ARGON2_PARAMS.parallelism,
      len: ARGON2_PARAMS.hashLength,
    });
    expect(bytesToHex(await deriveNullifierRoot(entry.input.phone))).toBe(entry.expect.root_hex);
  }, 30_000);
});
