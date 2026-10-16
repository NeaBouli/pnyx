import * as SecureStore from "expo-secure-store";
import { ed25519 } from "@noble/curves/ed25519.js";

import { loadUserBillScope } from "./bill-scope-storage";
import { storeProfileLocation } from "./profile-location";
import { clearVoteMarks } from "./vote-marks";
import {
  holdIdentityStateWhile,
  installIdentityState,
  prepareForServerIssuedKey,
  withIdentityStateLock,
} from "./crypto-native";

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
  "is_demo_mode",
  // EVA-001 PR4: key lifecycle state belongs to the replaced identity.
  "ekklesia_key_origin",
  "ekklesia_polis_seed",
  "ekklesia_rotation_staging",
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
  // Journaled: an interrupted rollback is completed on the next start.
  await installIdentityState(Object.fromEntries(IMPORT_STATE_KEYS.map((key) => [key, snapshot.get(key) ?? null])));
}

/**
 * Import credentials while deriving geographic visibility only from the
 * server-authoritative identity status. Deep-link location fields are never
 * accepted as identity-bound scope data.
 */
export function importAccountCredentials(
  credentials: ImportedAccountCredentials,
): Promise<void> {
  // EVA-001 PR4: background key rotation never starts during an import; the
  // storage phases are journaled under the identity lock, the network-bound
  // scope refresh runs outside it.
  return holdIdentityStateWhile(() => importAccountCredentialsPhased(credentials));
}

async function importAccountCredentialsPhased(
  credentials: ImportedAccountCredentials,
): Promise<void> {
  requireHex32(credentials.privateKey, "private key");
  requireHex32(credentials.publicKey, "public key");
  requireHex32(credentials.nullifier, "nullifier");
  const derivedPublicKey = bytesToHex(ed25519.getPublicKey(hexToBytes(credentials.privateKey)));
  if (derivedPublicKey !== credentials.publicKey.toLowerCase()) {
    throw new Error("Imported Ed25519 key pair does not match");
  }

  let snapshot: Map<string, string | null> | null = null;
  try {
    await withIdentityStateLock(async () => {
      snapshot = await snapshotImportState();
      // Same identity: keep pk_polis registered across the key replacement.
      await prepareForServerIssuedKey(credentials.nullifier);
      await installIdentityState({
        ekklesia_private_key: credentials.privateKey,
        ekklesia_public_key: credentials.publicKey,
        ekklesia_nullifier: credentials.nullifier,
        ekklesia_nullifier_root: null,
        ekklesia_identity_commitment: null,
        polis_registered: null,
        // An imported identity is real; end any earlier demo session (audit F4).
        is_demo_mode: null,
      });
      // Clear any previous identity's cached scope before asking the API. If the
      // primary is unavailable, loadUserBillScope returns this empty, owner-bound
      // cache and the imported account remains NATIONAL-only.
      await storeProfileLocation(
        { periferiaId: null, dimosId: null },
        credentials.nullifier,
      );
    });

    await loadUserBillScope();

    await withIdentityStateLock(async () => {
      await SecureStore.setItemAsync("onboarding_completed", "true");
      await SecureStore.setItemAsync("user_profile_completed", "true");
      // Only clear after all rollback-capable writes succeed. A rejected import
      // restores the original identity and must retain its local evidence.
      if (snapshot!.get("ekklesia_nullifier") !== credentials.nullifier) {
        await clearVoteMarks();
      }
    });
  } catch (error) {
    if (snapshot) {
      const previous = snapshot as Map<string, string | null>;
      await withIdentityStateLock(async () => {
        // Roll back only our own install: if anything replaced the imported
        // credentials meanwhile (e.g. a verification), that state is newer.
        const [priv, pub, nullifier] = await Promise.all([
          SecureStore.getItemAsync("ekklesia_private_key"),
          SecureStore.getItemAsync("ekklesia_public_key"),
          SecureStore.getItemAsync("ekklesia_nullifier"),
        ]);
        if (priv === credentials.privateKey && pub === credentials.publicKey && nullifier === credentials.nullifier) {
          await restoreImportState(previous);
        }
      });
    }
    throw error;
  }
}
