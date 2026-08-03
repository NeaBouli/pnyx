import * as SecureStore from "expo-secure-store";

import { updateIdentityLocation, type ProfileLocationResponse } from "./api";
import { signProfileLocation } from "./crypto-native";

const PERIFERIA_KEY = "user_periferia_id";
const DIMOS_KEY = "user_dimos_id";
const SCOPE_OWNER_KEY = "user_bill_scope_owner";
const PENDING_PERIFERIA_KEY = "pending_user_periferia_id";
const PENDING_DIMOS_KEY = "pending_user_dimos_id";

export interface ProfileLocationSelection {
  periferiaId: number | null;
  dimosId: number | null;
}

function positiveId(value: number | null | undefined): number | null {
  return Number.isInteger(value) && (value ?? 0) > 0 ? value! : null;
}

export async function loadPendingProfileLocation(): Promise<ProfileLocationSelection> {
  const [pendingPeriferia, pendingDimos] = await Promise.all([
    SecureStore.getItemAsync(PENDING_PERIFERIA_KEY),
    SecureStore.getItemAsync(PENDING_DIMOS_KEY),
  ]);
  return {
    periferiaId: positiveId(Number(pendingPeriferia)),
    dimosId: positiveId(Number(pendingDimos)),
  };
}

export async function clearPendingProfileLocation(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(PENDING_PERIFERIA_KEY),
    SecureStore.deleteItemAsync(PENDING_DIMOS_KEY),
  ]);
}

export async function loadStoredProfileLocation(
  ownerNullifierHash: string | null = null,
): Promise<ProfileLocationSelection> {
  if (!ownerNullifierHash) return loadPendingProfileLocation();

  const [periferia, dimos, storedOwner] = await Promise.all([
    SecureStore.getItemAsync(PERIFERIA_KEY),
    SecureStore.getItemAsync(DIMOS_KEY),
    SecureStore.getItemAsync(SCOPE_OWNER_KEY),
  ]);
  if (storedOwner !== ownerNullifierHash) {
    return { periferiaId: null, dimosId: null };
  }
  return {
    periferiaId: positiveId(Number(periferia)),
    dimosId: positiveId(Number(dimos)),
  };
}

export async function storeProfileLocation(
  selection: ProfileLocationSelection,
  ownerNullifierHash: string | null = null,
): Promise<void> {
  const periferiaId = positiveId(selection.periferiaId);
  const dimosId = positiveId(selection.dimosId);
  const periferiaKey = ownerNullifierHash ? PERIFERIA_KEY : PENDING_PERIFERIA_KEY;
  const dimosKey = ownerNullifierHash ? DIMOS_KEY : PENDING_DIMOS_KEY;
  await Promise.all([
    periferiaId === null
      ? SecureStore.deleteItemAsync(periferiaKey)
      : SecureStore.setItemAsync(periferiaKey, String(periferiaId)),
    dimosId === null
      ? SecureStore.deleteItemAsync(dimosKey)
      : SecureStore.setItemAsync(dimosKey, String(dimosId)),
    ownerNullifierHash
      ? SecureStore.setItemAsync(SCOPE_OWNER_KEY, ownerNullifierHash)
      : Promise.resolve(),
  ]);
  if (ownerNullifierHash) await clearPendingProfileLocation();
}

export async function syncProfileLocation(params: {
  nullifierHash: string;
  privateKeyHex: string;
  selection: ProfileLocationSelection;
}): Promise<ProfileLocationResponse> {
  const periferiaId = positiveId(params.selection.periferiaId);
  const dimosId = positiveId(params.selection.dimosId);
  const response = await updateIdentityLocation({
    nullifier_hash: params.nullifierHash,
    periferia_id: periferiaId,
    dimos_id: dimosId,
    signature_hex: signProfileLocation(
      params.privateKeyHex,
      periferiaId,
      dimosId,
      params.nullifierHash,
    ),
  });
  await storeProfileLocation({
    periferiaId: response.periferia_id,
    dimosId: response.dimos_id,
  }, params.nullifierHash);
  return response;
}
