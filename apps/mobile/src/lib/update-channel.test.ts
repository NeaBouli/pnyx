import { describe, expect, it } from "vitest";
import {
  DIRECT_APK_URL,
  FDROID_URL,
  getDistributionChannelLabel,
  PLAY_STORE_URL,
  normalizeDistributionChannel,
  resolveUpdateUrl,
  shouldOfferUpdate,
  shouldRequireUpdate,
} from "./update-channel";

describe("update channel resolver", () => {
  const payload = {
    direct_apk_url:
      "https://github.com/NeaBouli/pnyx/releases/download/v1.0.32/ekklesia-v1.0.32-vC61-DIRECT.apk",
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

  const minimumPayload = {
    ...payload,
    latest_version_code: 65,
    min_required_version_code: 62,
    min_required_version_code_by_channel: { direct: 62, play: 62, fdroid: 621 },
  };

  it.each([611, 612, 613, 614])("prompts unsupported F-Droid code %i through F-Droid", (code) => {
    expect(shouldRequireUpdate(minimumPayload, code, "fdroid")).toBe(true);
    expect(shouldOfferUpdate(minimumPayload, code, "fdroid")).toBe(true);
    expect(resolveUpdateUrl(minimumPayload, "fdroid")).toBe(FDROID_URL);
  });

  it.each([621, 622, 623, 624, 651, 652, 653, 654])("accepts supported F-Droid code %i", (code) => {
    expect(shouldRequireUpdate(minimumPayload, code, "fdroid")).toBe(false);
    expect(shouldOfferUpdate(minimumPayload, code, "fdroid")).toBe(false);
  });

  it.each(["direct", "play", undefined])("separates required and optional updates for %s", (channel) => {
    expect(shouldRequireUpdate(minimumPayload, 61, channel)).toBe(true);
    expect(shouldOfferUpdate(minimumPayload, 61, channel)).toBe(true);
    expect(shouldRequireUpdate(minimumPayload, 62, channel)).toBe(false);
    expect(shouldOfferUpdate(minimumPayload, 62, channel)).toBe(true);
    expect(shouldOfferUpdate(minimumPayload, 65, channel)).toBe(false);
    // A required update still prompts if the optional release field is absent.
    expect(shouldOfferUpdate({ min_required_version_code: 62 }, 61, channel)).toBe(true);
  });

  it("never uses the legacy scalar as an F-Droid minimum", () => {
    const legacy = { latest_version_code: 65, min_required_version_code: 62 };
    expect(shouldRequireUpdate(legacy, 614, "fdroid")).toBe(false);
    expect(shouldOfferUpdate(legacy, 614, "fdroid")).toBe(false);
    expect(shouldRequireUpdate(legacy, 61, "direct")).toBe(true);
    expect(shouldRequireUpdate({
      ...minimumPayload,
      min_required_version_code: 999,
    }, 621, "fdroid")).toBe(false);
  });

  it.each([0, -1, 61.5, NaN, Infinity])("ignores invalid minimum or native code %s", (code) => {
    expect(shouldRequireUpdate({ min_required_version_code: code }, 61, "direct")).toBe(false);
    expect(shouldRequireUpdate(minimumPayload, code, "fdroid")).toBe(false);
  });

  it("falls back to canonical URLs without legacy /download route", () => {
    expect(resolveUpdateUrl({}, "play")).toBe(PLAY_STORE_URL);
    expect(resolveUpdateUrl({}, "fdroid")).toBe(FDROID_URL);
    expect(resolveUpdateUrl({}, "direct")).toBe(DIRECT_APK_URL);
    expect(resolveUpdateUrl({}, "direct")).not.toBe("https://ekklesia.gr/download");
    expect(resolveUpdateUrl({}, "direct")).not.toBe("https://ekklesia.gr/download/");
  });
});
