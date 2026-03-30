/**
 * Browser-native Ed25519 cryptography for ekklesia.gr
 * Uses @noble/curves (already installed) — no server trust needed.
 *
 * This module mirrors packages/crypto/keypair.py (Python/PyNaCl)
 * but runs entirely in the browser.
 *
 * Storage: localStorage for Beta. Later: iOS Keychain / Android Keystore via Expo.
 */

import { ed25519 } from "@noble/curves/ed25519.js";

// ─── Key Generation ──────────────────────────────────────────────────────────

export function generateKeypair(): {
  privateKey: Uint8Array;
  publicKey: Uint8Array;
} {
  const privateKey = ed25519.utils.randomSecretKey();
  const publicKey = ed25519.getPublicKey(privateKey);
  return { privateKey, publicKey };
}

// ─── Hex Conversion ──────────────────────────────────────────────────────────

export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}

export function privateKeyToHex(key: Uint8Array): string {
  return bytesToHex(key);
}

export function hexToPrivateKey(hex: string): Uint8Array {
  return hexToBytes(hex);
}

export function publicKeyToHex(key: Uint8Array): string {
  return bytesToHex(key);
}

export function hexToPublicKey(hex: string): Uint8Array {
  return hexToBytes(hex);
}

// ─── Nullifier Hash ──────────────────────────────────────────────────────────

/**
 * Compute nullifier hash: SHA-256(phone + ":" + serverSalt)
 * Must match Python: hashlib.sha256(f"{phone}:{salt}".encode()).hexdigest()
 */
export async function computeNullifier(
  phoneNumber: string,
  serverSalt: string
): Promise<string> {
  const raw = `${phoneNumber}:${serverSalt}`;
  const encoded = new TextEncoder().encode(raw);
  const hashBuffer = await crypto.subtle.digest("SHA-256", encoded);
  return bytesToHex(new Uint8Array(hashBuffer));
}

// ─── Vote Signing ────────────────────────────────────────────────────────────

/**
 * Build the canonical vote message that the backend expects.
 * Keys MUST be sorted alphabetically — matches Python json.dumps(sort_keys=True).
 */
export function buildVoteMessage(params: {
  bill_id: string;
  vote: string;
  nullifier_hash: string;
}): string {
  // Alphabetical: bill_id, nullifier_hash, vote
  return JSON.stringify({
    bill_id: params.bill_id,
    nullifier_hash: params.nullifier_hash,
    vote: params.vote.toUpperCase(),
  });
}

/**
 * Sign a vote with Ed25519 private key.
 * Returns signature as hex string (128 chars = 64 bytes).
 */
export function signVote(
  privateKeyHex: string,
  params: { bill_id: string; vote: string; nullifier_hash: string }
): string {
  const message = buildVoteMessage(params);
  const messageBytes = new TextEncoder().encode(message);
  const privateKey = hexToPrivateKey(privateKeyHex);
  const signature = ed25519.sign(messageBytes, privateKey);
  return bytesToHex(signature);
}

/**
 * Verify a vote signature.
 */
export function verifyVote(
  publicKeyHex: string,
  params: { bill_id: string; vote: string; nullifier_hash: string },
  signatureHex: string
): boolean {
  const message = buildVoteMessage(params);
  const messageBytes = new TextEncoder().encode(message);
  const publicKey = hexToPublicKey(publicKeyHex);
  const signature = hexToBytes(signatureHex);
  try {
    return ed25519.verify(signature, messageBytes, publicKey);
  } catch {
    return false;
  }
}

// ─── Secure Storage (Beta: localStorage) ─────────────────────────────────────
// TODO: Replace with expo-secure-store (iOS Keychain / Android Keystore) in mobile app.

const STORAGE_KEY_PRIVATE = "ekklesia_private_key";
const STORAGE_KEY_PUBLIC = "ekklesia_public_key";
const STORAGE_KEY_NULLIFIER = "ekklesia_nullifier_hash";

export function storeKeypair(keypair: {
  privateKey: Uint8Array;
  publicKey: Uint8Array;
}): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY_PRIVATE, privateKeyToHex(keypair.privateKey));
  localStorage.setItem(STORAGE_KEY_PUBLIC, publicKeyToHex(keypair.publicKey));
}

export function loadKeypair(): {
  privateKeyHex: string;
  publicKeyHex: string;
} | null {
  if (typeof window === "undefined") return null;
  const priv = localStorage.getItem(STORAGE_KEY_PRIVATE);
  const pub = localStorage.getItem(STORAGE_KEY_PUBLIC);
  if (!priv || !pub) return null;
  return { privateKeyHex: priv, publicKeyHex: pub };
}

export function storeNullifier(hash: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY_NULLIFIER, hash);
}

export function loadNullifier(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEY_NULLIFIER);
}

export function clearKeypair(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY_PRIVATE);
  localStorage.removeItem(STORAGE_KEY_PUBLIC);
  localStorage.removeItem(STORAGE_KEY_NULLIFIER);
}

export function isVerified(): boolean {
  return !!loadKeypair() && !!loadNullifier();
}
