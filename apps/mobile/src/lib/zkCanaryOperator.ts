import type { ZkCapability, ZkServerStatus } from "./zkSemaphoreCore";

export const ZK_CANARY_BILL_ID = "ZK-CANARY-001";
export const ZK_CANARY_SCOPE_ID = `bill:${ZK_CANARY_BILL_ID}`;
export const ZK_CANARY_VOTE_COMMITMENT = "YES";

export function isZkCanaryWindowOpen(serverStatus: ZkServerStatus | null): boolean {
  return serverStatus?.canary_enabled === true;
}

export function canShowZkCanaryOperator(params: {
  serverStatus: ZkServerStatus | null;
  operatorUnlocked: boolean;
}): boolean {
  return params.operatorUnlocked && isZkCanaryWindowOpen(params.serverStatus);
}

export function canRunZkCanaryOptIn(params: {
  serverStatus: ZkServerStatus | null;
  capability: ZkCapability;
  optedIn: boolean;
}): boolean {
  return Boolean(
    params.optedIn &&
      params.capability.status === "ready" &&
      params.capability.canOptIn &&
      params.serverStatus?.canary_enabled === true &&
      params.serverStatus.opt_in_enabled === true,
  );
}

export function canRunZkCanaryVote(params: {
  serverStatus: ZkServerStatus | null;
  capability: ZkCapability;
  optedIn: boolean;
}): boolean {
  return Boolean(
    canRunZkCanaryOptIn(params) &&
      params.serverStatus?.verifier_enabled === true &&
      params.serverStatus.production_enabled === true,
  );
}
