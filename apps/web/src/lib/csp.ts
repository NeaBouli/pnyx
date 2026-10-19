// Keep the static target and legacy value in sync with the Compose CSP gate.
export const LEGACY_CSP = "default-src 'self' https://api.ekklesia.gr; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://api.qrserver.com https://avatars.githubusercontent.com; connect-src 'self' https://api.ekklesia.gr https://api.coingecko.com https://arweave.net https://api.github.com https://polis-oauth-proxy.bergamolia.workers.dev; frame-ancestors 'none'";

export const STATIC_CSP = LEGACY_CSP.replace("script-src 'self' 'unsafe-inline'", "script-src 'self'") + "; object-src 'none'; base-uri 'self'";

export function noncePolicy(nonce: string): string {
  return STATIC_CSP.replace("script-src 'self'", `script-src 'self' 'nonce-${nonce}'`);
}

export function createNonce(): string {
  return btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32))));
}
