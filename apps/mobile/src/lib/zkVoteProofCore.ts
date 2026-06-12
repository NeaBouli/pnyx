import { canonicalZkMessageValue, canonicalZkScopeValue } from "./zkProofBinding";

const BN254_FIELD_MODULUS = 21888242871839275222246405745257275088548364400416034343698204186575808495617n;

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export interface SemaphoreVoteIdentityLike {
  toElement(): Uint8Array;
}

export interface SemaphoreVoteGroupLike {
  members(): Uint8Array[];
}

export interface SemaphoreVoteModuleLike {
  Identity: new (privateKey: Uint8Array) => SemaphoreVoteIdentityLike;
  Group: new (members: Uint8Array[]) => SemaphoreVoteGroupLike;
  generateSemaphoreProof(
    identity: SemaphoreVoteIdentityLike,
    group: SemaphoreVoteGroupLike,
    message: string,
    scope: string,
    treeDepth: number,
  ): Promise<string>;
}

export interface ZkVoteProofInput {
  privateKey: Uint8Array;
  voteScopeId: string;
  voteCommitment: string;
  members: string[];
  merkleDepth: number;
}

export interface ZkVoteProofResult {
  voteScopeId: string;
  voteCommitment: string;
  message: string;
  scope: string;
  groupSize: number;
  proof: Record<string, unknown>;
}

export function fieldDecimalToSemaphoreMemberBytes(value: string): Uint8Array {
  const clean = value.trim();
  if (!/^[0-9]+$/.test(clean)) {
    throw new Error("Semaphore member must be a decimal field value");
  }
  const field = BigInt(clean);
  if (field < 0n || field >= BN254_FIELD_MODULUS) {
    throw new Error("Semaphore member is outside the BN254 field");
  }
  const bytes = new Uint8Array(32);
  let current = field;
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number(current & 0xffn);
    current >>= 8n;
  }
  return bytes;
}

export async function generateZkVoteProofWithModule(
  semaphoreModule: SemaphoreVoteModuleLike,
  input: ZkVoteProofInput,
): Promise<ZkVoteProofResult> {
  if (input.merkleDepth <= 0) {
    throw new Error("merkleDepth must be positive");
  }
  if (input.members.length < 1) {
    throw new Error("ZK group has no members");
  }

  const identity = new semaphoreModule.Identity(input.privateKey);
  const memberBytes = input.members.map(fieldDecimalToSemaphoreMemberBytes);
  const identityMemberHex = bytesToHex(identity.toElement());
  const identityIsInGroup = memberBytes.some((member) => bytesToHex(member) === identityMemberHex);
  if (!identityIsInGroup) {
    throw new Error("Semaphore identity is not in the published group");
  }

  const group = new semaphoreModule.Group(memberBytes);
  const message = canonicalZkMessageValue(input.voteScopeId, input.voteCommitment);
  const scope = canonicalZkScopeValue(input.voteScopeId);
  const proofJson = await semaphoreModule.generateSemaphoreProof(
    identity,
    group,
    message,
    scope,
    input.merkleDepth,
  );
  const proof = JSON.parse(proofJson) as Record<string, unknown>;

  return {
    voteScopeId: input.voteScopeId,
    voteCommitment: input.voteCommitment,
    message,
    scope,
    groupSize: group.members().length,
    proof,
  };
}
