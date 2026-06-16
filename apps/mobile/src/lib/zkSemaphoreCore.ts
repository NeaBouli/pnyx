export type ZkCapabilityStatus = "disabled" | "unsupported" | "ready";

export interface ZkCapability {
  status: ZkCapabilityStatus;
  canOptIn: boolean;
  reasons: string[];
}

export interface ZkServerStatus {
  production_enabled: boolean;
  verifier_enabled: boolean;
  opt_in_enabled: boolean;
  canary_enabled: boolean;
  root_publication_enabled?: boolean;
  arweave_publication_enabled?: boolean;
  global_rollout_enabled?: boolean;
  production_scope_allowlist_configured?: boolean;
  merkle_tree_depth: number;
  verifier_version: string;
  message_el: string;
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

export function combineZkCapabilityWithServer(
  local: ZkCapability,
  serverStatus: ZkServerStatus | null,
  serverError?: string | null,
): ZkCapability {
  if (local.status === "unsupported") return local;

  if (serverError) {
    return {
      status: "disabled",
      canOptIn: false,
      reasons: [...local.reasons, "ZK server status could not be loaded."],
    };
  }

  if (!serverStatus) {
    return {
      status: "disabled",
      canOptIn: false,
      reasons: [...local.reasons, "ZK server status is still loading."],
    };
  }

  if (!serverStatus.opt_in_enabled) {
    const reason = serverStatus.message_el.trim() || "ZK server opt-in gate is disabled.";
    return {
      status: "disabled",
      canOptIn: false,
      reasons: [...local.reasons, reason],
    };
  }

  return local;
}
