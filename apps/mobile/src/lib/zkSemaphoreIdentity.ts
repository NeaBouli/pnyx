import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import { Identity } from "semaphore-react-native";

import { bytesToHex, hexToBytes } from "./crypto-native";

const ZK_SEMAPHORE_PRIVATE_KEY = "ekklesia_zk_semaphore_private_key_v1";

export interface StoredZkSemaphoreIdentity {
  privateKey: Uint8Array;
  commitment: string;
  memberHex: string;
}

function scopedSemaphoreKey(voteScopeId?: string): string {
  if (!voteScopeId) return ZK_SEMAPHORE_PRIVATE_KEY;
  const safeScope = voteScopeId.trim().replace(/[^A-Za-z0-9._-]/g, "_");
  return `${ZK_SEMAPHORE_PRIVATE_KEY}_${safeScope}`;
}

export async function getOrCreateZkSemaphorePrivateKey(voteScopeId?: string): Promise<Uint8Array> {
  const key = scopedSemaphoreKey(voteScopeId);
  const stored = await SecureStore.getItemAsync(key);
  if (stored) return hexToBytes(stored);

  const privateKey = Crypto.getRandomBytes(32);
  await SecureStore.setItemAsync(key, bytesToHex(privateKey));
  return privateKey;
}

export async function hasZkSemaphoreIdentity(voteScopeId?: string): Promise<boolean> {
  return (await SecureStore.getItemAsync(scopedSemaphoreKey(voteScopeId))) !== null;
}

export async function getOrCreateZkSemaphoreIdentity(voteScopeId?: string): Promise<StoredZkSemaphoreIdentity> {
  const privateKey = await getOrCreateZkSemaphorePrivateKey(voteScopeId);
  const identity = new Identity(privateKey);
  return {
    privateKey,
    commitment: identity.commitment(),
    memberHex: bytesToHex(identity.toElement()),
  };
}

export async function clearZkSemaphoreIdentity(voteScopeId?: string): Promise<void> {
  await SecureStore.deleteItemAsync(scopedSemaphoreKey(voteScopeId));
}
