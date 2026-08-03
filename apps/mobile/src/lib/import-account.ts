import * as SecureStore from "expo-secure-store";
import { ed25519 } from "@noble/curves/ed25519.js";

import { loadUserBillScope } from "./bill-scope-storage";
import { storeProfileLocation } from "./profile-location";

export interface ImportedAccountCredentials {
  privateKey: string;
  nullifier: string;
  publicKey: string;
}

const IMPORT_STATE_KEYS = [
  "ekklesia_private_key",
  "ekklesia_public_key",
  "ekklesia_nullifier",
  "ekklesia_nullifier_root",
  "ekklesia_identity_commitment",
  "polis_registered",
  "user_periferia_id",
  "user_dimos_id",
  "user_bill_scope_owner",
  "pending_user_periferia_id",
  "pending_user_dimos_id",
  "onboarding_completed",
  "user_profile_completed",
] as const;

function requireHex32(value: string, label: string): void {
  if (!/^[0-9a-fA-F]{64}$/.test(value)) {
    throw new Error(`Invalid ${label}`);
  }
}

function hexToBytes(value: string): Uint8Array {
  return Uint8Array.from(value.match(/.{2}/g)!.map((byte) => Number.parseInt(byte, 16)));
}

function bytesToHex(value: Uint8Array): string {
  return Array.from(value, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function snapshotImportState(): Promise<Map<string, string | null>> {
  const values = await Promise.all(
    IMPORT_STATE_KEYS.map((key) => SecureStore.getItemAsync(key)),
  );
  return new Map(IMPORT_STATE_KEYS.map((key, index) => [key, values[index]]));
}

async function restoreImportState(snapshot: Map<string, string | null>): Promise<void> {
  for (const key of IMPORT_STATE_KEYS) {
    const value = snapshot.get(key) ?? null;
    if (value === null) await SecureStore.deleteItemAsync(key);
    else await SecureStore.setItemAsync(key, value);
  }
}

/**
 * Import credentials while deriving geographic visibility only from the
 * server-authoritative identity status. Deep-link location fields are never
 * accepted as identity-bound scope data.
 */
export async function importAccountCredentials(
  credentials: ImportedAccountCredentials,
): Promise<void> {
  requireHex32(credentials.privateKey, "private key");
  requireHex32(credentials.publicKey, "public key");
  requireHex32(credentials.nullifier, "nullifier");
  const derivedPublicKey = bytesToHex(ed25519.getPublicKey(hexToBytes(credentials.privateKey)));
  if (derivedPublicKey !== credentials.publicKey.toLowerCase()) {
    throw new Error("Imported Ed25519 key pair does not match");
  }

  const snapshot = await snapshotImportState();
  try {
    await SecureStore.setItemAsync("ekklesia_private_key", credentials.privateKey);
    await SecureStore.setItemAsync("ekklesia_public_key", credentials.publicKey);
    await SecureStore.setItemAsync("ekklesia_nullifier", credentials.nullifier);
    await SecureStore.deleteItemAsync("ekklesia_nullifier_root");
    await SecureStore.deleteItemAsync("ekklesia_identity_commitment");
    await SecureStore.deleteItemAsync("polis_registered");

    // Clear any previous identity's cached scope before asking the API. If the
    // primary is unavailable, loadUserBillScope returns this empty, owner-bound
    // cache and the imported account remains NATIONAL-only.
    await storeProfileLocation(
      { periferiaId: null, dimosId: null },
      credentials.nullifier,
    );
    await loadUserBillScope();

    await SecureStore.setItemAsync("onboarding_completed", "true");
    await SecureStore.setItemAsync("user_profile_completed", "true");
  } catch (error) {
    await restoreImportState(snapshot);
    throw error;
  }
}
