import { afterEach, expect, it, vi } from "vitest";
import { createNonce, LEGACY_CSP, noncePolicy, STATIC_CSP } from "./csp";
afterEach(() => vi.restoreAllMocks());
it("nonces use Web Crypto with at least 128 random bits and change per call", () => {
  const random = vi.spyOn(crypto, "getRandomValues");
  const a = createNonce(), b = createNonce();
  expect(a).not.toBe(b);
  expect(Buffer.from(a, "base64").byteLength).toBeGreaterThanOrEqual(16);
  expect(random).toHaveBeenCalledTimes(2);
  expect(random.mock.calls[0][0]).toBeInstanceOf(Uint8Array);
  expect(random.mock.calls[0][0]!.byteLength).toBeGreaterThanOrEqual(16);
});
it("target policy permits only local fonts and a fresh script nonce", () => {
  const nonce = createNonce();
  const policy = noncePolicy(nonce);
  expect(policy).toContain(`script-src 'self' 'nonce-${nonce}'`);
  expect(policy).toContain("font-src 'self'");
  expect(STATIC_CSP).not.toContain("script-src 'self' 'unsafe-inline'");
  expect(LEGACY_CSP).toContain("frame-ancestors 'none'");
  // Observation uses browser violation events; no unimplemented report endpoint.
  expect(policy).not.toMatch(/report-uri|report-to/);
});
