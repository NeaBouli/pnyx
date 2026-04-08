/**
 * crypto-native.ts — Ed25519 + Secure Enclave Storage
 * Χρησιμοποιεί expo-secure-store για ασφαλή αποθήκευση κλειδιών
 * Ed25519 υπογραφή μέσω @noble/curves (pure JS, audited)
 */
import * as SecureStore from "expo-secure-store";
import * as Crypto from "expo-crypto";
import { ed25519 } from "@noble/curves/ed25519.js";

const KEYS = {
  PRIVATE_KEY: "ekklesia_private_key",
  PUBLIC_KEY: "ekklesia_public_key",
  NULLIFIER: "ekklesia_nullifier",
} as const;

// ─── Key Storage ────────────────────────────────────────────────────────────

export async function storeKeypair(
  privateKeyHex: string,
  publicKeyHex: string
): Promise<void> {
  await SecureStore.setItemAsync(KEYS.PRIVATE_KEY, privateKeyHex, {
    requireAuthentication: true,
  });
  await SecureStore.setItemAsync(KEYS.PUBLIC_KEY, publicKeyHex);
}

export async function loadKeypair(): Promise<{
  privateKeyHex: string;
  publicKeyHex: string;
} | null> {
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

export async function clearKeys(): Promise<void> {
  await SecureStore.deleteItemAsync(KEYS.PRIVATE_KEY);
  await SecureStore.deleteItemAsync(KEYS.PUBLIC_KEY);
  await SecureStore.deleteItemAsync(KEYS.NULLIFIER);
}

export async function isVerified(): Promise<boolean> {
  const nullifier = await loadNullifier();
  return nullifier !== null;
}

// ─── Vote Message ───────────────────────────────────────────────────────────

export function buildVotePayload(
  billId: string,
  vote: string,
  nullifierHash: string
): string {
  return JSON.stringify(
    { bill_id: billId, nullifier_hash: nullifierHash, vote: vote.toUpperCase() },
    Object.keys({ bill_id: "", nullifier_hash: "", vote: "" }).sort()
  );
}

// ─── Hex Conversion ──────────────────────────────────────────────────────────

export function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return bytes;
}

export function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// ─── Ed25519 Signing ─────────────────────────────────────────────────────────

/**
 * Sign a vote payload with Ed25519 private key.
 * Returns signature as 128-char hex string (64 bytes).
 * Matches backend verify_signature() in packages/crypto/keypair.py
 */
export function signVote(
  privateKeyHex: string,
  params: { bill_id: string; vote: string; nullifier_hash: string }
): string {
  const message = buildVotePayload(params.bill_id, params.vote, params.nullifier_hash);
  const messageBytes = new TextEncoder().encode(message);
  const privateKey = hexToBytes(privateKeyHex);
  const signature = ed25519.sign(messageBytes, privateKey);
  return bytesToHex(signature);
}

/**
 * Verify an Ed25519 signature locally (for self-check before submitting).
 */
export function verifyVote(
  publicKeyHex: string,
  params: { bill_id: string; vote: string; nullifier_hash: string },
  signatureHex: string
): boolean {
  const message = buildVotePayload(params.bill_id, params.vote, params.nullifier_hash);
  const messageBytes = new TextEncoder().encode(message);
  const publicKey = hexToBytes(publicKeyHex);
  const signature = hexToBytes(signatureHex);
  try {
    return ed25519.verify(signature, messageBytes, publicKey);
  } catch {
    return false;
  }
}

// ─── Nullifier Hash (local computation) ─────────────────────────────────────

export async function computeNullifier(
  phone: string,
  salt: string
): Promise<string> {
  const digest = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    `${phone}:${salt}`
  );
  return digest;
}
