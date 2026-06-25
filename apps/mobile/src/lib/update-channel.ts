export type DistributionChannel = "play" | "direct" | string | null | undefined;

export interface UpdateUrlPayload {
  direct_apk_url?: string | null;
  playstore_url?: string | null;
}

export const DIRECT_APK_URL = "https://ekklesia.gr/download/ekklesia-latest.apk";
export const PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=ekklesia.gr";

export function normalizeDistributionChannel(channel: DistributionChannel): "play" | "direct" {
  return channel === "play" ? "play" : "direct";
}

export function resolveUpdateUrl(payload: UpdateUrlPayload, channel: DistributionChannel): string {
  if (normalizeDistributionChannel(channel) === "play") {
    return payload.playstore_url || PLAY_STORE_URL;
  }

  return payload.direct_apk_url || DIRECT_APK_URL;
}
