/**
 * crypto-native.ts — Ed25519 + Secure Enclave Storage
 * Χρησιμοποιεί expo-secure-store για ασφαλή αποθήκευση κλειδιών
 */
import * as SecureStore from "expo-secure-store";
import * as Crypto from "expo-crypto";

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

// ─── Nullifier Hash (local computation) ─────────────────────────────────────

export async function computeNullifier(
  phone: string,
  salt: string
): Promise<string> {
  const digest = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    phone + salt
  );
  return digest;
}
