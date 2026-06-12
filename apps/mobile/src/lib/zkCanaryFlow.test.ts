import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetchZkRootMembers: vi.fn(),
  submitZkOptIn: vi.fn(),
  submitZkVote: vi.fn(),
  signZkOptInPayload: vi.fn(),
  getOrCreateZkSemaphoreIdentity: vi.fn(),
  generateZkVoteProof: vi.fn(),
}));

vi.mock("./api", () => ({
  fetchZkRootMembers: mocks.fetchZkRootMembers,
  submitZkOptIn: mocks.submitZkOptIn,
  submitZkVote: mocks.submitZkVote,
}));

vi.mock("./crypto-native", () => ({
  signZkOptInPayload: mocks.signZkOptInPayload,
}));

vi.mock("./zkSemaphoreIdentity", () => ({
  getOrCreateZkSemaphoreIdentity: mocks.getOrCreateZkSemaphoreIdentity,
}));

vi.mock("./zkVoteProof", () => ({
  generateZkVoteProof: mocks.generateZkVoteProof,
}));

import { submitZkOptInForBill, submitZkVoteWithPublishedRoot } from "./zkCanaryFlow";

describe("zkCanaryFlow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits opt-in using a separate Semaphore identity and Tier-1 signature", async () => {
    mocks.getOrCreateZkSemaphoreIdentity.mockResolvedValue({
      commitment: "123456",
      memberHex: "010203",
      privateKey: new Uint8Array([1, 2, 3]),
    });
    mocks.signZkOptInPayload.mockResolvedValue({
      nullifierHash: "n".repeat(64),
      signatureHex: "a".repeat(128),
    });
    mocks.submitZkOptIn.mockResolvedValue({
      status: "pending_root",
      vote_scope_id: "bill:ZK-CANARY-001",
      commitment_id: 7,
      tier_locked: true,
      merkle_tree_depth: 16,
      message_el: "ok",
    });

    const result = await submitZkOptInForBill("ZK-CANARY-001");

    expect(mocks.signZkOptInPayload).toHaveBeenCalledWith("ZK-CANARY-001", "123456");
    expect(mocks.submitZkOptIn).toHaveBeenCalledWith({
      nullifierHash: "n".repeat(64),
      billId: "ZK-CANARY-001",
      commitment: "123456",
      signatureHex: "a".repeat(128),
    });
    expect(result.memberHex).toBe("010203");
    expect(result.response.commitment_id).toBe(7);
  });

  it("submits a ZK vote only after fetching a published root with members", async () => {
    mocks.fetchZkRootMembers.mockResolvedValue({
      vote_scope_id: "bill:ZK-CANARY-001",
      merkle_root: "root",
      merkle_depth: 16,
      group_size: 2,
      commitment_version: "semaphore-v4",
      status: "OPEN",
      root_id: 4,
      members: ["1", "2"],
    });
    mocks.generateZkVoteProof.mockResolvedValue({
      voteScopeId: "bill:ZK-CANARY-001",
      voteCommitment: "YES",
      message: "message",
      scope: "scope",
      groupSize: 2,
      proof: { merkleTreeRoot: "root", nullifier: "nullifier" },
    });
    mocks.submitZkVote.mockResolvedValue({
      accepted: true,
      vote_scope_id: "bill:ZK-CANARY-001",
      receipt_id: 8,
      arweave_pending: true,
      merkle_tree_depth: 16,
      verifier_version: "py-ecc-groth16-bn254:v1:semaphore-v4-depth16",
    });

    const result = await submitZkVoteWithPublishedRoot({
      voteScopeId: "bill:ZK-CANARY-001",
      voteCommitment: "YES",
    });

    expect(mocks.fetchZkRootMembers).toHaveBeenCalledWith("bill:ZK-CANARY-001");
    expect(mocks.generateZkVoteProof).toHaveBeenCalledWith({
      voteScopeId: "bill:ZK-CANARY-001",
      voteCommitment: "YES",
      members: ["1", "2"],
      merkleDepth: 16,
    });
    expect(mocks.submitZkVote).toHaveBeenCalledWith({
      voteScopeId: "bill:ZK-CANARY-001",
      voteCommitment: "YES",
      proof: { merkleTreeRoot: "root", nullifier: "nullifier" },
    });
    expect(result.accepted).toBe(true);
  });
});
