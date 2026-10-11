/**
 * In-app import code for admin test identities (EVA-034/035).
 *
 * Format: EKKLESIA-IMPORT-V1:<private_key_hex>:<nullifier_hex>:<public_key_hex>:<checksum8>
 * checksum8 = first 8 hex of SHA-256("EKKLESIA-IMPORT-V1:<priv>:<nullifier>:<pub>").
 * Built by apps/api/routers/admin_account.py build_import_code(). The code is
 * pasted into the import screen; it is never handled as a deep link.
 */
import { sha256 } from "@noble/hashes/sha2.js";
import { ed25519 } from "@noble/curves/ed25519.js";

import type { ImportedAccountCredentials } from "./import-account";

export const IMPORT_CODE_PREFIX = "EKKLESIA-IMPORT-V1";

const HEX64 = /^[0-9a-f]{64}$/;

function bytesToHex(value: Uint8Array): string {
  return Array.from(value, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function hexToBytes(value: string): Uint8Array {
  return Uint8Array.from(value.match(/.{2}/g)!.map((byte) => Number.parseInt(byte, 16)));
}

export function importCodeChecksum(privateKey: string, nullifier: string, publicKey: string): string {
  const body = `${IMPORT_CODE_PREFIX}:${privateKey}:${nullifier}:${publicKey}`;
  return bytesToHex(sha256(new TextEncoder().encode(body))).slice(0, 8);
}

/**
 * Validate a pasted import code and return the credentials it carries.
 * Rejects wrong prefix, malformed hex, a bad checksum (typo, truncation) and a
 * public key that does not belong to the private key. Error messages never
 * contain any part of the code.
 */
export function parseImportCode(input: string): ImportedAccountCredentials {
  const parts = input.replace(/\s+/g, "").split(":");
  if (parts.length !== 5 || parts[0] !== IMPORT_CODE_PREFIX) {
    throw new Error("invalid-format");
  }
  const [, rawPrivate, rawNullifier, rawPublic, checksum] = parts;
  const privateKey = rawPrivate.toLowerCase();
  const nullifier = rawNullifier.toLowerCase();
  const publicKey = rawPublic.toLowerCase();
  if (!HEX64.test(privateKey) || !HEX64.test(nullifier) || !HEX64.test(publicKey)) {
    throw new Error("invalid-format");
  }
  if (checksum.toLowerCase() !== importCodeChecksum(privateKey, nullifier, publicKey)) {
    throw new Error("invalid-checksum");
  }
  if (bytesToHex(ed25519.getPublicKey(hexToBytes(privateKey))) !== publicKey) {
    throw new Error("key-mismatch");
  }
  return { privateKey, nullifier, publicKey };
}

/** Short, readable public key fingerprint for the confirmation step. */
export function publicKeyFingerprint(publicKey: string): string {
  const hex = publicKey.toUpperCase();
  const groups = [hex.slice(0, 4), hex.slice(4, 8), hex.slice(-8, -4), hex.slice(-4)];
  return `${groups[0]} ${groups[1]} … ${groups[2]} ${groups[3]}`;
}
