import Constants from "expo-constants";
import { Platform } from "react-native";
import {
  detectZkCapability,
  isZkSemaphoreFeatureEnabled,
  type ZkCapability,
} from "./zkSemaphoreCore";

export { detectZkCapability, isZkSemaphoreFeatureEnabled, type ZkCapability };

export function getRuntimeZkCapability(): ZkCapability {
  const extra = Constants.expoConfig?.extra as Record<string, unknown> | undefined;
  return detectZkCapability({
    featureEnabled: isZkSemaphoreFeatureEnabled(extra),
    platformOS: Platform.OS,
    appOwnership: Constants.appOwnership,
    // GH#81: no release-grade native prover is available yet.
    hasNativeProver: false,
  });
}
