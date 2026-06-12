import { sha256 } from "@noble/hashes/sha256";

export const ZK_PROOF_BINDING_VERSION = "ekklesia.zk.binding.v1";
const ZK_SCOPE_DOMAIN = `${ZK_PROOF_BINDING_VERSION}:scope:`;
const ZK_MESSAGE_DOMAIN = `${ZK_PROOF_BINDING_VERSION}:message:`;

export function semaphoreTextToBigIntString(value: string): string {
  const raw = new TextEncoder().encode(value);
  if (raw.length < 1 || raw.length > 32) {
    throw new Error("Semaphore text BigInt input must be 1..32 UTF-8 bytes");
  }
  const padded = new Uint8Array(32);
  padded.set(raw);
  return bytesToBigInt(padded).toString();
}

export function canonicalZkScopeValue(voteScopeId: string): string {
  return sha256ToFieldDecimal(`${ZK_SCOPE_DOMAIN}${validateVoteScopeId(voteScopeId)}`);
}

export function canonicalZkMessageValue(voteScopeId: string, voteCommitment: string): string {
  const scope = validateVoteScopeId(voteScopeId);
  const cleanCommitment = voteCommitment.trim();
  if (!cleanCommitment || cleanCommitment.length > 160) {
    throw new Error("vote_commitment must be 1..160 characters");
  }
  return sha256ToFieldDecimal(`${ZK_MESSAGE_DOMAIN}${scope}:${cleanCommitment}`);
}

function sha256ToFieldDecimal(value: string): string {
  return (bytesToBigInt(sha256(new TextEncoder().encode(value))) >> 8n).toString();
}

function validateVoteScopeId(value: string): string {
  const clean = value.trim();
  if (!/^(bill|municipal|regional):[A-Za-z0-9._-]{1,110}$/.test(clean)) {
    throw new Error("invalid vote_scope_id");
  }
  return clean;
}

function bytesToBigInt(bytes: Uint8Array): bigint {
  let value = 0n;
  for (const byte of bytes) {
    value = (value << 8n) + BigInt(byte);
  }
  return value;
}
