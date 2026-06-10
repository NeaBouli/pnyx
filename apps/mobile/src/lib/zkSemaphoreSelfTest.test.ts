import { describe, expect, it } from "vitest";
import {
  formatZkSelfTestError,
  runZkSemaphoreSelfTestWithModule,
  type SemaphoreGroupLike,
  type SemaphoreIdentityLike,
  type SemaphoreModuleLike,
} from "./zkSemaphoreSelfTestCore";

class FakeIdentity implements SemaphoreIdentityLike {
  constructor(private readonly privateKeyBytes: Uint8Array) {}

  commitment(): string {
    return `commitment-${this.privateKeyBytes[0]}`;
  }

  privateKey(): Uint8Array {
    return this.privateKeyBytes;
  }

  toElement(): Uint8Array {
    return this.privateKeyBytes;
  }
}

class FakeGroup implements SemaphoreGroupLike {
  constructor(private readonly groupMembers: Uint8Array[]) {}

  depth(): number {
    return 16;
  }

  members(): Uint8Array[] {
    return this.groupMembers;
  }

  root(): Uint8Array {
    return Uint8Array.from([1, 2, 3]);
  }
}

function fakeModule(verifyResult: boolean): SemaphoreModuleLike {
  return {
    Identity: FakeIdentity,
    Group: FakeGroup,
    generateSemaphoreProof: async () => "proof-json",
    verifySemaphoreProof: async () => verifyResult,
  };
}

describe("runZkSemaphoreSelfTestWithModule", () => {
  it("returns ok when proof generation and verification succeed", async () => {
    let tick = 1000;
    const result = await runZkSemaphoreSelfTestWithModule(fakeModule(true), () => {
      tick += 125;
      return tick;
    });

    expect(result.ok).toBe(true);
    expect(result.verified).toBe(true);
    if (result.ok) {
      expect(result.durationMs).toBe(125);
      expect(result.commitmentPreview).toBe("commitment-101");
      expect(result.proofDepth).toBe(16);
      expect(result.groupSize).toBe(2);
      expect(result.proofBytes).toBe("proof-json".length);
    }
  });

  it("returns a failure when native verification rejects the proof", async () => {
    const result = await runZkSemaphoreSelfTestWithModule(fakeModule(false), () => 0);

    expect(result.ok).toBe(false);
    expect(result.verified).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain("verification returned false");
    }
  });

  it("keeps native errors user-reportable", async () => {
    const result = await runZkSemaphoreSelfTestWithModule({
      Identity: FakeIdentity,
      Group: FakeGroup,
      generateSemaphoreProof: async () => {
        throw new Error("ProofGenerationError: missing zkey");
      },
      verifySemaphoreProof: async () => true,
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain("missing zkey");
    }
  });
});

describe("formatZkSelfTestError", () => {
  it("formats unknown native throw values", () => {
    expect(formatZkSelfTestError({})).toBe("Unknown Semaphore self-test error");
    expect(formatZkSelfTestError("native failed")).toBe("native failed");
  });
});
