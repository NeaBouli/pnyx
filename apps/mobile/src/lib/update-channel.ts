export type DistributionChannel = "play" | "direct" | string | null | undefined;

export interface UpdateUrlPayload {
  direct_apk_url?: string | null;
  playstore_url?: string | null;
  fdroid_url?: string | null;
}

export interface UpdateVersionPayload extends UpdateUrlPayload {
  latest_version_code?: number | null;
  min_required_version_code?: number | null;
  min_required_version_code_by_channel?: Partial<Record<"direct" | "play" | "fdroid", number | null>> | null;
}

export const DIRECT_APK_URL =
  "https://github.com/NeaBouli/pnyx/releases/download/v1.0.37/ekklesia-v1.0.37-vC66-DIRECT.apk";
export const PLAY_STORE_URL = "https://play.google.com/apps/testing/ekklesia.gr";
export const FDROID_URL = "https://f-droid.org/packages/ekklesia.gr/";

export function normalizeDistributionChannel(channel: DistributionChannel): "play" | "fdroid" | "direct" {
  if (channel === "play") return "play";
  if (channel === "fdroid") return "fdroid";
  return "direct";
}

export function getDistributionChannelLabel(channel: DistributionChannel): "Google Play" | "F-Droid" | "Direct" {
  const normalizedChannel = normalizeDistributionChannel(channel);
  if (normalizedChannel === "play") return "Google Play";
  if (normalizedChannel === "fdroid") return "F-Droid";
  return "Direct";
}

export function shouldRequireUpdate(
  payload: UpdateVersionPayload,
  currentVersionCode: number,
  channel: DistributionChannel,
): boolean {
  const normalizedChannel = normalizeDistributionChannel(channel);
  // The server supplies ABI-scheme minimums for F-Droid. Never compare its
  // native code against the legacy Direct/Play scalar (614 > 62).
  const minimum = payload.min_required_version_code_by_channel?.[normalizedChannel]
    ?? (normalizedChannel === "fdroid" ? undefined : payload.min_required_version_code);
  return typeof minimum === "number"
    && Number.isSafeInteger(minimum)
    && minimum > 0
    && Number.isSafeInteger(currentVersionCode)
    && currentVersionCode > 0
    && currentVersionCode < minimum;
}

export function shouldOfferUpdate(
  payload: UpdateVersionPayload,
  currentVersionCode: number,
  channel: DistributionChannel,
): boolean {
  if (shouldRequireUpdate(payload, currentVersionCode, channel)) return true;
  // Supported F-Droid builds continue to delegate optional updates to F-Droid.
  if (normalizeDistributionChannel(channel) === "fdroid") return false;
  return typeof payload.latest_version_code === "number"
    && Number.isSafeInteger(payload.latest_version_code)
    && payload.latest_version_code > currentVersionCode;
}

export function resolveUpdateUrl(payload: UpdateUrlPayload, channel: DistributionChannel): string {
  const normalizedChannel = normalizeDistributionChannel(channel);
  if (normalizedChannel === "play") {
    return payload.playstore_url || PLAY_STORE_URL;
  }
  if (normalizedChannel === "fdroid") {
    return payload.fdroid_url || FDROID_URL;
  }

  return payload.direct_apk_url || DIRECT_APK_URL;
}
