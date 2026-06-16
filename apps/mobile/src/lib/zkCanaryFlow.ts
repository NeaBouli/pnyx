import {
  fetchZkRootMembers,
  submitZkOptIn,
  submitZkVote,
  verifyZkProof,
  type ZkOptInResponse,
  type ZkVerifyResponse,
  type ZkVoteAcceptResponse,
} from "./api";
import { signZkOptInPayload } from "./crypto-native";
import { getOrCreateZkSemaphoreIdentity } from "./zkSemaphoreIdentity";
import { generateZkVoteProof } from "./zkVoteProof";

export interface ZkOptInFlowResult {
  commitment: string;
  memberHex: string;
  response: ZkOptInResponse;
}

export interface ZkCanaryVerifyFlowResult {
  real: ZkVerifyResponse;
  mutations: {
    message: ZkVerifyResponse;
    scope: ZkVerifyResponse;
    root: ZkVerifyResponse;
    depth: ZkVerifyResponse;
  };
  groupSize: number;
}

export async function submitZkOptInForBill(billId: string): Promise<ZkOptInFlowResult> {
  const voteScopeId = `bill:${billId}`;
  const identity = await getOrCreateZkSemaphoreIdentity(voteScopeId);
  const signature = await signZkOptInPayload(billId, identity.commitment);
  const response = await submitZkOptIn({
    nullifierHash: signature.nullifierHash,
    billId,
    commitment: identity.commitment,
    signatureHex: signature.signatureHex,
  });
  return {
    commitment: identity.commitment,
    memberHex: identity.memberHex,
    response,
  };
}

export async function submitZkVoteWithPublishedRoot(params: {
  voteScopeId: string;
  voteCommitment: string;
}): Promise<ZkVoteAcceptResponse> {
  const proof = await buildZkVoteProofWithPublishedRoot(params);
  return submitZkVote({
    voteScopeId: params.voteScopeId,
    voteCommitment: params.voteCommitment,
    proof: proof.proof,
  });
}

async function buildZkVoteProofWithPublishedRoot(params: {
  voteScopeId: string;
  voteCommitment: string;
}) {
  const root = await fetchZkRootMembers(params.voteScopeId);
  return generateZkVoteProof({
    voteScopeId: params.voteScopeId,
    voteCommitment: params.voteCommitment,
    members: root.members,
    merkleDepth: root.merkle_depth,
  });
}

function incrementProofField(proof: Record<string, unknown>, field: string): Record<string, unknown> {
  const clone = { ...proof };
  const value = clone[field];
  if (typeof value === "string" && /^[0-9]+$/.test(value)) {
    clone[field] = (BigInt(value) + 1n).toString();
  } else if (typeof value === "number") {
    clone[field] = value + 1;
  } else {
    clone[field] = `${String(value)}-mutated`;
  }
  return clone;
}

export async function verifyZkVoteWithPublishedRoot(params: {
  voteScopeId: string;
  voteCommitment: string;
}): Promise<ZkCanaryVerifyFlowResult> {
  const proof = await buildZkVoteProofWithPublishedRoot(params);
  const verify = (candidate: Record<string, unknown>) => verifyZkProof({
    voteScopeId: params.voteScopeId,
    proof: candidate,
  });

  const [real, message, scope, root, depth] = await Promise.all([
    verify(proof.proof),
    verify(incrementProofField(proof.proof, "message")),
    verify(incrementProofField(proof.proof, "scope")),
    verify(incrementProofField(proof.proof, "merkleTreeRoot")),
    verify(incrementProofField(proof.proof, "merkleTreeDepth")),
  ]);

  return {
    real,
    mutations: { message, scope, root, depth },
    groupSize: proof.groupSize,
  };
}
