/**
 * notifications.ts — Push Token Registration (MOD-20)
 * Registers Expo Push Token with server after user verification.
 * Token is linked to nullifier_hash (anonymous — no PII).
 *
 * F-Droid: FCM disabled via BUILD_FLAVOR=fdroid environment variable.
 * Play Store: notifications fully enabled.
 */
import * as Device from "expo-device";
import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";
import Constants from "expo-constants";

const API_BASE = process.env.EXPO_PUBLIC_API_URL || "https://api.ekklesia.gr";
const TOKEN_KEY = "push_token";

// F-Droid build: no push notifications (FCM not allowed)
const IS_FDROID = Constants.expoConfig?.extra?.buildFlavor === "fdroid";

if (!IS_FDROID) {
  // Only import and configure notifications for Play Store builds
  try {
    const Notifications = require("expo-notifications");
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
      }),
    });
  } catch {}
}

export async function registerForPushNotifications(): Promise<string | null> {
  // F-Droid: skip entirely — no FCM
  if (IS_FDROID) {
    console.log("[notifications] F-Droid build — push disabled");
    return null;
  }

  if (!Device.isDevice) return null;

  const Notifications = require("expo-notifications");

  const { status: existing } = await Notifications.getPermissionsAsync();
  let finalStatus = existing;

  if (existing !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== "granted") return null;

  const tokenData = await Notifications.getExpoPushTokenAsync({
    projectId: "f6cfa7b1-ff85-4020-ac35-94d3774615fd",
  });
  const token = tokenData.data;

  // Store locally
  await SecureStore.setItemAsync(TOKEN_KEY, token);

  // Register with server (anonymous)
  const nullifier = await SecureStore.getItemAsync("ekklesia:nullifier:v1");
  try {
    await fetch(`${API_BASE}/api/v1/notify/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        device_id: `${Platform.OS}-${Device.modelName || "unknown"}`,
        platform: Platform.OS,
      }),
    });
  } catch {}

  return token;
}

export async function getPushToken(): Promise<string | null> {
  return SecureStore.getItemAsync(TOKEN_KEY);
}
