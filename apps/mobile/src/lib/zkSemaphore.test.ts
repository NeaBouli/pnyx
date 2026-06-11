import { describe, expect, it } from "vitest";
import {
  combineZkCapabilityWithServer,
  detectZkCapability,
  isZkSemaphoreFeatureEnabled,
} from "./zkSemaphoreCore";

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

  it("still reports unsupported devices while the feature flag is off", () => {
    const result = detectZkCapability({
      featureEnabled: false,
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

describe("combineZkCapabilityWithServer", () => {
  const readyLocal = {
    status: "ready" as const,
    canOptIn: true,
    reasons: [],
  };

  const enabledServer = {
    production_enabled: true,
    verifier_enabled: true,
    opt_in_enabled: true,
    canary_enabled: true,
    merkle_tree_depth: 16,
    verifier_version: "py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
    message_el: "enabled",
  };

  it("keeps opt-in blocked while server status is loading", () => {
    const result = combineZkCapabilityWithServer(readyLocal, null);

    expect(result.status).toBe("disabled");
    expect(result.canOptIn).toBe(false);
    expect(result.reasons.join(" ")).toContain("server status is still loading");
  });

  it("requires server opt-in gate before reporting ready", () => {
    const result = combineZkCapabilityWithServer(readyLocal, {
      ...enabledServer,
      opt_in_enabled: false,
      message_el: "server disabled",
    });

    expect(result.status).toBe("disabled");
    expect(result.canOptIn).toBe(false);
    expect(result.reasons).toContain("server disabled");
  });

  it("uses a fallback reason when the server gate message is empty", () => {
    const result = combineZkCapabilityWithServer(readyLocal, {
      ...enabledServer,
      opt_in_enabled: false,
      message_el: "",
    });

    expect(result.status).toBe("disabled");
    expect(result.reasons).toContain("ZK server opt-in gate is disabled.");
  });

  it("blocks opt-in when server status fetch failed", () => {
    const result = combineZkCapabilityWithServer(readyLocal, null, "Network error");

    expect(result.status).toBe("disabled");
    expect(result.canOptIn).toBe(false);
    expect(result.reasons.join(" ")).toContain("server status could not be loaded");
  });

  it("allows ready only when local and server gates are ready", () => {
    const result = combineZkCapabilityWithServer(readyLocal, enabledServer);

    expect(result.status).toBe("ready");
    expect(result.canOptIn).toBe(true);
  });

  it("does not hide unsupported device reasons behind server status", () => {
    const unsupported = {
      status: "unsupported" as const,
      canOptIn: false,
      reasons: ["Native Mopro/Semaphore prover is not bundled."],
    };
    const result = combineZkCapabilityWithServer(unsupported, enabledServer);

    expect(result).toBe(unsupported);
  });
});
