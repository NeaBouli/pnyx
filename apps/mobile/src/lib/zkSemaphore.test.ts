import { describe, expect, it } from "vitest";
import { detectZkCapability, isZkSemaphoreFeatureEnabled } from "./zkSemaphoreCore";

describe("isZkSemaphoreFeatureEnabled", () => {
  it("defaults to disabled", () => {
    expect(isZkSemaphoreFeatureEnabled({}, undefined)).toBe(false);
  });

  it("enables only explicit true values", () => {
    expect(isZkSemaphoreFeatureEnabled({ zkSemaphoreEnabled: true }, undefined)).toBe(true);
    expect(isZkSemaphoreFeatureEnabled({}, "true")).toBe(true);
    expect(isZkSemaphoreFeatureEnabled({ zkSemaphoreEnabled: false }, "false")).toBe(false);
  });
});

describe("detectZkCapability", () => {
  it("returns disabled while the feature flag is off", () => {
    const result = detectZkCapability({
      featureEnabled: false,
      platformOS: "android",
      appOwnership: "standalone",
      hasNativeProver: true,
    });

    expect(result.status).toBe("disabled");
    expect(result.canOptIn).toBe(false);
  });

  it("blocks opt-in when the native prover is missing", () => {
    const result = detectZkCapability({
      featureEnabled: true,
      platformOS: "android",
      appOwnership: "standalone",
      hasNativeProver: false,
    });

    expect(result.status).toBe("unsupported");
    expect(result.canOptIn).toBe(false);
    expect(result.reasons.join(" ")).toContain("Native Mopro/Semaphore prover");
  });

  it("allows opt-in only when feature flag and native prover are both present", () => {
    const result = detectZkCapability({
      featureEnabled: true,
      platformOS: "android",
      appOwnership: "standalone",
      hasNativeProver: true,
    });

    expect(result.status).toBe("ready");
    expect(result.canOptIn).toBe(true);
  });
});
