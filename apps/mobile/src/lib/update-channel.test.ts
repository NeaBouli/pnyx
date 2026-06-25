import { describe, expect, it } from "vitest";
import {
  DIRECT_APK_URL,
  PLAY_STORE_URL,
  normalizeDistributionChannel,
  resolveUpdateUrl,
} from "./update-channel";

describe("update channel resolver", () => {
  const payload = {
    direct_apk_url: "https://ekklesia.gr/download/ekklesia-latest.apk",
    playstore_url: "https://play.google.com/store/apps/details?id=ekklesia.gr",
  };

  it("keeps Play builds on the Play Store update path", () => {
    expect(resolveUpdateUrl(payload, "play")).toBe(payload.playstore_url);
  });

  it("keeps Direct APK builds on the APK update path", () => {
    expect(resolveUpdateUrl(payload, "direct")).toBe(payload.direct_apk_url);
  });

  it("defaults unknown channels to Direct APK updates", () => {
    expect(normalizeDistributionChannel(undefined)).toBe("direct");
    expect(normalizeDistributionChannel("internal")).toBe("direct");
    expect(resolveUpdateUrl(payload, undefined)).toBe(payload.direct_apk_url);
  });

  it("falls back to canonical URLs without legacy /download route", () => {
    expect(resolveUpdateUrl({}, "play")).toBe(PLAY_STORE_URL);
    expect(resolveUpdateUrl({}, "direct")).toBe(DIRECT_APK_URL);
    expect(resolveUpdateUrl({}, "direct")).not.toBe("https://ekklesia.gr/download");
    expect(resolveUpdateUrl({}, "direct")).not.toBe("https://ekklesia.gr/download/");
  });
});
