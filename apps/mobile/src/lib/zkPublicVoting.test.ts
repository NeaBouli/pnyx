import { describe, expect, it } from "vitest";

import { canShowPublicZkVoting, canSubmitPublicZkVote, publicZkVoteScopeForBill } from "./zkPublicVoting";
import type { ZkScopeStatus } from "./api";
import type { ZkServerStatus } from "./zkSemaphoreCore";

function status(overrides: Partial<ZkServerStatus> = {}): ZkServerStatus {
  return {
    production_enabled: true,
    verifier_enabled: true,
    opt_in_enabled: true,
    canary_enabled: false,
    root_publication_enabled: true,
    arweave_publication_enabled: false,
    global_rollout_enabled: false,
    production_scope_allowlist_configured: true,
    merkle_tree_depth: 16,
    verifier_version: "test",
    message_el: "ok",
    ...overrides,
  };
}

function scopeStatus(overrides: Partial<ZkScopeStatus> = {}): ZkScopeStatus {
  return {
    vote_scope_id: "bill:GR-5294",
    scope_type: "bill",
    production_enabled: true,
    verifier_enabled: true,
    opt_in_enabled: true,
    canary_enabled: false,
    allowlisted: true,
    global_rollout_enabled: false,
    root_published: false,
    active_commitments: 0,
    can_opt_in: true,
    can_vote: false,
    merkle_tree_depth: 16,
    verifier_version: "test",
    message_el: "ok",
    ...overrides,
  };
}

describe("public ZK voting visibility", () => {
  it("shows for an allowlisted production Parliament OPEN_END scope", () => {
    expect(canShowPublicZkVoting({
      serverStatus: status(),
      scopeStatus: scopeStatus(),
      billStatus: "OPEN_END",
      billSource: "PARLIAMENT",
      billLoaded: true,
    })).toBe(true);
  });

  it("blocks announced bills", () => {
    expect(canShowPublicZkVoting({
      serverStatus: status(),
      scopeStatus: scopeStatus(),
      billStatus: "ANNOUNCED",
      billSource: "PARLIAMENT",
      billLoaded: true,
    })).toBe(false);
  });

  it("blocks non-Parliament sources", () => {
    expect(canShowPublicZkVoting({
      serverStatus: status(),
      scopeStatus: scopeStatus(),
      billStatus: "OPEN_END",
      billSource: "DIAVGEIA",
      billLoaded: true,
    })).toBe(false);
  });

  it("blocks when production allowlist is not configured", () => {
    expect(canShowPublicZkVoting({
      serverStatus: status({ production_scope_allowlist_configured: false }),
      scopeStatus: scopeStatus(),
      billStatus: "OPEN_END",
      billSource: "PARLIAMENT",
      billLoaded: true,
    })).toBe(false);
  });

  it("blocks canary mode from public bill UI", () => {
    expect(canShowPublicZkVoting({
      serverStatus: status({ canary_enabled: true }),
      scopeStatus: scopeStatus(),
      billStatus: "OPEN_END",
      billSource: "PARLIAMENT",
      billLoaded: true,
    })).toBe(false);
  });

  it("blocks scopes that are not explicitly writable by the API", () => {
    expect(canShowPublicZkVoting({
      serverStatus: status(),
      scopeStatus: scopeStatus({ can_opt_in: false, allowlisted: false }),
      billStatus: "OPEN_END",
      billSource: "PARLIAMENT",
      billLoaded: true,
    })).toBe(false);
  });

  it("requires a published root before submitting a ZK vote", () => {
    expect(canSubmitPublicZkVote(scopeStatus({ can_vote: false, root_published: false }))).toBe(false);
    expect(canSubmitPublicZkVote(scopeStatus({ can_vote: true, root_published: true }))).toBe(true);
  });

  it("builds canonical bill scope ids", () => {
    expect(publicZkVoteScopeForBill("GR-5294")).toBe("bill:GR-5294");
  });
});
