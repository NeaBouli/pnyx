import {
  fetchZkRootMembers,
  submitZkOptIn,
  submitZkVote,
  type ZkOptInResponse,
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

export async function submitZkOptInForBill(billId: string): Promise<ZkOptInFlowResult> {
  const identity = await getOrCreateZkSemaphoreIdentity();
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
  const root = await fetchZkRootMembers(params.voteScopeId);
  const proof = await generateZkVoteProof({
    voteScopeId: params.voteScopeId,
    voteCommitment: params.voteCommitment,
    members: root.members,
    merkleDepth: root.merkle_depth,
  });
  return submitZkVote({
    voteScopeId: params.voteScopeId,
    voteCommitment: params.voteCommitment,
    proof: proof.proof,
  });
}
