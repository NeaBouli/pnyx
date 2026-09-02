export type DistributionChannel = "play" | "direct" | string | null | undefined;

export interface UpdateUrlPayload {
  direct_apk_url?: string | null;
  playstore_url?: string | null;
  fdroid_url?: string | null;
}

export const DIRECT_APK_URL =
  "https://github.com/NeaBouli/pnyx/releases/download/v1.0.31/ekklesia-v1.0.31-vC60-DIRECT.apk";
export const PLAY_STORE_URL = "https://play.google.com/apps/testing/ekklesia.gr";
export const FDROID_URL = "https://f-droid.org/packages/ekklesia.gr/";

export function normalizeDistributionChannel(channel: DistributionChannel): "play" | "fdroid" | "direct" {
  if (channel === "play") return "play";
  if (channel === "fdroid") return "fdroid";
  return "direct";
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
