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

export async function isDemoMode(): Promise<boolean> {
  const val = await SecureStore.getItemAsync(DEMO_KEY);
  return val === "true";
}

export async function clearDemo(): Promise<void> {
  await SecureStore.deleteItemAsync(DEMO_KEY);
}
