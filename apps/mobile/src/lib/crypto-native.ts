/**
 * crypto-native.ts — Tier 1 HMAC-Nullifier-Chain for React Native
 *
 * Mirrors packages/crypto/src/nullifier.ts protocol exactly.
 * Uses expo-secure-store (Android Keystore / iOS Keychain) for hardware-backed storage.
 * Uses react-native-argon2 for key derivation (no WASM needed).
 *
 * Key hierarchy:
 *   phone → Argon2id → nullifier_root (hardware-stored, never leaves device)
 *   nullifier_root → HMAC → identity_commitment (sent to server)
 *   nullifier_root × bill_id → HMAC → ephemeral_seed → Ed25519 keypair (per vote)
 *   nullifier_root × bill_id → HMAC → vote_nullifier (unique per bill, not linkable)
 *   nullifier_root × bill_id → HMAC → linkage_tag (trust-based proof)
 *
 * @module ekklesia/crypto-native
 */
import * as SecureStore from "expo-secure-store";
import { hmac } from "@noble/hashes/hmac";
import { sha256 } from "@noble/hashes/sha256";
import { pbkdf2 } from "@noble/hashes/pbkdf2";
import { ed25519 } from "@noble/curves/ed25519";
// NOTE: Argon2id preferred but react-native-argon2 requires native build config.
// Using PBKDF2-SHA256 (100k iterations) as portable fallback.
// TODO: Switch to Argon2id when native module is configured in EAS build.

// ─── Constants (mirror types.ts) ─────────────────────────────────────────────

const PROTO_VERSION = "ekklesia:v1";
const REGISTRATION_SALT = "ekklesia.gr:registration:2026:v1";

const ARGON2_PARAMS = {
  iterations: 3,
  memory: 65536,    // 64 MiB
  parallelism: 1,
  hashLength: 32,
};

const DOMAIN = {
  IDENTITY_COMMITMENT: "ekklesia:identity_commitment:v1",
  VOTE_NULLIFIER:      "ekklesia:vote_nullifier:v1",
  EPHEMERAL_SEED:      "ekklesia:ephemeral_seed:v1",
  LINKAGE_TAG:         "ekklesia:linkage_tag:v1",
  POLIS_KEY:           "ekklesia:polis_key:v1",
} as const;

const KEYS = {
  NULLIFIER_ROOT:        "ekklesia_nullifier_root",
  IDENTITY_COMMITMENT:   "ekklesia_identity_commitment",
  // Legacy (Phase B compat)
  PRIVATE_KEY: "ekklesia_private_key",
  PUBLIC_KEY:  "ekklesia_public_key",
  NULLIFIER:   "ekklesia_nullifier",
} as const;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function utf8ToBytes(s: string): Uint8Array {
  return new TextEncoder().encode(s);
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes).map(b => b.toString(16).padStart(2, "0")).join("");
}

function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}

function concatBytes(...arrays: Uint8Array[]): Uint8Array {
  const total = arrays.reduce((acc, a) => acc + a.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const arr of arrays) {
    result.set(arr, offset);
    offset += arr.length;
  }
  return result;
}

function hmacSha256(key: Uint8Array, domain: string, suffix?: Uint8Array): Uint8Array {
  const domainBytes = utf8ToBytes(domain);
  const message = suffix ? concatBytes(domainBytes, suffix) : domainBytes;
  return hmac(sha256, key, message);
}

function normalizePhone(raw: string): string {
  const digits = raw.replace(/\D/g, "");
  if (digits.startsWith("30") && digits.length === 12) return `+${digits}`;
  if (digits.startsWith("0030")) return `+30${digits.slice(4)}`;
  if (digits.length === 10 && digits.startsWith("6")) return `+30${digits}`;
  throw new Error(`Cannot normalize phone: ${raw}`);
}

// ─── Key Derivation ──────────────────────────────────────────────────────────

/**
 * Derive nullifier_root from phone number using Argon2id.
 * This is the master secret — stored in hardware keystore.
 */
export async function deriveNullifierRoot(phone: string): Promise<Uint8Array> {
  const normalized = normalizePhone(phone);
  // PBKDF2-SHA256 fallback (100k iterations ≈ 300-500ms on mobile)
  // TODO: Replace with Argon2id(t=3, m=65536) when native module configured
  return pbkdf2(sha256, utf8ToBytes(normalized), utf8ToBytes(REGISTRATION_SALT), {
    c: 100000,
    dkLen: 32,
  });
}

/**
 * Derive identity_commitment from nullifier_root.
 * This is the ONLY value sent to the server.
 */
export function deriveIdentityCommitment(nullifierRoot: Uint8Array): string {
  return bytesToHex(hmacSha256(nullifierRoot, DOMAIN.IDENTITY_COMMITMENT));
}

/**
 * Derive vote_nullifier for a specific bill. Unique per (user × bill).
 */
export function deriveVoteNullifier(nullifierRoot: Uint8Array, billId: string): string {
  return bytesToHex(hmacSha256(nullifierRoot, DOMAIN.VOTE_NULLIFIER + ":" + billId));
}

/**
 * Derive ephemeral Ed25519 keypair for a specific bill.
 * Deterministic — same root + bill = same keypair.
 */
export function deriveEphemeralKeypair(nullifierRoot: Uint8Array, billId: string): {
  privateKey: Uint8Array;
  publicKey: Uint8Array;
} {
  const seed = hmacSha256(nullifierRoot, DOMAIN.EPHEMERAL_SEED + ":" + billId);
  const privateKey = seed;  // Ed25519 uses 32-byte seed as private key
  const publicKey = ed25519.getPublicKey(privateKey);
  return { privateKey, publicKey };
}

/**
 * Derive linkage_tag for trust-based proof.
 */
export function deriveLinkageTag(nullifierRoot: Uint8Array, billId: string): string {
  const linkageKey = hmacSha256(nullifierRoot, DOMAIN.LINKAGE_TAG);
  return bytesToHex(hmacSha256(linkageKey, billId));
}

/**
 * Derive POLIS persistent key (for ticket system).
 */
export function derivePolisKey(nullifierRoot: Uint8Array): {
  privateKey: Uint8Array;
  publicKey: Uint8Array;
} {
  const seed = hmacSha256(nullifierRoot, DOMAIN.POLIS_KEY);
  return { privateKey: seed, publicKey: ed25519.getPublicKey(seed) };
}

// ─── Hardware-backed Storage ─────────────────────────────────────────────────

/**
 * Secure store helper: tries biometrics first, falls back to PIN/pattern/none.
 * - Devices WITH biometrics → biometric unlock (most secure)
 * - Devices WITH PIN/pattern only → standard encryption (still secure)
 * - Devices with NO lock → OS-encrypted (minimum security)
 */
async function secureSet(key: string, value: string): Promise<void> {
  try {
    await SecureStore.setItemAsync(key, value, { requireAuthentication: true });
  } catch {
    // No biometrics enrolled — fallback to standard encryption
    await SecureStore.setItemAsync(key, value, { requireAuthentication: false });
  }
}

/**
 * Store nullifier_root in Android Keystore / iOS Keychain.
 * Uses biometrics if available, falls back gracefully.
 */
export async function storeNullifierRoot(root: Uint8Array): Promise<void> {
  await secureSet(KEYS.NULLIFIER_ROOT, bytesToHex(root));
}

export async function loadNullifierRoot(): Promise<Uint8Array | null> {
  const hex = await SecureStore.getItemAsync(KEYS.NULLIFIER_ROOT);
  if (!hex) return null;
  return hexToBytes(hex);
}

export async function storeIdentityCommitment(commitment: string): Promise<void> {
  await SecureStore.setItemAsync(KEYS.IDENTITY_COMMITMENT, commitment);
}

export async function loadIdentityCommitment(): Promise<string | null> {
  return SecureStore.getItemAsync(KEYS.IDENTITY_COMMITMENT);
}

// ─── Legacy compat (Phase B — will be deprecated) ────────────────────────────

export async function storeKeypair(privateKeyHex: string, publicKeyHex: string): Promise<void> {
  await secureSet(KEYS.PRIVATE_KEY, privateKeyHex);
  await SecureStore.setItemAsync(KEYS.PUBLIC_KEY, publicKeyHex);
}

export async function loadKeypair(): Promise<{ privateKeyHex: string; publicKeyHex: string } | null> {
  const priv = await SecureStore.getItemAsync(KEYS.PRIVATE_KEY);
  const pub = await SecureStore.getItemAsync(KEYS.PUBLIC_KEY);
  if (!priv || !pub) return null;
  return { privateKeyHex: priv, publicKeyHex: pub };
}

export async function storeNullifier(nullifier: string): Promise<void> {
  await SecureStore.setItemAsync(KEYS.NULLIFIER, nullifier);
}

export async function loadNullifier(): Promise<string | null> {
  return SecureStore.getItemAsync(KEYS.NULLIFIER);
}

export async function isVerified(): Promise<boolean> {
  // Check both new (Tier 1) and legacy (Phase B)
  const root = await SecureStore.getItemAsync(KEYS.NULLIFIER_ROOT);
  const legacy = await SecureStore.getItemAsync(KEYS.NULLIFIER);
  return root !== null || legacy !== null;
}

export async function clearKeys(): Promise<void> {
  await SecureStore.deleteItemAsync(KEYS.NULLIFIER_ROOT);
  await SecureStore.deleteItemAsync(KEYS.IDENTITY_COMMITMENT);
  await SecureStore.deleteItemAsync(KEYS.PRIVATE_KEY);
  await SecureStore.deleteItemAsync(KEYS.PUBLIC_KEY);
  await SecureStore.deleteItemAsync(KEYS.NULLIFIER);
}

// ─── Vote Signing (Tier 1) ───────────────────────────────────────────────────

/**
 * Build canonical signed payload for a vote.
 * Must exactly match server-side build_signed_payload() in crypto/nullifier.py
 */
export function buildSignedPayload(
  billId: string,
  choice: string,
  pkEph: Uint8Array,
  voteNullifier: Uint8Array,
  linkageTag: Uint8Array,
  timestampMs: number,
): Uint8Array {
  const billBytes = utf8ToBytes(billId);
  const choiceBytes = utf8ToBytes(choice);
  const tsBytes = new Uint8Array(8);
  const view = new DataView(tsBytes.buffer);
  view.setBigUint64(0, BigInt(timestampMs));
  return concatBytes(billBytes, choiceBytes, pkEph, voteNullifier, linkageTag, tsBytes);
}

/**
 * Sign a vote using ephemeral key derived from nullifier_root.
 */
export function signVoteEphemeral(
  nullifierRoot: Uint8Array,
  billId: string,
  choice: "YES" | "NO" | "ABSTAIN",
): {
  signature: string;
  pk_eph: string;
  vote_nullifier: string;
  linkage_tag: string;
  timestamp_ms: number;
} {
  const { privateKey, publicKey } = deriveEphemeralKeypair(nullifierRoot, billId);
  const voteNullifier = hexToBytes(deriveVoteNullifier(nullifierRoot, billId));
  const linkageTag = hexToBytes(deriveLinkageTag(nullifierRoot, billId));
  const timestampMs = Date.now();

  const payload = buildSignedPayload(billId, choice, publicKey, voteNullifier, linkageTag, timestampMs);
  const signature = ed25519.sign(payload, privateKey);

  // Zero ephemeral private key
  privateKey.fill(0);

  return {
    signature: bytesToHex(signature),
    pk_eph: bytesToHex(publicKey),
    vote_nullifier: bytesToHex(voteNullifier),
    linkage_tag: bytesToHex(linkageTag),
    timestamp_ms: timestampMs,
  };
}

// ─── Full Registration Flow (Tier 1) ─────────────────────────────────────────

/**
 * Complete registration flow:
 * 1. Derive nullifier_root from phone (Argon2id)
 * 2. Derive identity_commitment
 * 3. Store nullifier_root in hardware keystore
 * 4. Return identity_commitment for server registration
 */
export async function registerTier1(phone: string): Promise<{
  identity_commitment: string;
  version: string;
}> {
  const nullifierRoot = await deriveNullifierRoot(phone);
  const commitment = deriveIdentityCommitment(nullifierRoot);

  await storeNullifierRoot(nullifierRoot);
  await storeIdentityCommitment(commitment);

  // Zero phone-derived material from JS memory (best-effort)
  nullifierRoot.fill(0);

  return {
    identity_commitment: commitment,
    version: PROTO_VERSION,
  };
}
