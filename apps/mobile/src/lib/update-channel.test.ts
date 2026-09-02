import { describe, expect, it } from "vitest";
import {
  DIRECT_APK_URL,
  FDROID_URL,
  getDistributionChannelLabel,
  PLAY_STORE_URL,
  normalizeDistributionChannel,
  resolveUpdateUrl,
  shouldOfferUpdate,
} from "./update-channel";

describe("update channel resolver", () => {
  const payload = {
    direct_apk_url:
      "https://github.com/NeaBouli/pnyx/releases/download/v1.0.31/ekklesia-v1.0.31-vC60-DIRECT.apk",
    playstore_url: "https://play.google.com/apps/testing/ekklesia.gr",
    fdroid_url: "https://f-droid.org/packages/ekklesia.gr/",
  };

  it("keeps Play builds on the Play Store update path", () => {
    expect(resolveUpdateUrl(payload, "play")).toBe(payload.playstore_url);
  });

  it("keeps Direct APK builds on the APK update path", () => {
    expect(resolveUpdateUrl(payload, "direct")).toBe(payload.direct_apk_url);
  });

  it("keeps F-Droid builds on the F-Droid update path", () => {
    expect(normalizeDistributionChannel("fdroid")).toBe("fdroid");
    expect(getDistributionChannelLabel("fdroid")).toBe("F-Droid");
    expect(resolveUpdateUrl(payload, "fdroid")).toBe(payload.fdroid_url);
  });

  it("uses stable labels for every supported channel", () => {
    expect(getDistributionChannelLabel("play")).toBe("Google Play");
    expect(getDistributionChannelLabel("direct")).toBe("Direct");
    expect(getDistributionChannelLabel(undefined)).toBe("Direct");
  });

  it("delegates F-Droid update availability to the F-Droid client", () => {
    expect(shouldOfferUpdate({ latest_version_code: 604 }, 581, "fdroid")).toBe(false);
    expect(shouldOfferUpdate({ latest_version_code: 60 }, 59, "direct")).toBe(true);
    expect(shouldOfferUpdate({ latest_version_code: 60 }, 59, "play")).toBe(true);
    expect(shouldOfferUpdate({ latest_version_code: 60 }, 60, "direct")).toBe(false);
    expect(shouldOfferUpdate({}, 59, "direct")).toBe(false);
    expect(shouldOfferUpdate({ latest_version_code: 60.5 }, 59, "play")).toBe(false);
  });

  it("defaults unknown channels to Direct APK updates", () => {
    expect(normalizeDistributionChannel(undefined)).toBe("direct");
    expect(normalizeDistributionChannel("internal")).toBe("direct");
    expect(resolveUpdateUrl(payload, undefined)).toBe(payload.direct_apk_url);
  });

  it("falls back to canonical URLs without legacy /download route", () => {
    expect(resolveUpdateUrl({}, "play")).toBe(PLAY_STORE_URL);
    expect(resolveUpdateUrl({}, "fdroid")).toBe(FDROID_URL);
    expect(resolveUpdateUrl({}, "direct")).toBe(DIRECT_APK_URL);
    expect(resolveUpdateUrl({}, "direct")).not.toBe("https://ekklesia.gr/download");
    expect(resolveUpdateUrl({}, "direct")).not.toBe("https://ekklesia.gr/download/");
  });
});
