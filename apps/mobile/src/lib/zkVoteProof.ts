import { getOrCreateZkSemaphoreIdentity } from "./zkSemaphoreIdentity";
import { generateZkVoteProofWithModule, type SemaphoreVoteModuleLike, type ZkVoteProofResult } from "./zkVoteProofCore";

export {
  fieldDecimalToSemaphoreMemberBytes,
  generateZkVoteProofWithModule,
  type SemaphoreVoteGroupLike,
  type SemaphoreVoteIdentityLike,
  type SemaphoreVoteModuleLike,
  type ZkVoteProofInput,
  type ZkVoteProofResult,
} from "./zkVoteProofCore";

declare const require: (name: string) => unknown;

export async function generateZkVoteProof(params: {
  voteScopeId: string;
  voteCommitment: string;
  members: string[];
  merkleDepth: number;
}): Promise<ZkVoteProofResult> {
  const identity = await getOrCreateZkSemaphoreIdentity(params.voteScopeId);
  const runtimeSemaphore = require("semaphore-react-native") as SemaphoreVoteModuleLike;
  return generateZkVoteProofWithModule(runtimeSemaphore, {
    privateKey: identity.privateKey,
    voteScopeId: params.voteScopeId,
    voteCommitment: params.voteCommitment,
    members: params.members,
    merkleDepth: params.merkleDepth,
  });
}
