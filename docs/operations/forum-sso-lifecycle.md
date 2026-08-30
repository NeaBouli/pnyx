# Forum SSO Lifecycle Verification

## Scope and Threat Model

GH#258 is a client lifecycle correction, not an authentication-policy redesign.
Late network responses, old redirect timers and overlapping polls must not
complete a different or expired browser attempt. Development StrictMode effect
replay must not duplicate a nonce-consuming callback.

The client still signs `discourse_sso:${nonce}:${publicKey}` and sends only the
nonce, public key and signature. QR completion still sends only the nonce and
session ID. The server remains authoritative for verified identity eligibility,
canonical forum redirects, nonce TTL and atomic single-use consumption. No
private key, client-selected return URL or additional identity field is sent.
The API-returned redirect and app link retain their existing trust boundary.

## Implementation and Tests

- The server/hydration view does not access browser storage. Browser-only
  initialization occurs in a keyed session after hydration; storage denial
  falls back to the mobile-app QR path.
- Nonce, return URL and retry changes create a fresh lifecycle. Cleanup
  invalidates old asynchronous work and clears polling, expiry and redirects.
- One parsed initial request is retained across StrictMode effect replay;
  neither signed callbacks nor QR creation are duplicated by that replay.
- Polls are serial and completion is latched once. Five-minute expiry checks
  include a wall-clock deadline so delayed responses cannot revive an old QR.
- Initial and QR completion requests have a 15-second abort deadline, including
  response-body reads, so a stalled network exposes the existing retry UI.
  AbortController plus a cleared timer avoids requiring newer AbortSignal
  static helpers. A timeout never bypasses server nonce-consumption checks.
- Existing markup, CSS, app links and the four equal 2-by-2 download tiles are
  unchanged. No new login method, account policy or voter eligibility is added.
- JSDOM 26.1.0 is pinned as a test-only dependency compatible with the existing
  CI Node version. The lockfile adds its dev tree only. CI retains `npm ci` and
  `ignore-scripts=true`; no lint rule or security check is suppressed.

The first 19 deterministic DOM tests produced 11 failures against the unchanged
page before the patch. Kimi independently reproduced that baseline and verified
the fix. Sol added the review's additional malformed-response, StrictMode
polling and retry-race cases. The three subsequent stalled-request regressions
failed before the request-deadline fix; 29 lifecycle tests / 69 web tests pass, alongside
lint (zero warnings), typecheck, build and npm audit (zero findings).

Existing backend SSO tests (27) verify canonical callback targets, signatures,
nonce replay rejection and QR purpose. Sol also ran mail/SSO/real isolated
Redis contracts (37). Mock tests are not proof of production mail delivery or
a new real-citizen login canary.

Loopback browser verification covers Greek desktop/mobile QR and app-link
display, the 2-by-2 equal-size download grid, missing-parameter retry and browser
console errors. The 390px viewport had no horizontal overflow. Test fixtures
never proxy requests to production or use an actual citizen identity.

## Separate Web Rollout Gate

Repository integration does not deploy this patch. A later authorized Web-only
rollout must:

1. Record the exact merged commit, green required checks and security results.
   Inventory the currently deployed Web image and retain its digest/rollback
   tag. Include the pending PR #259 lifecycle changes in the release manifest.
2. Keep API, forum, database, DNS, secrets, IAM, app artifacts and Google Play
   unchanged. No automatic auth-config or personal-evaluation cutoff changes.
3. Verify the anonymous forum-to-verification-page redirect and missing-link
   error state, then QR/app-link rendering on desktop and mobile. Confirm old
   sessions do not navigate the new page. Real identity completion must be a
   voluntary owner/tester action, never identity impersonation by automation.
4. Check logout and ordinary bills/results navigation for regressions, record
   the evidence, and restore the prior Web image if an acceptance check fails.

GH#253 personal-evaluation adoption/cutoff, Google tester/time gates, DMARC
evidence and the newsletter handoff in GH#261 remain separate work.
