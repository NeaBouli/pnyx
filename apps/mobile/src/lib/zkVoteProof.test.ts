import { describe, expect, it } from "vitest";

import {
  fieldDecimalToSemaphoreMemberBytes,
  generateZkVoteProofWithModule,
  type SemaphoreVoteGroupLike,
  type SemaphoreVoteIdentityLike,
  type SemaphoreVoteModuleLike,
} from "./zkVoteProofCore";

class FakeIdentity implements SemaphoreVoteIdentityLike {
  constructor(private readonly privateKey: Uint8Array) {}

  toElement(): Uint8Array {
    return this.privateKey;
  }
}

class FakeGroup implements SemaphoreVoteGroupLike {
  constructor(private readonly groupMembers: Uint8Array[]) {}

  members(): Uint8Array[] {
    return this.groupMembers;
  }
}

function fakeModule(capture: string[]): SemaphoreVoteModuleLike {
  return {
    Identity: FakeIdentity,
    Group: FakeGroup,
    generateSemaphoreProof: async (_identity, group, message, scope, depth) => {
      capture.push(`${message}:${scope}:${depth}:${group.members().length}`);
      return JSON.stringify({
        merkleTreeRoot: "root",
        message,
        scope,
        merkleTreeDepth: depth,
        nullifier: "nullifier",
      });
    },
  };
}

describe("fieldDecimalToSemaphoreMemberBytes", () => {
  it("converts Semaphore decimal field members to little-endian bytes", () => {
    const member = fieldDecimalToSemaphoreMemberBytes(
      "5260637929807650649558727749444203893895782316560874701982787513199649822018",
    );

    expect(Array.from(member, (byte) => byte.toString(16).padStart(2, "0")).join("")).toBe(
      "4215c708b28a7f4f150b0f884743ecd43b6c7e051447bad0d6f166a8616aa10b",
    );
  });

  it("rejects invalid field members", () => {
    expect(() => fieldDecimalToSemaphoreMemberBytes("abc")).toThrow("decimal field value");
    expect(() => fieldDecimalToSemaphoreMemberBytes(
      "21888242871839275222246405745257275088548364400416034343698204186575808495617",
    )).toThrow("outside the BN254 field");
  });
});

describe("generateZkVoteProofWithModule", () => {
  it("builds a proof bound to canonical vote message and scope", async () => {
    const capture: string[] = [];
    const privateKey = fieldDecimalToSemaphoreMemberBytes("1");
    const result = await generateZkVoteProofWithModule(fakeModule(capture), {
      privateKey,
      voteScopeId: "bill:ZK-CANARY-001",
      voteCommitment: "YES",
      members: ["1", "2"],
      merkleDepth: 16,
    });

    expect(result.voteScopeId).toBe("bill:ZK-CANARY-001");
    expect(result.voteCommitment).toBe("YES");
    expect(result.groupSize).toBe(2);
    expect(result.proof).toMatchObject({
      message: result.message,
      scope: result.scope,
      merkleTreeDepth: 16,
    });
    expect(capture[0]).toBe(`${result.message}:${result.scope}:16:2`);
  });

  it("fails before proof generation when the local identity is not in the published group", async () => {
    const capture: string[] = [];

    await expect(generateZkVoteProofWithModule(fakeModule(capture), {
      privateKey: fieldDecimalToSemaphoreMemberBytes("3"),
      voteScopeId: "bill:ZK-CANARY-001",
      voteCommitment: "YES",
      members: ["1", "2"],
      merkleDepth: 16,
    })).rejects.toThrow("Semaphore identity is not in the published group");
    expect(capture).toEqual([]);
  });
});
