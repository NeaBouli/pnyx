import * as Application from "expo-application";
import Constants from "expo-constants";

export function parseNativeVersionCode(
  nativeBuildVersion: string | null,
  fallbackVersionCode = 0,
): number {
  if (nativeBuildVersion) {
    const parsed = Number.parseInt(nativeBuildVersion, 10);
    if (Number.isSafeInteger(parsed) && parsed >= 0) return parsed;
  }
  return fallbackVersionCode;
}

export function getCurrentVersionCode(): number {
  return parseNativeVersionCode(
    Application.nativeBuildVersion,
    Constants.expoConfig?.android?.versionCode ?? 0,
  );
}

export function getCurrentVersionName(): string {
  return Application.nativeApplicationVersion ?? Constants.expoConfig?.version ?? "?";
}
