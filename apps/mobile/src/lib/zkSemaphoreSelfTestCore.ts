export interface SemaphoreIdentityLike {
  commitment(): string;
  privateKey(): Uint8Array;
  toElement(): Uint8Array;
}

export interface SemaphoreGroupLike {
  depth(): number;
  members(): Uint8Array[];
  root(): Uint8Array;
}

export interface SemaphoreModuleLike {
  Identity: new (privateKey: Uint8Array) => SemaphoreIdentityLike;
  Group: new (members: Uint8Array[]) => SemaphoreGroupLike;
  generateSemaphoreProof(
    identity: SemaphoreIdentityLike,
    group: SemaphoreGroupLike,
    message: string,
    scope: string,
    treeDepth: number,
  ): Promise<string>;
  verifySemaphoreProof(proof: string): Promise<boolean>;
}

export interface ZkSemaphoreSelfTestSuccess {
  ok: true;
  verified: true;
  durationMs: number;
  commitmentPreview: string;
  proofDepth: number;
  groupSize: number;
  proofBytes: number;
}

export interface ZkSemaphoreSelfTestFailure {
  ok: false;
  verified: false;
  durationMs: number;
  error: string;
}

export type ZkSemaphoreSelfTestResult =
  | ZkSemaphoreSelfTestSuccess
  | ZkSemaphoreSelfTestFailure;

const TEST_PRIVATE_KEY_A = Uint8Array.from([
  101, 107, 107, 108, 101, 115, 105, 97,
  45, 115, 101, 109, 97, 112, 104, 111,
  114, 101, 45, 115, 101, 108, 102, 116,
  101, 115, 116, 45, 97, 45, 48, 49,
]);

const TEST_PRIVATE_KEY_B = Uint8Array.from([
  101, 107, 107, 108, 101, 115, 105, 97,
  45, 115, 101, 109, 97, 112, 104, 111,
  114, 101, 45, 115, 101, 108, 102, 116,
  101, 115, 116, 45, 98, 45, 48, 49,
]);

const SELF_TEST_MESSAGE = "ekklesia-zk-v2-self-test";
const SELF_TEST_SCOPE = "ekklesia-gh81-device-proof-check";
const SELF_TEST_TREE_DEPTH = 16;

export function formatZkSelfTestError(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === "string") return error;
  return "Unknown Semaphore self-test error";
}

export async function runZkSemaphoreSelfTestWithModule(
  semaphore: SemaphoreModuleLike,
  now = Date.now,
): Promise<ZkSemaphoreSelfTestResult> {
  const startedAt = now();

  try {
    const identity = new semaphore.Identity(TEST_PRIVATE_KEY_A);
    const secondIdentity = new semaphore.Identity(TEST_PRIVATE_KEY_B);
    const group = new semaphore.Group([identity.toElement(), secondIdentity.toElement()]);
    const proof = await semaphore.generateSemaphoreProof(
      identity,
      group,
      SELF_TEST_MESSAGE,
      SELF_TEST_SCOPE,
      SELF_TEST_TREE_DEPTH,
    );
    const verified = await semaphore.verifySemaphoreProof(proof);
    const durationMs = now() - startedAt;

    if (!verified) {
      return {
        ok: false,
        verified: false,
        durationMs,
        error: "Native Semaphore proof verification returned false",
      };
    }

    return {
      ok: true,
      verified: true,
      durationMs,
      commitmentPreview: identity.commitment().slice(0, 18),
      proofDepth: SELF_TEST_TREE_DEPTH,
      groupSize: group.members().length,
      proofBytes: proof.length,
    };
  } catch (error) {
    return {
      ok: false,
      verified: false,
      durationMs: now() - startedAt,
      error: formatZkSelfTestError(error),
    };
  }
}
