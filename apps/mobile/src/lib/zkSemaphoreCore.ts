export type ZkCapabilityStatus = "disabled" | "unsupported" | "ready";

export interface ZkCapability {
  status: ZkCapabilityStatus;
  canOptIn: boolean;
  reasons: string[];
}

export interface ZkCapabilityInput {
  featureEnabled: boolean;
  platformOS: string;
  appOwnership?: string | null;
  hasNativeProver: boolean;
}

export function isZkSemaphoreFeatureEnabled(
  extra?: Record<string, unknown> | null,
  envValue = process.env.EXPO_PUBLIC_ZK_SEMAPHORE_ENABLED,
): boolean {
  if (extra?.zkSemaphoreEnabled === true) return true;
  return envValue === "true";
}

export function detectZkCapability(input: ZkCapabilityInput): ZkCapability {
  const reasons: string[] = [];

  if (input.appOwnership === "expo") {
    reasons.push("Expo Go cannot load native proving modules.");
  }
  if (!["android", "ios"].includes(input.platformOS)) {
    reasons.push("ZK proving is only planned for Android/iOS devices.");
  }
  if (!input.hasNativeProver) {
    reasons.push("Native Mopro/Semaphore prover is not bundled.");
  }

  if (reasons.length > 0) {
    return { status: "unsupported", canOptIn: false, reasons };
  }

  if (!input.featureEnabled) {
    return {
      status: "disabled",
      canOptIn: false,
      reasons: ["ZK Semaphore V2 feature flag is off."],
    };
  }

  return { status: "ready", canOptIn: true, reasons: [] };
}
