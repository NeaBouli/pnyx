import { LEGACY_CSP } from "../../csp.mjs";
export { LEGACY_CSP };

export const STATIC_CSP = LEGACY_CSP.replace("script-src 'self' 'unsafe-inline'", "script-src 'self'") + "; font-src 'self'; object-src 'none'; base-uri 'self'";

export function noncePolicy(nonce: string): string {
  return STATIC_CSP.replace("script-src 'self'", `script-src 'self' 'nonce-${nonce}'`);
}

export function createNonce(): string {
  return btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))));
}
