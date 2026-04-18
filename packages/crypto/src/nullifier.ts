/**
 * @file nullifier.ts
 * @description Client-side Tier 1 voting crypto for ekklesia.gr.
 *
 * Protocol summary (Tier 1 — HMAC-Nullifier-Chain):
 *   1. Registration: Argon2id(phone) → nullifier_root → identity_commitment → server
 *   2. Voting:       nullifier_root → ephemeral Ed25519 keypair (per bill)
 *                                   → vote_nullifier (per bill, unique, not linkable)
 *                                   → linkage_tag   (proves shared root, trust-based)
 *                    Sign payload with ephemeral key → send → discard key
 *
 * Trust model (Tier 1):
 *   Server cannot cryptographically verify key derivation without ZK.
 *   Guarantee: open-source client + Argon2id cost makes Sybil expensive.
 *   Full cryptographic guarantee: Tier 2 (Semaphore/Groth16).
 *
 * @module @ekklesia/crypto/nullifier
 */

import { hmac }           from "@noble/hashes/hmac";
import { sha256 }         from "@noble/hashes/sha256";
import { ed25519 }        from "@noble/curves/ed25519";
import { argon2id }       from "hash-wasm";
import {
  bytesToHex,
  hexToBytes,
  utf8ToBytes,
  concatBytes,
}                          from "@noble/hashes/utils";
import {
  ARGON2_PARAMS,
  DOMAIN,
  PROTO_VERSION,
  REGISTRATION_SALT,
  type PhoneRegion,
  type RegistrationPayload,
  type VoteChoice,
  type VotePayload,
  type VoteReceipt,
} from "./types.js";

// ─── Internal helpers ─────────────────────────────────────────────────────────

/**
 * HMAC-SHA256 over UTF-8 domain string + optional binary suffix.
 * Always returns 32 bytes.
 */
function hmacSha256(key: Uint8Array, domain: string, suffix?: Uint8Array): Uint8Array {
  const domainBytes = utf8ToBytes(domain);
  const message     = suffix ? concatBytes(domainBytes, suffix) : domainBytes;
  return hmac(sha256, key, message);
}

/**
 * Normalize Greek phone number to E.164.
 * Accepts: 6912345678 / 06912345678 / +306912345678 / 00306912345678
 */
function normalizePhone(raw: string): string {
  const digits = raw.replace(/\D/g, "");
  if (digits.startsWith("30") && digits.length === 12) return `+${digits}`;
  if (digits.startsWith("0030"))                        return `+30${digits.slice(4)}`;
  if (digits.length === 10 && digits.startsWith("6"))   return `+30${digits}`;
  throw new Error(`Cannot normalize phone number: ${raw}`);
}

/**
 * Zero out a Uint8Array in-place (best-effort in JS — GC may copy).
 * Do not rely on this for hard security guarantees.
 */
function zero(buf: Uint8Array): void {
  buf.fill(0);
}

// ─── Storage helpers (IndexedDB) ──────────────────────────────────────────────

const DB_NAME    = "ekklesia_crypto";
const DB_VERSION = 1;
const STORE_NAME = "identity";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE_NAME);
    req.onsuccess       = () => resolve(req.result);
    req.onerror         = () => reject(req.error);
  });
}

async function dbGet(key: string): Promise<Uint8Array | undefined> {
  const db  = await openDb();
  const tx  = db.transaction(STORE_NAME, "readonly");
  const req = tx.objectStore(STORE_NAME).get(key);
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result as Uint8Array | undefined);
    req.onerror   = () => reject(req.error);
  });
}

async function dbSet(key: string, value: Uint8Array): Promise<void> {
  const db  = await openDb();
  const tx  = db.transaction(STORE_NAME, "readwrite");
  tx.objectStore(STORE_NAME).put(value, key);
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror    = () => reject(tx.error);
  });
}

async function dbDelete(key: string): Promise<void> {
  const db  = await openDb();
  const tx  = db.transaction(STORE_NAME, "readwrite");
  tx.objectStore(STORE_NAME).delete(key);
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror    = () => reject(tx.error);
  });
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Derives the nullifier_root from a phone number using Argon2id.
 *
 * This is the root secret from which all voting keys are derived.
 * NEVER send this to the server or log it.
 *
 * @param phone - Raw phone number (any common format accepted)
 * @returns 32-byte nullifier_root
 */
export async function deriveNullifierRoot(phone: string): Promise<Uint8Array> {
  const normalized = normalizePhone(phone);
  const result     = await argon2id({
    password:    normalized,
    salt:        REGISTRATION_SALT,
    ...ARGON2_PARAMS,
  });
  // hash-wasm returns hex string when outputType is not set to "binary" in some versions
  if (typeof result === "string") return hexToBytes(result);
  return result as Uint8Array;
}

/**
 * Persists nullifier_root to IndexedDB under key "nullifier_root".
 *
 * Security note: IndexedDB is not hardware-backed.
 * XSS on the domain can read it. Mitigate with strict CSP.
 */
export async function persistNullifierRoot(nullifierRoot: Uint8Array): Promise<void> {
  await dbSet("nullifier_root", nullifierRoot);
}

/**
 * Loads nullifier_root from IndexedDB.
 * Returns undefined if not registered on this device.
 */
export async function loadNullifierRoot(): Promise<Uint8Array | undefined> {
  return dbGet("nullifier_root");
}

/**
 * Checks whether this device has a registered identity.
 */
export async function isRegistered(): Promise<boolean> {
  const root = await loadNullifierRoot();
  return root !== undefined;
}

/**
 * Derives the identity_commitment from nullifier_root.
 * This is the ONLY value sent to the server during registration.
 * It cannot be used to reconstruct nullifier_root.
 *
 * @param nullifierRoot - 32-byte root secret
 * @returns identity_commitment as hex string
 */
export function deriveIdentityCommitment(nullifierRoot: Uint8Array): string {
  const commitment = hmacSha256(nullifierRoot, DOMAIN.IDENTITY_COMMITMENT);
  return bytesToHex(commitment);
}

/**
 * Builds the registration payload to send to the server.
 *
 * @param phone       - Raw phone number
 * @param phoneRegion - ISO 3166-1 alpha-2 (e.g. "GR")
 * @param persist     - Whether to persist nullifier_root to IndexedDB (default: true)
 * @returns { payload, nullifierRoot } — caller must handle nullifierRoot carefully
 */
export async function buildRegistrationPayload(
  phone: string,
  phoneRegion: PhoneRegion,
  persist = true,
): Promise<{ payload: RegistrationPayload; nullifierRoot: Uint8Array }> {
  const nullifierRoot         = await deriveNullifierRoot(phone);
  const identity_commitment   = deriveIdentityCommitment(nullifierRoot);

  if (persist) await persistNullifierRoot(nullifierRoot);

  const payload: RegistrationPayload = {
    identity_commitment,
    phone_region: phoneRegion,
    version:      PROTO_VERSION,
  };

  return { payload, nullifierRoot };
}

// ─── Voting ───────────────────────────────────────────────────────────────────

/**
 * Derives the vote_nullifier for a specific bill.
 * Unique per (user × bill). Not linkable across bills without nullifier_root.
 *
 * @param nullifierRoot - 32-byte root secret
 * @param billId        - Bill identifier e.g. "GR-2026-0042"
 * @returns vote_nullifier as hex string
 */
export function deriveVoteNullifier(nullifierRoot: Uint8Array, billId: string): string {
  const nullifier = hmacSha256(
    nullifierRoot,
    DOMAIN.VOTE_NULLIFIER + ":" + billId,
  );
  return bytesToHex(nullifier);
}

/**
 * Derives the linkage_tag for a specific bill.
 *
 * Purpose: allows server to verify (in a trust-based way) that
 * the vote_nullifier and the identity_commitment share the same nullifier_root.
 * In Tier 2 this is replaced by a ZK-proof.
 *
 * @param nullifierRoot - 32-byte root secret
 * @param billId        - Bill identifier
 * @returns linkage_tag as hex string
 */
export function deriveLinkageTag(nullifierRoot: Uint8Array, billId: string): string {
  const linkageKey = hmacSha256(nullifierRoot, DOMAIN.LINKAGE_TAG);
  const tag        = hmacSha256(linkageKey, billId);
  return bytesToHex(tag);
}

/**
 * Derives a deterministic ephemeral Ed25519 keypair for a specific bill.
 * Deterministic: same (nullifier_root × bill_id) always yields the same keypair.
 * Ephemeral: private key must be zeroed after signing.
 *
 * @param nullifierRoot - 32-byte root secret
 * @param billId        - Bill identifier
 * @returns { sk, pk } — caller MUST call zero(sk) after use
 */
export function deriveEphemeralKeypair(
  nullifierRoot: Uint8Array,
  billId: string,
): { sk: Uint8Array; pk: Uint8Array } {
  const seed = hmacSha256(
    nullifierRoot,
    DOMAIN.EPHEMERAL_SEED + ":" + billId,
  );
  const sk = seed;                       // 32-byte private key seed
  const pk = ed25519.getPublicKey(sk);   // derive public key
  return { sk, pk };
}

/**
 * Builds the canonical byte payload that is signed by the ephemeral key.
 * All fields are length-prefixed to prevent collision attacks.
 *
 * Layout: version(1B) | bill_id_len(2B) | bill_id | choice(1B) |
 *         pk_eph(32B) | vote_nullifier(32B) | linkage_tag(32B) | timestamp(8B)
 */
export function buildSignedPayload(
  billId:        string,
  choice:        VoteChoice,
  pkEph:         Uint8Array,
  voteNullifier: Uint8Array,
  linkageTag:    Uint8Array,
  timestampMs:   number,
): Uint8Array {
  const versionByte  = new Uint8Array([1]);
  const billBytes    = utf8ToBytes(billId);
  const billLenBytes = new Uint8Array(2);
  new DataView(billLenBytes.buffer).setUint16(0, billBytes.length, false);

  const choiceMap: Record<VoteChoice, number> = { YES: 1, NO: 2, ABSTAIN: 3 };
  const choiceByte = new Uint8Array([choiceMap[choice]]);

  const tsBuf = new ArrayBuffer(8);
  new DataView(tsBuf).setBigUint64(0, BigInt(timestampMs), false);
  const tsBytes = new Uint8Array(tsBuf);

  return concatBytes(
    versionByte, billLenBytes, billBytes,
    choiceByte, pkEph, voteNullifier, linkageTag, tsBytes,
  );
}

/**
 * Builds and signs a vote payload.
 * Ephemeral private key is zeroed immediately after signing.
 *
 * @param nullifierRoot - 32-byte root secret (from loadNullifierRoot())
 * @param billId        - Bill identifier
 * @param choice        - Vote choice
 * @returns Signed VotePayload ready to POST to /api/votes
 */
export function buildVotePayload(
  nullifierRoot: Uint8Array,
  billId:        string,
  choice:        VoteChoice,
): VotePayload {
  const timestampMs   = Date.now();
  const { sk, pk }    = deriveEphemeralKeypair(nullifierRoot, billId);
  const voteNullifier = hexToBytes(deriveVoteNullifier(nullifierRoot, billId));
  const linkageTag    = hexToBytes(deriveLinkageTag(nullifierRoot, billId));

  const payloadBytes = buildSignedPayload(
    billId, choice, pk, voteNullifier, linkageTag, timestampMs,
  );
  const signature = ed25519.sign(payloadBytes, sk);

  // Zero the ephemeral private key immediately (best-effort)
  zero(sk);

  return {
    bill_id:        billId,
    choice,
    pk_eph:         bytesToHex(pk),
    vote_nullifier: bytesToHex(voteNullifier),
    linkage_tag:    bytesToHex(linkageTag),
    signature:      bytesToHex(signature),
    timestamp_ms:   timestampMs,
    version:        PROTO_VERSION,
  };
}

// ─── Receipt verification ─────────────────────────────────────────────────────

/**
 * Verifies a server-issued VoteReceipt.
 * Clients SHOULD call this after receiving a successful vote response.
 *
 * @param receipt      - VoteReceipt from server
 * @param voteNullifier - The vote_nullifier we sent (to verify it matches)
 * @returns true if receipt is genuine and matches our vote
 */
export function verifyReceipt(
  receipt:        VoteReceipt,
  voteNullifier:  string,
): boolean {
  if (receipt.vote_nullifier !== voteNullifier) return false;

  const receiptBytes = concatBytes(
    utf8ToBytes(receipt.bill_id),
    hexToBytes(receipt.vote_nullifier),
    (() => {
      const buf = new ArrayBuffer(8);
      new DataView(buf).setBigUint64(0, BigInt(receipt.server_timestamp_ms), false);
      return new Uint8Array(buf);
    })(),
  );

  try {
    return ed25519.verify(
      hexToBytes(receipt.server_signature),
      receiptBytes,
      hexToBytes(receipt.server_pk),
    );
  } catch {
    return false;
  }
}

// ─── Receipt storage ──────────────────────────────────────────────────────────

export async function storeReceipt(receipt: VoteReceipt): Promise<void> {
  const key   = `receipt:${receipt.bill_id}`;
  const bytes = utf8ToBytes(JSON.stringify(receipt));
  await dbSet(key, bytes);
}

export async function loadReceipt(billId: string): Promise<VoteReceipt | undefined> {
  const bytes = await dbGet(`receipt:${billId}`);
  if (!bytes) return undefined;
  return JSON.parse(new TextDecoder().decode(bytes)) as VoteReceipt;
}

// ─── Identity reset ───────────────────────────────────────────────────────────

/**
 * Wipes the local identity.
 * WARNING: Irreversible unless user re-registers with their phone.
 */
export async function clearIdentity(): Promise<void> {
  await dbDelete("nullifier_root");
}
