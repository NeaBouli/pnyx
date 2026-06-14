import { describe, expect, it } from "vitest";
import {
  canShowZkCanaryOperator,
  canRunZkCanaryOptIn,
  canRunZkCanaryVote,
  isZkCanaryWindowOpen,
  ZK_CANARY_BILL_ID,
  ZK_CANARY_SCOPE_ID,
  ZK_CANARY_VOTE_COMMITMENT,
} from "./zkCanaryOperator";
import type { ZkCapability, ZkServerStatus } from "./zkSemaphoreCore";

const readyCapability: ZkCapability = { status: "ready", canOptIn: true, reasons: [] };

const enabledStatus: ZkServerStatus = {
  production_enabled: true,
  verifier_enabled: true,
  opt_in_enabled: true,
  canary_enabled: true,
  merkle_tree_depth: 16,
  verifier_version: "canary",
  message_el: "canary",
};

describe("zkCanaryOperator", () => {
  it("pins the operator flow to the hidden canary scope", () => {
    expect(ZK_CANARY_BILL_ID).toBe("ZK-CANARY-001");
    expect(ZK_CANARY_SCOPE_ID).toBe("bill:ZK-CANARY-001");
    expect(ZK_CANARY_VOTE_COMMITMENT).toBe("YES");
  });

  it("keeps the operator hidden unless the server canary window is open", () => {
    expect(isZkCanaryWindowOpen(null)).toBe(false);
    expect(isZkCanaryWindowOpen({ ...enabledStatus, canary_enabled: false })).toBe(false);
    expect(isZkCanaryWindowOpen(enabledStatus)).toBe(true);
  });

  it("also requires an explicit local operator unlock before showing controls", () => {
    expect(canShowZkCanaryOperator({
      serverStatus: enabledStatus,
      operatorUnlocked: false,
    })).toBe(false);
    expect(canShowZkCanaryOperator({
      serverStatus: { ...enabledStatus, canary_enabled: false },
      operatorUnlocked: true,
    })).toBe(false);
    expect(canShowZkCanaryOperator({
      serverStatus: enabledStatus,
      operatorUnlocked: true,
    })).toBe(true);
  });

  it("requires local opt-in, device readiness, canary and opt-in gates for opt-in", () => {
    expect(canRunZkCanaryOptIn({
      serverStatus: enabledStatus,
      capability: readyCapability,
      optedIn: true,
    })).toBe(true);

    expect(canRunZkCanaryOptIn({
      serverStatus: { ...enabledStatus, canary_enabled: false },
      capability: readyCapability,
      optedIn: true,
    })).toBe(false);
    expect(canRunZkCanaryOptIn({
      serverStatus: { ...enabledStatus, opt_in_enabled: false },
      capability: readyCapability,
      optedIn: true,
    })).toBe(false);
    expect(canRunZkCanaryOptIn({
      serverStatus: enabledStatus,
      capability: readyCapability,
      optedIn: false,
    })).toBe(false);
    expect(canRunZkCanaryOptIn({
      serverStatus: enabledStatus,
      capability: { status: "disabled", canOptIn: false, reasons: [] },
      optedIn: true,
    })).toBe(false);
  });

  it("requires verifier and production gates before the canary vote can run", () => {
    expect(canRunZkCanaryVote({
      serverStatus: enabledStatus,
      capability: readyCapability,
      optedIn: true,
    })).toBe(true);
    expect(canRunZkCanaryVote({
      serverStatus: { ...enabledStatus, verifier_enabled: false },
      capability: readyCapability,
      optedIn: true,
    })).toBe(false);
    expect(canRunZkCanaryVote({
      serverStatus: { ...enabledStatus, production_enabled: false },
      capability: readyCapability,
      optedIn: true,
    })).toBe(false);
  });
});
