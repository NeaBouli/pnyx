import { describe, expect, it } from "vitest";
import { ed25519 } from "@noble/curves/ed25519.js";

import { IMPORT_CODE_PREFIX, importCodeChecksum, parseImportCode, publicKeyFingerprint } from "./import-code";

const toHex = (bytes: Uint8Array) => Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");

const PRIVATE_KEY = "01".repeat(32);
const PUBLIC_KEY = toHex(ed25519.getPublicKey(Uint8Array.from({ length: 32 }, () => 1)));
const NULLIFIER = "3".repeat(64);

function code(priv = PRIVATE_KEY, nullifier = NULLIFIER, pub = PUBLIC_KEY, checksum?: string): string {
  return `${IMPORT_CODE_PREFIX}:${priv}:${nullifier}:${pub}:${checksum ?? importCodeChecksum(priv, nullifier, pub)}`;
}

describe("import code", () => {
  it("matches the API golden vector (apps/api/tests/test_admin_import_code.py)", () => {
    expect(importCodeChecksum("11".repeat(32), "22".repeat(32), "33".repeat(32))).toBe("3d847acc");
  });

  it("parses a valid code, tolerating whitespace and upper case", () => {
    const pasted = `  ${code().toUpperCase().replace(IMPORT_CODE_PREFIX.toUpperCase(), IMPORT_CODE_PREFIX)}\n`;
    expect(parseImportCode(pasted)).toEqual({
      privateKey: PRIVATE_KEY, nullifier: NULLIFIER, publicKey: PUBLIC_KEY,
    });
  });

  it("rejects deep-link URLs and other formats", () => {
    expect(() => parseImportCode(`ekklesia://import-account?key=${PRIVATE_KEY}&nullifier=${NULLIFIER}&pubkey=${PUBLIC_KEY}`))
      .toThrow("invalid-format");
    expect(() => parseImportCode(code().replace(IMPORT_CODE_PREFIX, "EKKLESIA-IMPORT-V2"))).toThrow("invalid-format");
    expect(() => parseImportCode(code(PRIVATE_KEY.slice(2)))).toThrow("invalid-format");
  });

  it("rejects a wrong checksum (typo or truncation)", () => {
    expect(() => parseImportCode(code(PRIVATE_KEY, NULLIFIER, PUBLIC_KEY, "00000000"))).toThrow("invalid-checksum");
    const typo = code().replace(`:${NULLIFIER}:`, `:4${NULLIFIER.slice(1)}:`);
    expect(() => parseImportCode(typo)).toThrow("invalid-checksum");
  });

  it("rejects a public key that does not belong to the private key", () => {
    expect(() => parseImportCode(code(PRIVATE_KEY, NULLIFIER, "ab".repeat(32)))).toThrow("key-mismatch");
  });

  it("never echoes the code in error messages", () => {
    try {
      parseImportCode(code(PRIVATE_KEY, NULLIFIER, PUBLIC_KEY, "00000000"));
    } catch (error) {
      expect(String(error)).not.toContain(PRIVATE_KEY);
      expect(String(error)).not.toContain(NULLIFIER);
    }
  });

  it("formats a short public key fingerprint", () => {
    expect(publicKeyFingerprint("ab".repeat(16) + "cd".repeat(16))).toBe("ABAB ABAB … CDCD CDCD");
  });
});
