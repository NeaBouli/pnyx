import Constants from "expo-constants";
import { Platform } from "react-native";
import {
  detectZkCapability,
  isZkSemaphoreFeatureEnabled,
  type ZkCapability,
} from "./zkSemaphoreCore";
import { getNativeSemaphoreStatus } from "./zkSemaphoreNative";

export { detectZkCapability, isZkSemaphoreFeatureEnabled, type ZkCapability };

export function getRuntimeZkCapability(): ZkCapability {
  const extra = Constants.expoConfig?.extra as Record<string, unknown> | undefined;
  const nativeStatus = getNativeSemaphoreStatus();

  return detectZkCapability({
    featureEnabled: isZkSemaphoreFeatureEnabled(extra),
    platformOS: Platform.OS,
    appOwnership: Constants.appOwnership,
    hasNativeProver: nativeStatus.ready,
  });
}
