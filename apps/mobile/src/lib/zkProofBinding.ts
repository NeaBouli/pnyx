import { sha256 } from "@noble/hashes/sha2.js";

export const ZK_PROOF_BINDING_VERSION = "ekklesia.zk.binding.v1";
const ZK_SCOPE_DOMAIN = `${ZK_PROOF_BINDING_VERSION}:scope:`;
const ZK_MESSAGE_DOMAIN = `${ZK_PROOF_BINDING_VERSION}:message:`;
const ZK_SCOPE_TEXT_PREFIX = "zks:";
const ZK_MESSAGE_TEXT_PREFIX = "zkm:";
const DIGEST_TEXT_CHARS = 28;
const BASE64URL = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

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
  return semaphoreTextToBigIntString(canonicalZkScopeText(voteScopeId));
}

export function canonicalZkMessageValue(voteScopeId: string, voteCommitment: string): string {
  return semaphoreTextToBigIntString(canonicalZkMessageText(voteScopeId, voteCommitment));
}

export function canonicalZkScopeText(voteScopeId: string): string {
  return sha256ToSemaphoreText(ZK_SCOPE_TEXT_PREFIX, `${ZK_SCOPE_DOMAIN}${validateVoteScopeId(voteScopeId)}`);
}

export function canonicalZkMessageText(voteScopeId: string, voteCommitment: string): string {
  const scope = validateVoteScopeId(voteScopeId);
  const cleanCommitment = voteCommitment.trim();
  if (!cleanCommitment || cleanCommitment.length > 160) {
    throw new Error("vote_commitment must be 1..160 characters");
  }
  return sha256ToSemaphoreText(ZK_MESSAGE_TEXT_PREFIX, `${ZK_MESSAGE_DOMAIN}${scope}:${cleanCommitment}`);
}

function sha256ToSemaphoreText(prefix: string, value: string): string {
  const digest = base64UrlNoPadding(sha256(new TextEncoder().encode(value))).slice(0, DIGEST_TEXT_CHARS);
  const text = `${prefix}${digest}`;
  if (new TextEncoder().encode(text).length > 32) {
    throw new Error("canonical Semaphore binding text must fit 32 UTF-8 bytes");
  }
  return text;
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

function base64UrlNoPadding(bytes: Uint8Array): string {
  let output = "";
  let buffer = 0;
  let bits = 0;
  for (const byte of bytes) {
    buffer = (buffer << 8) | byte;
    bits += 8;
    while (bits >= 6) {
      bits -= 6;
      output += BASE64URL[(buffer >> bits) & 0x3f];
    }
  }
  if (bits > 0) {
    output += BASE64URL[(buffer << (6 - bits)) & 0x3f];
  }
  return output;
}
