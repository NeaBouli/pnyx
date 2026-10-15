/**
 * Demo mode for Google Play reviewer.
 * Demo number: +306900000000
 * Only active in "play" distribution channel.
 */
import * as SecureStore from "expo-secure-store";
import Constants from "expo-constants";

const DEMO_NUMBER = "+306900000000";
const DEMO_KEY = "is_demo_mode";

const channel =
  (Constants.expoConfig?.extra?.distributionChannel as string) ?? "direct";

export function isDemoNumber(phone: string): boolean {
  return channel === "play" && phone.trim() === DEMO_NUMBER;
}

export async function activateDemo(): Promise<void> {
  await SecureStore.setItemAsync(DEMO_KEY, "true");
}

/** Prefix of the synthetic nullifier VerifyScreen stores for the demo identity. */
export const DEMO_NULLIFIER_PREFIX = "demo_";

/**
 * Demo mode is active only while the stored identity is the synthetic demo
 * identity. A stale flag next to a real (verified or imported) identity must
 * never turn a real vote into a simulated one (audit F4, 2026-10-13).
 */
export async function isDemoMode(): Promise<boolean> {
  const val = await SecureStore.getItemAsync(DEMO_KEY);
  if (val !== "true") return false;
  const nullifier = await SecureStore.getItemAsync("ekklesia_nullifier");
  return typeof nullifier === "string" && nullifier.startsWith(DEMO_NULLIFIER_PREFIX);
}

export async function clearDemo(): Promise<void> {
  await SecureStore.deleteItemAsync(DEMO_KEY);
}
