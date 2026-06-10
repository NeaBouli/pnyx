import {
  runZkSemaphoreSelfTestWithModule,
  type ZkSemaphoreSelfTestResult,
} from "./zkSemaphoreSelfTestCore";
import * as semaphore from "semaphore-react-native";

export type { ZkSemaphoreSelfTestResult };

export function runZkSemaphoreSelfTest(): Promise<ZkSemaphoreSelfTestResult> {
  return runZkSemaphoreSelfTestWithModule(semaphore);
}
