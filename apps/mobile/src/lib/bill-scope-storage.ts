import * as SecureStore from "expo-secure-store";

import { checkIdentityStatus } from "./api";
import type { UserBillScope } from "./bill-scope";

const PERIFERIA_KEY = "user_periferia_id";
const DIMOS_KEY = "user_dimos_id";
const SCOPE_OWNER_KEY = "user_bill_scope_owner";

function positiveId(raw: string | null): number | null {
  const value = raw ? Number(raw) : 0;
  return Number.isInteger(value) && value > 0 ? value : null;
}

async function cacheScope(scope: UserBillScope, ownerNullifierHash: string): Promise<void> {
  if (scope.periferiaId !== null) await SecureStore.setItemAsync(PERIFERIA_KEY, String(scope.periferiaId));
  else await SecureStore.deleteItemAsync(PERIFERIA_KEY);
  if (scope.dimosId !== null) await SecureStore.setItemAsync(DIMOS_KEY, String(scope.dimosId));
  else await SecureStore.deleteItemAsync(DIMOS_KEY);
  await SecureStore.setItemAsync(SCOPE_OWNER_KEY, ownerNullifierHash);
}

async function clearScopeCache(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(PERIFERIA_KEY),
    SecureStore.deleteItemAsync(DIMOS_KEY),
    SecureStore.deleteItemAsync(SCOPE_OWNER_KEY),
  ]);
}

export async function loadUserBillScope(): Promise<UserBillScope> {
  const [storedPeriferia, storedDimos, scopeOwner, currentNullifier, legacyNullifier] = await Promise.all([
    SecureStore.getItemAsync(PERIFERIA_KEY),
    SecureStore.getItemAsync(DIMOS_KEY),
    SecureStore.getItemAsync(SCOPE_OWNER_KEY),
    SecureStore.getItemAsync("ekklesia:nullifier:v1"),
    SecureStore.getItemAsync("ekklesia_nullifier"),
  ]);
  const cached = {
    periferiaId: positiveId(storedPeriferia),
    dimosId: positiveId(storedDimos),
  };
  const nullifier = currentNullifier || legacyNullifier;
  if (!nullifier) {
    // A stored location is authoritative only while it is bound to the
    // currently active anonymous identity. Logged-out/new users fail closed.
    await clearScopeCache();
    return { periferiaId: null, dimosId: null };
  }

  try {
    const server = await checkIdentityStatus(nullifier);
    if (server.status !== "ACTIVE") {
      await clearScopeCache();
      return { periferiaId: null, dimosId: null };
    }
    const authoritative = {
      periferiaId: server.periferia_id ?? null,
      dimosId: server.dimos_id ?? null,
    };
    await cacheScope(authoritative, nullifier);
    return authoritative;
  } catch {
    // Read-only mirror/offline mode may use only this identity's last
    // server-confirmed scope. A cache from another identity fails closed.
    return scopeOwner === nullifier ? cached : { periferiaId: null, dimosId: null };
  }
}
