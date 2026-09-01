export type DistributionChannel = "play" | "direct" | string | null | undefined;

export interface UpdateUrlPayload {
  direct_apk_url?: string | null;
  playstore_url?: string | null;
}

export const DIRECT_APK_URL =
  "https://github.com/NeaBouli/pnyx/releases/download/v1.0.30/ekklesia-v1.0.30-vC59-DIRECT.apk";
export const PLAY_STORE_URL = "https://play.google.com/apps/testing/ekklesia.gr";

export function normalizeDistributionChannel(channel: DistributionChannel): "play" | "direct" {
  return channel === "play" ? "play" : "direct";
}

export function resolveUpdateUrl(payload: UpdateUrlPayload, channel: DistributionChannel): string {
  if (normalizeDistributionChannel(channel) === "play") {
    return payload.playstore_url || PLAY_STORE_URL;
  }

  return payload.direct_apk_url || DIRECT_APK_URL;
}
