import { requireNativeModule } from "expo-modules-core";
import {
  getNativeSemaphoreStatus as getNativeSemaphoreStatusWithLoader,
  type SemaphoreNativeStatus,
} from "./zkSemaphoreNativeCore";

export function getNativeSemaphoreStatus(): SemaphoreNativeStatus {
  return getNativeSemaphoreStatusWithLoader(requireNativeModule);
}

export function hasNativeSemaphoreProver(): boolean {
  return getNativeSemaphoreStatus().ready;
}
