import * as LocalAuthentication from "expo-local-authentication";
import * as SecureStore from "expo-secure-store";
import { sha256 } from "@noble/hashes/sha2.js";
import { bytesToHex, utf8ToBytes } from "@noble/hashes/utils.js";

type DeviceConfirmation = "allowed" | "no_lock" | "denied";

function preferenceKey(owner: string): string {
  const scope = bytesToHex(sha256(utf8ToBytes("ekklesia:vote-device-confirmation:v1:" + owner)));
  return `ekklesia_vote_confirmation.${scope}`;
}

async function readPreference(owner: string): Promise<boolean | null> {
  const stored = await SecureStore.getItemAsync(preferenceKey(owner));
  return stored === null ? null : stored !== "off";
}

export async function isVoteDeviceConfirmationEnabled(owner: string): Promise<boolean> {
  const preference = await readPreference(owner);
  if (preference !== null) return preference;
  const level = await LocalAuthentication.getEnrolledLevelAsync();
  return level !== LocalAuthentication.SecurityLevel.NONE;
}

export async function saveVoteDeviceConfirmation(owner: string, enabled: boolean): Promise<void> {
  await SecureStore.setItemAsync(preferenceKey(owner), enabled ? "on" : "off");
}

export async function confirmOnDevice(promptMessage: string): Promise<DeviceConfirmation> {
  try {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage,
      fallbackLabel: "Χρήση κωδικού",
      disableDeviceFallback: false,
    });
    if (result.success) return "allowed";
    // An enrollment error alone does not establish that the device has no PIN.
    if (
      (result.error === "not_enrolled" || result.error === "passcode_not_set") &&
      await LocalAuthentication.getEnrolledLevelAsync() === LocalAuthentication.SecurityLevel.NONE
    ) return "no_lock";
  } catch {
    // A failed native call must not bypass device confirmation.
  }
  return "denied";
}

export async function confirmRegularVote(owner: string | null): Promise<DeviceConfirmation> {
  const preference = owner ? await readPreference(owner).catch(() => true) : null;
  if (preference === false) return "allowed";
  const confirmation = await confirmOnDevice("Επιβεβαιώστε την ψήφο σας");
  return confirmation === "no_lock" && preference === null ? "allowed" : confirmation;
}
