import type { ZkServerStatus } from "./zkSemaphoreCore";
import type { ZkScopeStatus } from "./api";

const ZK_PUBLIC_VOTABLE_STATUSES = new Set(["ACTIVE", "WINDOW_24H", "OPEN_END"]);

export function publicZkVoteScopeForBill(billId: string): string {
  return `bill:${billId}`;
}

export function canShowPublicZkVoting(params: {
  serverStatus: ZkServerStatus | null;
  scopeStatus: ZkScopeStatus | null;
  billStatus: string;
  billSource: string;
  billLoaded: boolean;
}): boolean {
  const { serverStatus, scopeStatus, billStatus, billSource, billLoaded } = params;
  if (!billLoaded || !serverStatus || !scopeStatus) return false;
  if (billSource !== "PARLIAMENT") return false;
  if (!ZK_PUBLIC_VOTABLE_STATUSES.has(billStatus)) return false;
  if (serverStatus.canary_enabled) return false;
  if (!scopeStatus.can_opt_in) return false;
  const productionScopeConfigured =
    serverStatus.production_scope_allowlist_configured === true ||
    serverStatus.global_rollout_enabled === true;
  return (
    serverStatus.production_enabled === true &&
    serverStatus.verifier_enabled === true &&
    serverStatus.opt_in_enabled === true &&
    productionScopeConfigured &&
    scopeStatus.vote_scope_id.startsWith("bill:")
  );
}

export function canSubmitPublicZkVote(scopeStatus: ZkScopeStatus | null): boolean {
  return scopeStatus?.can_vote === true;
}
