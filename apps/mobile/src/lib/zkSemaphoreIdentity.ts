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

export async function getOrCreateZkSemaphorePrivateKey(): Promise<Uint8Array> {
  const stored = await SecureStore.getItemAsync(ZK_SEMAPHORE_PRIVATE_KEY);
  if (stored) return hexToBytes(stored);

  const privateKey = Crypto.getRandomBytes(32);
  await SecureStore.setItemAsync(ZK_SEMAPHORE_PRIVATE_KEY, bytesToHex(privateKey));
  return privateKey;
}

export async function getOrCreateZkSemaphoreIdentity(): Promise<StoredZkSemaphoreIdentity> {
  const privateKey = await getOrCreateZkSemaphorePrivateKey();
  const identity = new Identity(privateKey);
  return {
    privateKey,
    commitment: identity.commitment(),
    memberHex: bytesToHex(identity.toElement()),
  };
}

export async function clearZkSemaphoreIdentity(): Promise<void> {
  await SecureStore.deleteItemAsync(ZK_SEMAPHORE_PRIVATE_KEY);
}
