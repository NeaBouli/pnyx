# R8 Web-only rollout receipt

Date: 2026-09-24

## Scope and approval

- Owner approved rollout when ready. PR #353 merged normally as
  `c801c51d27dcb018f7ef8faa0417801cb73aff58` after required CI,
  Security Audit and review gates. Post-merge CI `36005799151` and Security
  Audit `36005799014` passed for the exact merge commit.
- Scope: remove the doubled disclosure-title line, remove the embedded public
  Plausible loader, and publish a bilingual EKA audit status page. No analytics
  replacement or change to the separate analytics/admin service was made.

## Build and rollback

- The host had 19 GB free and no active build before starting. An exact Git
  archive of the merge commit was built with `npm ci`, Next.js production build
  and TypeScript successfully. The candidate passed an isolated Web canary.
- Candidate: `ekklesia-web:r8-web-c801c51-20260924T133656Z`, image ID
  `sha256:6aa8c74acdf3bb91e81c37e3beeec31eda71edcc711ff0242d2650ad8772cf8c`.
- Exact previous image retained as
  `ekklesia-web:rollback-pre-r8-web-20260924T133656Z`, image ID
  `sha256:b749a2169f1740990109e63bb75f4ebfb32808475c1d2e5b9babd39c504f8adc`.
- Protected release directory:
  `/opt/ekklesia/releases/r8-web-c801c51-20260924T133656Z`. It contains the
  exact source archive, candidate and rollback Compose image overrides, and a
  bounded Web-only switch script. The existing 17-file Compose chain was
  preserved; only `web` was recreated with `--no-deps --no-build`.

## Acceptance

- 179 focused redesign tests passed. R2 landing, R3 all-Wiki and R4
  community/header gates passed. The redacted Gitleaks scan found no leaks.
  Claude independently reviewed the final PR diff with no blocking finding.
- The isolated canary returned HTTP 200 for Landing, audit, Wiki, Community,
  CSS and dynamic public routes. Landing, CSS, audit and Security files in the
  image matched the exact source hashes.
- Live: 21 Landing, Community, Wiki and dynamic routes returned HTTP 200.
  Landing SHA-256 `bceb42c30c833340e76c29ce331674402a71665ad0476bea57147f71e646d39b`,
  audit SHA-256 `8e83bd71dd438c7caa27b5d59ca9f190634445834846a29170db9b8ccfe83b0f`,
  and R5 CSS SHA-256 `e598505520778b971f351ef8385e913ed61c889108cbf7cde21a1bb31978c374`
  matched the exact merge source. The later status-count-only follow-up will
  intentionally change the audit page hash.
- Live Chromium at 360, 840 and 1280px found ten default-closed disclosure
  sections, title and summary bottom borders at 0px, no document overflow,
  the Wiki link, no analytics script and no JavaScript errors. The new audit
  page had visible content, no broken image and a working English toggle.
- API health returned HTTP 200. Web image ID matched the candidate with zero
  restarts, no OOM and no fatal/panic/unhandled/exception/error log marker.
  The SHA-256 of non-Web container identity/image listing was unchanged at
  `e5dd99e0f03b0e8a90b34afc2896187a042d9f426d5d591fc63b135661568531`.
  Protected environment and base Compose hashes were unchanged. No rollback
  was needed.

## Remaining boundary

- EKA-33's no-analytics technical fix is live. The public audit count and
  issue #318 checklist must be synchronized only after the documentation
  follow-up passes its own merge and live-acceptance gates.
- EKA-28 concerns a separate analytics/admin service and is not changed.
  No API, database, DNS, secret, IAM, Dashboard, forum, mobile, store,
  payment, provider or other service was changed.

## R8b audit-status addendum

- PR #354 merged normally as `fe675823c03d5083f8c37e83b844cf536ae852ce`.
  PR CI, CodeRabbit and post-merge CI `36015863610` / Security Audit
  `36015863747` passed. The 179 redesign tests, R3 full-Wiki gate, browser
  checks at 360/840/1280px and redacted Gitleaks scan passed before merge.
- The exact merge files `wiki/audit.html` and `wiki/security.html` were layered
  onto the already accepted R8 Web image. Candidate image
  `ekklesia-web:r8b-audit-fe67582-20260924T145858Z` has ID
  `sha256:96abd2651127bb9f76f60c7902d7b79a61c65140cd798229158dde336406f7a0`.
  Prior R8 image is retained as
  `ekklesia-web:rollback-pre-r8b-audit-20260924T145858Z` with ID
  `sha256:6aa8c74acdf3bb91e81c37e3beeec31eda71edcc711ff0242d2650ad8772cf8c`.
  Protected release directory:
  `/opt/ekklesia/releases/r8b-audit-fe67582-20260924T145858Z`.
- The isolated canary served Landing, audit, Security, Community and results
  with HTTP 200. Its two replaced files matched the merge source hashes.
  Only `ekklesia-web` was recreated using the preserved 18-file Compose chain
  and `--no-deps --no-build`.
- Live audit SHA-256
  `c8d358a50fc4cdd29ee0af25430b6d4b0b4109f4e1a32bbfe4a84bebd3f334f2`
  and Security SHA-256
  `f3aa111b27864f7b61cab9e4e7cd39e2b72b1a62a01dcda0c76ef8d5b57ee5fb`
  matched the exact merge source; Landing stayed at its R8 hash. All 21
  acceptance routes returned HTTP 200. Live Chromium at 360, 840 and 1280px
  showed EKA-33 and 61 remaining, Greek/English toggling, zero disclosure
  title lines, no analytics script, no overflow and no JS errors.
- Web image ID matched the candidate, with zero restarts, no OOM or error log
  marker. API health returned 200; the non-Web container listing digest and
  protected environment/base Compose hashes were unchanged. No rollback was
  needed. The EKA-33 checkbox and evidence comment in
  [issue #318](https://github.com/NeaBouli/pnyx/issues/318) were updated only
  after this live acceptance. EKA-28 remains open.
