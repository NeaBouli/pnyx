# Pnyx / ekklesia.gr Bridge

## 2026-09-20 - R3 Full Wiki Web-only Rollout Completed

- Merged PR #335 (`b5000e76`) was released through a bounded image-only Web
  overlay. Only the 14 wiki HTML files and their four local R3 assets changed.
- The exact prior Web image is retained as
  `ekklesia-web:rollback-pre-r3-wiki-20260920T195518Z`; the candidate is
  `ekklesia-web:r3-wiki-b5000e7-20260920T195518Z`.
- All 14 production pages and four assets returned HTTP 200 and matched the
  target commit byte-for-byte. Real Chrome passed all 14 pages at 1440x1000 and
  360x800, and the 57 FAQ controls passed live Enter/Space and ARIA checks.
- The Web container has zero restarts and was not OOM-killed. API health and all
  non-Web container identities, images and states remained unchanged. Protected
  environment and Compose hashes also remained unchanged.
- No API, database, DNS, secret, IAM, Dashboard, forum, store, payment, provider
  or other service changed. No rollback was required.

Details: [R3 wiki rollout receipt](docs/operations/R3_WIKI_ROLLOUT_2026-09-20.md).

## 2026-09-20 - R3 Full Wiki Source Migration Validated

- The 13 remaining wiki pages now use the same local R3 shell as the merged
  pilot. All pre-existing text, bilingual pairs, links, metadata, forms,
  scripts, event handlers, inline styles, API contracts and external hosts are
  preserved by the fail-closed R0 comparison.
- The shared stylesheet covers the existing table, FAQ, roadmap, code, badge,
  content and motion variants without adding external assets. A real-browser
  finding raised two Broadcasting copy controls to the 44px target and keeps
  very tall mobile tables visible when the legacy 10% intersection threshold
  cannot be reached.
- Verification passed: the default and explicit full R3 gates, R1 foundation,
  117 redesign tests, Python compilation, static local-link resolution,
  `git diff --check` and Gitleaks. Real Chromium covered all 14 wiki pages at
  1440x1000 and 360x800 with no document overflow, missing landmark, broken
  local image, table-containment failure, language-toggle failure or
  migration-attributable JavaScript exception.
- CodeRabbit's two valid findings were resolved before integration: malformed
  footer nesting is now rejected by the structural gate, and all 57 existing
  FAQ questions expose browser-verified keyboard and synchronized ARIA state
  through a bounded local progressive-enhancement asset.
- This is source validation only. No production, server, database, DNS, IAM,
  secret, provider, payment, application, API or store change occurred. Normal
  protected-branch integration and a separately authorized web-only rollout
  remain later gates.

## 2026-09-20 - Independent Catalog and R0/R1 Review

- Claude Code completed a read-only review of the full PR #323 and stacked PR
  #332 diffs. It found no blocking correctness, security, privacy,
  accessibility or regression issue and changed no file.
- The review confirmed the 13-file design handoff remains reference-only and
  outside runtime/build paths, the 64-entry EKA register is coherent, the R0
  inventory is fail-closed and deterministic, and the R1 foundation preserves
  its isolation and CSP/accessibility constraints.
- One non-blocking but real typo was verified in the authoritative checkpoint:
  its baseline commit omitted one hexadecimal character and did not resolve.
  The report now uses the already-referenced valid 40-character commit ID.
- An older append-only bridge entry still reports the then-current 34-test
  count; the newer resolver entry correctly records the current 37-test suite.
  Historical bridge text was not rewritten.

## 2026-09-20 - Audit/Redesign Catalog Integration Readiness Review

- Sol completed the deferred read-only review of PR #323 after Kimi returned a
  weekly-quota `403` before reading or changing the repository. The branch is
  exactly 12 commits ahead of and zero commits behind `main`; all existing CI
  and Security jobs pass and the PR is mergeable.
- The imported 13-file design archive matches the owner's ZIP SHA-256 and file
  count. It remains outside `docs/`, has no application/build/workflow
  reference and is explicitly classified as reference-only; its prototype
  CDN/dynamic-code behavior cannot enter the current runtime implicitly.
- Gitleaks found no secret in the branch. The 64-item EKA register, status,
  TODO, plan, issue #318 and rollout receipts are coherent except for one stale
  EKA-17 checkbox/text in the master report. That entry and the TODO summary
  were corrected to the already verified closed state; no other status or
  application content changed.
- PR #323 may move to external review after this documentation correction and
  fresh checks. PR #332 remains stacked and must absorb this parent commit
  before its own integration gate.

## 2026-09-20 - Redesign R0 Resolver Review Correction

- CodeRabbit identified one valid R0 inventory defect in stacked PR #332:
  relative resource paths were anchored below `docs/` even though the page
  path already included that prefix. This made four existing local
  stylesheets appear unresolved without changing the public pages themselves.
- Kimi implemented the bounded correction under Sol review. Relative resources
  now resolve from the repository root, root-relative behavior remains
  unchanged and path traversal outside `docs/` still fails closed.
- Three regressions cover nested relative resolution, root-relative behavior
  and traversal rejection. The complete redesign suite now passes 37 tests;
  regenerated R0 artifacts are byte-for-byte reproducible and all four local
  stylesheets resolve with content hashes.
- All 35 allowlisted public HTML pages remain byte-identical to the parent
  branch. No live page, application, dependency, workflow or production
  service changed.

## 2026-09-20 - Redesign R0/R1 Prepared in an Isolated Stacked Branch

- The complete current public surface is frozen by an exact 35-path allowlist
  and deterministic baseline inventory. It records content, bilingual values,
  metadata, links, forms, resources, API contracts, structured data,
  interactions, responsive markers and stable category hashes. Regeneration
  fails closed on page-set drift, malformed JSON-LD and unrecorded duplicate
  IDs.
- The inventory surfaced one pre-existing duplicate ID, `dot-mod02`, in
  `docs/wiki/modules.html`. It is recorded as a bounded baseline defect because
  R0/R1 may not modify public pages; any new occurrence still fails closed.
- The R1 foundation remains outside `docs/` and is not public or deployed. It
  contains local tokens, a semantic shell and loading/error/empty/focus states,
  with no external request, runtime script, inline style/handler, prototype
  runtime, negative letter spacing or viewport-scaled typography.
- Sol reviewed the Kimi implementation and tightened markup-API/inline-style
  inventory coverage, path containment and strict-CSP/mobile behavior. The
  final 34 focused tests, byte-for-byte regeneration, secret-pattern scan and
  boundary checks pass. Real Chromium renders at 1440px and an emulated 360px
  viewport have no overflowing elements (`scrollWidth == innerWidth`).
- This work is intentionally stacked on the reference-only catalog branch at
  `2f474e6`. None of the 35 existing HTML files, app code, imported handoff,
  dependencies, workflows or production services changed. R2 and all content,
  font/icon, CSP and owner-dependent visual decisions remain separate gates.

## 2026-09-20 - EKA-17 HLR Environment Migration Completed

- PR #331 remains the reviewed source authority at
  `c18b75ffb616655a4b308bf7f314dc2f48472628`. Production received only its
  `packages/crypto/hlr.py` runtime file as an overlay on the exact previously
  running API image; the deployed file SHA-256 is
  `74f982b192356bdae65d55be389a6708c7be183adab673e04492b7054fccf5b5`.
- The complete legacy primary credential pair was copied atomically to the
  canonical `HLRLOOKUP_*` names without printing values. Legacy aliases remain
  temporarily for rollback compatibility; the separate `HLRLOOKUPS_*` fallback
  pair is unchanged. Host-file and container values were equal before and after
  the migration.
- Only `ekklesia-api` was recreated. The candidate image is
  `ekklesia-api:eka17-c18b75f-20260920T133207Z`; the exact prior image remains
  tagged `ekklesia-api:rollback-pre-eka17-20260920T133207Z`, and the original
  environment file is retained in the protected release directory.
- Five repeated health probes, live credential-resolution checks, public HLR
  status, container state and logs passed. The API has zero restarts, was not
  OOM-killed, no non-target container changed and HLR usage counters were
  identical before and after. No real number lookup or provider request ran.
- No database, DNS, IAM, Web, Dashboard, forum, store, payment or other service
  changed. EKA-17 is closed on source, rollout and live acceptance evidence.

Details: [EKA-17 release receipt](docs/operations/EKA17_HLR_ENV_ROLLOUT_2026-09-20.md).

## 2026-09-06 - Android v1.0.32 API/Web Rollout Completed

- PR #294 merged normally as
  `ff2622f90ca0c0db94881bee13ec1ed4cb6317c8` after all required CI, Security
  and review checks passed without bypass.
- The bounded production rollout completed at 09:10 UTC. The public app-version
  contract now reports `1.0.32` / `61` with `force_update=false`, and Web,
  SSO, FAQ, roadmap and `llms.txt` return HTTP 200.
- `https://ekklesia.gr/download/ekklesia-latest.apk` now serves the verified
  v1.0.32 Direct APK: 82,777,431 bytes, SHA-256
  `67e051c549c9e97d1ebfa0a840f4e41216125403bfc5614a79563062154bec56`.
- Production images are `ekklesia-api:app-v61-20260906T090233Z` and
  `ekklesia-web:app-v61-20260906T090233Z`. The API image preserves the prior
  Telegram/ZK-count image and changes only `app_version.py`; the Web image uses
  the previously deployed v60 source baseline plus the reviewed v61 static and
  SSO overlays.
- Rollback source/image tag `rollback-pre-app-v61-20260906T090233Z` is retained
  at pre-change source `25d6c14499905bdcb901488f3ac00b275fd9b620`.
  Protected configuration, HLR runtime values and all 41 non-target containers
  were unchanged. Both new containers have restart count zero and no new error
  markers.
- Google Play vC61 remains under Closed Testing Alpha review. No production
  track, F-Droid, database, DNS, secret, IAM, dashboard or other service was
  changed.

## 2026-09-06 - Android v1.0.32 Submitted to Google Play Closed Testing

- Google Play accepted `61 (1.0.32)` for the Closed Testing Alpha track with
  Greek release notes and no supported-device removals.
- The change is under Google review. No production-track promotion occurred.
- The bounded API/Web/latest-APK rollout remains a separate controlled gate;
  the running v1.0.31 images and alias are unchanged at this point.

## 2026-09-06 - Android v1.0.32 GitHub Release Published

- PR #292 merged normally as `d25d4ee116055ff8395e1305d4f77bf6de414ace`
  after all required CI, Security and review gates passed without bypass.
- GitHub release `v1.0.32` is public and its tag resolves exactly to that merge
  commit. The Direct APK, Play AAB and checksum file are uploaded.
- GitHub's uploaded-asset digests match the locally verified APK SHA-256
  `67e051c549c9e97d1ebfa0a840f4e41216125403bfc5614a79563062154bec56`
  and AAB SHA-256
  `1064bad1d21e80f47b36c331defaf0b501d1d5e72374c431155f782fb3208b24`.
- Public API/Web references are prepared in a separate post-publication branch.
  Google Play Closed Testing submission and the bounded API/Web/latest-alias
  rollout remain later gates; no production-track promotion has occurred.

## 2026-09-06 - Android v1.0.32 Icon Badge Release Prepared

- v1.0.32/versionCode 61 adds local, category-aware app-icon notification
  counts for enabled notifications. Counts are capped at 99 and cleared when
  the app opens, returns to the foreground or a notification switch is disabled.
  Numeric display remains dependent on Android launcher support; some launchers
  show a dot.
- Direct APK and Play AAB release builds pass and retain the established signing
  certificate. Their SHA-256 values are recorded in
  `docs/operations/ANDROID_V61_RELEASE_2026-09-05.md`.
- The local F-Droid helper is aligned with the official native exclusion of
  `expo-notifications`. F-Droid remains a separate unsigned source-build path;
  no Direct or Play binary is uploaded there.
- Publication is ordered and fail-closed: protected merge and green checks,
  GitHub release plus checksum verification, Play Closed Testing submission,
  then bounded API/Web/latest-APK rollout with rollback tags and live probes.
- No production-track promotion, database, DNS, secret, IAM, voting, identity,
  eligibility or ZK change is part of this release.

## 2026-09-05 - Android Xiaomi and HLR Follow-Up Prepared (PR #291)

- A bounded follow-up fixes two remaining false-negative paths without changing
  voting, identity, eligibility, ZK, database or release policy: Android Picker
  item/selected text now has explicit theme-safe colors, and Greek mobile input
  also accepts the locally written `069...` form.
- Fallback HLR remains fail-closed for identity issuance: only `CONNECTED`
  passes. `ABSENT` and `UNDETERMINED` return a temporary retry message; invalid
  and confirmed-dead results remain rejected. This closes the security review
  finding that an assigned-but-unreachable number must not authorize identity.
- Verification passed: 41 crypto/HLR tests, 206 mobile tests, 11 dependency
  security regressions, TypeScript, native Android Direct Debug build for all
  supported ABIs, diff check and isolated secret scan. Kimi reviewed the
  secret-free patch and returned `APPROVE WITH COMMENTS`; Sol resolved every
  verifiable comment against the installed sources and tests.
- CodeRabbit subsequently identified the new `ABSENT` authorization path as
  unsafe. The path was removed, the fallback boundary tests were updated, and
  all 36 crypto tests passed again. Kimi was unavailable for this follow-up due
  to a local file-watcher failure; Sol performed the final diff review.
- The live Direct APK remains unchanged at v1.0.31/vC60. Its live SHA-256 is
  `dde71f9edfbfb8251831ecbf42cf3200f354c9e0329cefb65025f272b91a15dc`,
  and the stale repository checksum record is corrected to match it. The
  landing documentation now warns that Direct, Play and F-Droid signatures
  cannot update across channels without uninstalling and re-verifying.
- No API, app, website, Google Play, F-Droid, database, DNS, secret, IAM or
  production change occurred. Two local Android AVDs failed before app install
  because their Android package service never started; this is retained as a
  test-host issue and is not attributed to Ekklesia.
- App-icon notification counts are not implemented in this PR. The mobile
  handler still has `shouldSetBadge: false`; the bounded badge task is tracked
  separately so it cannot silently alter this verification release.

## 2026-09-04 - Private VLABS finance handoff refreshed

- This public repository contains no finance details. Community support remains
  disabled while the current private VLABS operator gates are processed.
- The project developer must record exact `PRODUCT_READY` evidence for the
  support UI. VLABS must separately return `FINANCE_READY`; both are required
  before any support control can be enabled.
- Obtain the current finance instructions through Gio and the private VLABS
  operator only. Do not add recipient, account, tax, provider, donor, document
  or runtime values here.

## 2026-08-31 - GH261 Consent Guard, Not a Rollout

- Fresh read-only inventory: five local confirmations, two provider-list
  contacts, three missing provider contacts, zero list-only contacts. No live
  contacts or production data changed. The operator-only DOI and test delivery
  succeeded; both one-message budgets are exhausted, not ongoing consent.
- Code adds atomic single-use confirmation without overwriting preferences,
  future-only timestamped evidence and admin-only aggregate readiness checks.
  The readiness path has no apply mode and always proposes zero writes.
- Automatic audience enrollment remains blocked by incomplete historical
  consent/suppression evidence and missing campaign preference enforcement.
  GH#261 stays open; no provider, list, scheduler, secret or deployment change.
  See `docs/operations/newsletter-delivery-audit.md` for scope and release gates.

## 2026-08-30 - Send-Only Mail and SSO Follow-Up

- Owner confirmed no domain inboxes or forum reply-by-email. Newsletter
  delivery remains outbound through Brevo. PR #262 routes new replies to the
  existing published external operator contact; configured contact-form
  recipients remain authoritative. DNS, secrets and production are unchanged.
- Subscriber handoff from confirmed Redis/Listmonk records into the Brevo
  campaign list is not established by the repository code: GH#261 records the
  separate consent-safe inventory/reconciliation gate. No bulk contact write,
  provider change or real campaign was performed.
- GH#258 now has 29 deterministic lifecycle tests and zero web lint warnings.
  Kimi reproduced the original 11 failing cases and independently reviewed the
  protocol invariants; Sol added edge cases and verified the unchanged Greek
  desktop/mobile layout. The complete web suite has 69 passing tests.
- Web rollout, API mail-delivery verification, GH#253 adoption/cutoff, Google
  testers and full DMARC evidence remain distinct gates. See `docs/STATUS.md`,
  `docs/TODO.md` and `docs/operations/forum-sso-lifecycle.md` for current state;
  the entries below retain their historical verification scope.

## 2026-08-30 - Bounded Completion and Gate Reconciliation

- The active scope is the approved status block 1-8, excluding donation work
  (point 7). Production, credentials and published app artifacts are unchanged.
- Current integration, security dependency gates, store/DMARC evidence and
  future backlog are distinguished in `docs/STATUS.md` and `docs/TODO.md`.
- PR #257 (`9ec3591`) prepares signed personal reads; PR #259 (`54ff2fc`)
  integrates the bounded web cleanup. Neither merge publishes a release.
- At the PR #259 checkpoint, one SSO initialization warning remained under
  GH#258; 19 others were fixed without suppressions or dependency churn.
  That historical checkpoint is superseded by the GH#258 verification above.
- Personal evaluation migration remains GH#253 through app release, adoption
  and cutoff. No tracker may equate an additive API/mobile patch with completed
  production enforcement.
- Four image-size alerts remain visible; no compatible patched upstream
  release was found. ecdsa and TypeScript-7 upstream gates are unchanged.
- Private Google Play enrollment evidence and the DMARC catalog remain in the
  local gitignored operations bridge. NEA-422 remains In Progress.

## 2026-08-24 — Real DiscourseConnect Canary Complete

- The owner completed the voluntary production canary with an existing
  verified Ekklesia mobile identity: the forum QR was scanned, the pseudonymous
  `verified-citizens` session opened successfully, and logout returned the
  browser to the anonymous forum state.
- The canary closes the final manual acceptance gate retained by GitHub #82 and
  #215. Automation did not create, impersonate or inspect a citizen identity.
- Follow-up live probes found three misleading SSO-page actions: the redundant
  `/el/verify` target returned 404, while the advertised Google and Facebook
  routes returned 403. The QR DiscourseConnect path and email-only discussion
  signup remained operational; the broken actions were removed from the web
  page and static fallback without changing authentication or voting logic.

## 2026-08-23 — DiscourseConnect Restored and Hardened

- The owner-authorized production launcher change restored the three missing
  DiscourseConnect settings without rotating or publishing the existing shared
  secret. The backed-up official rebuild stayed on `v2026.8.0-latest.1` at
  commit `b88e77d`; migrations remain complete, all forum services are running,
  the configured API/forum secrets match, and the `verified-citizens` group is
  present. A protected pre-change config backup and rollback image are retained.
- The public protocol chain now redirects from Discourse to the API and then to
  the Greek verification page. Signature rejection, five-minute nonce TTL,
  local-login fallback, logout-route protection, forum endpoints, bill topics
  and the full monitor pass. No database, DNS, IAM or unrelated application
  setting changed.
- This change additionally limits signed callbacks to the canonical
  `pnyx.ekklesia.gr` Discourse endpoint and atomically consumes each Redis nonce.
  Focused tests cover browser and QR completion, unsafe callback targets,
  malformed payloads, invalid signatures and replay rejection.
- GitHub #82 and #215 retain only the final voluntary real-identity login/logout
  canary. Automation must not create or impersonate a citizen identity to close
  that acceptance step.

## 2026-08-23 — DMARC Observation Gate Catalogued

- The available aggregate report was parsed into a private local catalog. Its
  single message passed DMARC through aligned Brevo DKIM; SPF
  authentication passed but was not aligned, which is expected for that Brevo
  return path. No spoofing evidence was found in the available report.
- The active API, forum and newsletter sending paths use Brevo. A dormant local
  Postfix path has no observed deliveries in the reviewed window. This is an
  inventory result, not authorization to remove legacy DNS entries.
- Enforcement remains blocked until a complete observation window and evidence
  for every active sender path are available. Review may begin on 2026-09-01,
  but no decision may be made until delayed reports covering 2026-08-31 have
  arrived. The intended inbound-mail policy must also be confirmed because the
  domain currently publishes no MX record.
- No DNS record was changed. Linear `NEA-422` remains the tracking authority;
  the public procedure is documented in
  `docs/operations/dmarc-observation-gate.md`.

## 2026-08-23 — Forum Patch and Docker Inventory Reconciled

- Discourse is pinned to `v2026.8.0-latest.1` at upstream commit `b88e77d`.
  The backed-up official rebuild completed successfully, including the launcher-
  managed PostgreSQL 15 to 18 upgrade. Public forum endpoints, Greek locale,
  category/tag access, topic CRUD, bill-topic access, guarded first-post
  ownership and the post-maintenance monitor pass. The rollback image is
  `local_discourse/app:rollback-pre-discourse-patch-20260823T083607Z`.
- The DiscourseConnect regression recorded during this maintenance was restored
  later the same day under the separate owner authorization documented above.
- Docker/containerd issue #211 no longer reproduces after the normal official
  Discourse image pull/build/commit reconciled stale `moby-dangling` metadata.
  Image inventory and size commands pass repeatedly; every active, tagged,
  rollback and dangling image inspected successfully. No prune, image deletion,
  daemon restart or manual metadata repair was performed. The underlying cause
  was not established, so recheck inventory after any future daemon restart.

## 2026-08-13 — Public security audit correction — OPEN

- The reported credential hits were semantically verified as Python test
  function identifiers, not credential literals. No key rotation or history
  rewrite is required from this finding.
- Add a narrow semantic suppression for these identifiers without weakening
  secret detection. Review any public operations metadata separately before
  classifying it as sensitive.
- Do not publish scanner snippets, matched values or infrastructure identifiers
  in this public repository. This entry does not change payment/runtime state.

## 2026-08-12 — Software Policy Separation Confirmed

- The VLABS software no-voluntary-refund policy does not classify Ekklesia
  voluntary support. Its processor refund/dispute handling and recipient,
  tax/document decision remain a separate private VLABS gate.
- Community-support intake remains paused. No collection, fiscal document,
  provider, runtime or Production activation is authorized by this entry.
- Detailed finance records remain only in private `NeaBouli/vlabs`; no
  operational payment or identity values belong in this public Bridge.

## 2026-08-12 — Private Finance Ownership Refreshed

- Detailed recipient, payment, fiscal, provider and reconciliation decisions
  are maintained only in private `NeaBouli/vlabs` at
  `docs/finance-integrations/projects/ekklesia.md`.
- Community-support intake remains paused. This public entry does not authorize
  collection, document issuance or any commercial/runtime activation.
- Keep this public repository limited to generic paused status and the private
  control-center pointer; do not add operational finance or identity data.

## 2026-08-08 — HLR Fix Merged and Parser Backport Tracked (Codex)

- PR #169 was squash-merged to `main` as `080c68e`; main CI and Security Audit
  passed, including Python API, Crypto, all clients, dependency audit and secret
  detection.
- The Greek HLR correction is server-side. No Android source or release
  metadata changed, so no APK/AAB rebuild or Google Play upload is required.
- The local `image-size@1.2.2-pnyx.0` backport remains linked to open Dependabot
  alerts #78–#81 because upstream has no published fixed release. The alerts are
  not dismissed or hidden; the backport is retired only when a maintained,
  Metro-compatible release contains equivalent fixes and passes the complete
  repository CI and Security Audit.
- Owner-approved API-only production rollout completed on 2026-08-08. The
  production checkout fast-forwarded cleanly from
  `c01006408d5f4b52b09d4c83037bc1771bb3071f` to current `main`
  `0da7dbca856fe6aada950bca9dcb34ec988f1e58`; no migration ran and no web,
  mobile, database, DNS, secret, IAM or Google Play change was made.
- The previous immutable API image
  `sha256:c801db36a6573aaaed2f04f72804fca7e2799289fbe831a6692e81b743efbdd3`
  is retained under the convenience tag
  `docker-api:rollback-hlr-c010064-20260808`. The running immutable API image is
  `sha256:d5ae1e32c0efd8644cbc827af094108ff7b7d4c230c08a65286f71c218d64b8c`.
  Verification used `sha256sum packages/crypto/hlr.py` in the server checkout
  and `docker exec ekklesia-api sha256sum /packages/crypto/hlr.py`; both
  returned
  `898f76be312ef3ec38596f6075c820d53f55fe58cc80599e89f4ba73e24c20d6`.
- Pre-switch tests in the built image passed: HLR provider `16/16` and identity
  usage `2/2`. Post-switch verification passed: public `/health`, HLR credits,
  app-version and payment read endpoints return HTTP 200; MOD-01 is `ok`; the
  API container has exit code 0 and restart count 0. All four accepted Greek
  input formats normalize to the same E.164 value. No real phone number or
  paid HLR query was used for verification.
- Separate pre-existing operations findings remain open and were not caused by
  this rollout: MOD-24 forum sync reports two Discourse 422 failures, and
  `docker system df` reports a missing unrelated content blob
  (`sha256:6858a8be...35ca1`). Neither finding affected API/HLR health; no image
  cleanup or destructive Docker repair was attempted.

## 2026-07-16 — Payment Projection Reconciliation Prepared (Codex)

- Codex completed another independent donation-boundary review and prepared retry-safe projection reconciliation for provider captures and later adjustments in PR #136.
- Focused payment/finance tests pass; the public status exposes only minimized aggregate information. Detailed provider, recipient and accounting operations remain exclusively in the private VLABS control center.
- Payment intake and public contribution links remain paused. No payment, refund, invoice/receipt, provider/AADE request, runtime secret change or deployment occurred.

## 2026-07-13 — Docker Capacity Guard Fix Prepared (Codex)

- A production incident exposed a guard logic gap: an extra Docker capacity
  filesystem could be reported critical while a healthy root filesystem caused
  an early exit without safe cache cleanup.
- The fix evaluates root and configured extra paths together. It remains
  limited to logs, apt cache and unused Docker build cache; it never prunes
  images, containers, volumes, backups or application/database data.
- Linux container verification covers extra-path warning, age-filtered normal
  cleanup and critical unfiltered unused-build-cache cleanup; Bash syntax and
  diff checks pass.
- Payment intake and private finance export remain disabled. No payment,
  invoice, receipt, provider/AADE request or finance export occurred.

## 2026-07-13 — Private Finance Export Prepared (Codex)

- Codex prepared a default-off, HMAC-signed exporter from the PII-free Redis
  finance outbox to the private VLABS receiver. This public repository contains
  only generic code and empty environment variable names.
- Donation captures remain distinct from invoices. Provider references are
  hashed before export; queue rows are removed only after an exact receiver ACK.
- HTTPS path pinning, bounded batches, a Redis ownership lock, exact ACK checks,
  retry-safe record IDs and failure retention are covered by focused tests.
  Repeated malformed events are atomically retained in a private dead-letter
  queue after three attempts so they cannot block later valid events.
- CodeRabbit's poison-queue finding was addressed with retry counting, atomic
  quarantine and explicit scheduler observability.
- Verification: 26/26 focused finance/payment tests, real-Redis quarantine/
  recovery and the full API suite (`618 passed, 4 skipped, 25 expected xfail`)
  PASS; compile, diff and public secret/identity scan PASS.
- Payment intake, finance export and public contribution links remain disabled.
  No payment, invoice, receipt, provider/AADE request or deployment occurred.
- Runtime endpoints, secrets, recipient/tax identity and accounting decisions
  remain exclusively in the private VLABS finance files.

## 2026-07-12 — Donation and Client Readiness Merged (Codex)

- Codex hardened the donation boundary and validated all shipped clients in an
  isolated worktree; no deployment or live transaction occurred.
- Ekklesia Stripe/PayPal intake is limited to voluntary donations without
  consideration. HLR provider credits are an operating expense procured
  privately and are not a customer product or accepted payment purpose.
- Customer identity and payer hashes are removed from new payment records;
  legacy rows are projected through an explicit PII-free admin schema.
- Signed capture/refund/dispute events are prepared for the private VLABS
  finance handoff. Public donation links and runtime intake remain paused.
- Web, Dashboard, Mobile, Representative, shared crypto and focused API/agent
  checks are green. Both Expo Android exports complete successfully.
- Full public verification matrix: `docs/SOFTWARE_READINESS_2026-07-12.md`.
- PR #131 was squash-merged to `main` as `a99a12b`; all required GitHub
  checks passed. The automated CodeRabbit review was rate-limited, so the
  change also received a local self-review before merge.
- Remaining gates require private runtime configuration, legal/accounting
  confirmation, sandbox E2E approval and controlled deployment.
- Detailed provider, tax and document decisions remain only in private VLABS.

## Public Payment Data Boundary

- This repository is public. Operational payment, donation-classification and Etimologio information is stored only in private `NeaBouli/vlabs` at `docs/finance-integrations/projects/ekklesia.md`.
- Never publish legal-recipient identity, tax/personal identifiers, wallet ownership, secrets, provider/account IDs, donor/customer/invoice data, MARK/UID values or runtime values here.
- Public Bridge entries are limited to the private reference, ownership, generic status and production-disabled/paused state.

## 2026-07-11 — Payment PR Merged (Codex)

- Payment/funding PR #128 was squash-merged to `main` as `34881c7`.
- Codex remains owner of Stripe, PayPal, crypto-accounting boundaries and private VLABS Etimologio handoff; the Core-Dev owns non-payment product work.
- Public contribution links remain paused. No deployment, payment, invoice, provider or AADE request occurred. Legal recipient and tax/document classification remain Gio/Accountant gates.

## 2026-07-11 — Payment/Etimologio Ownership and Safety (Codex)

- Codex owns Stripe, PayPal, crypto-payment accounting boundaries and the
  private VLABS Etimologio handoff. Non-payment Pnyx product work remains with
  the project Core-Dev.
- Public contribution links are paused until Gio/Accountant confirms the legal
  recipient, legal form, tax treatment, document policy and whether each flow
  is a donation, support income or sale.
- Important classification: `15 EUR = 2500 HLR Credits` is Ekklesia's private
  provider procurement expense, not an incoming community payment. The former
  public HLR payment purpose has been removed.
- Webhooks now require the explicit `PAYMENTS_INTAKE_GATE`, verified provider
  signature/IPN, EUR, bounded positive amount and explicit payment purpose.
- Stripe additionally requires paid `payment` Checkout mode. PayPal additionally
  binds receiver email and/or merchant ID and uses atomic transaction claiming.
- Failed persistence after accounting mutation is held for manual review instead
  of deleting idempotency state and risking duplicate allocation.
- Public status continues to redact donor identity and processor IDs.
- Focused verification: 9 payment safety tests PASS; Python compile PASS.
- No live payment, refund, invoice, AADE/provider request, runtime secret,
  deployment or public payment reactivation.

### External gates

1. Gio/Accountant: identify the legal recipient and approve donation versus
   taxable support/service/product treatment per flow.
2. Configure donation-only Stripe/PayPal flows with explicit voluntary-support
   purpose metadata; never infer HLR provider procurement from donor amounts.
3. Decide invoice/receipt, VAT/myDATA and refund treatment, then connect the
   private VLABS finance ingest.
4. Run Stripe and PayPal sandbox/test E2E before restoring public links.

## 2026-09-06 - Task Block 1-9 Follow-up (Append-only)

- Continued from main `76611ea`; no restart of completed release work.
- Sol owns integration, external verification and release gates. Kimi owns the
  bounded mobile unread-event ledger patch; Sol reviews the implementation and
  independently tests runtime notification wiring and storage failures.
- Live v1.0.32 remains unchanged. Google review and tester qualification are
  external gates. F-Droid v1.0.31 ABI builds succeed but the public package API
  still exposes v1.0.29 at inspection.
- Newsletter/evaluation overlay was built and tested, not deployed: protected
  configuration drift stopped the switch. Private details remain only in the
  ignored operator bridge. Full source API suite: 1,008 passed, 11 skipped,
  25 expected failures, four subtests passed; no production DB used.
- Newsletter no-write readiness has no eligible entries. No additional mail,
  contact writes, consent inference or identity impersonation. Existing
  GitHub #261/#253 and Linear mail/F-Droid records received evidence updates.
- Security alerts remain visible. No forced dependency major, peer override,
  CI weakening, payment activation or production change.
- Current evidence and remaining gates:
  `docs/operations/RELEASE_GATES_2026-09-06.md`.
- Task 10 remains excluded pending the private VLABS operator's inputs.

### 2026-09-07 - Final Source Verification

- Mobile: 258 tests in 28 files passed, plus seven image-size and four
  decode-uri-component installed-package regressions. Typecheck passed;
  staged mobile diff secret scan found no leaks. No dedicated mobile lint
  script exists. No security timeout, rule or dependency contract was changed.
- Kimi's final review findings were addressed by Sol and retested. Android
  device/OEM acceptance remains pending; source verification is not a release.
- The reported website outage could not be reproduced during live checks:
  landing and API health returned HTTP 200, and the operator confirmed
  recovery. No service was restarted or production configuration changed.

### 2026-09-07 - Continued GH290 Verification

- PR #297 initial head 1474195 passed all CI/Security jobs. Continuation
  addresses Kimi's storage-size portability finding and cold-start taps.
- Sol's two-bank bounded unread-storage adapter preserves the prior committed
  value on interrupted writes; Kimi added 34 tests and Sol reviewed them.
  Full mobile verification: 293 tests, eleven dependency regressions and
  TypeScript passed. No identity, signing, dependency or version changes.
- S10 intermittently readable, Android 12 and installed v1.0.31 / 60. USB
  transport failures prevent reliable device acceptance. No app installation
  or data deletion performed. Private evidence remains in the ignored bridge.
- F-Droid catalog still v1.0.29 / 584; five Dependabot alerts remain open.
  API protected-configuration, consent/evidence and external review gates
  are unchanged. No production rollout or task-10 work occurred.

### 2026-09-07 - USB Recovery and PR297 Review Follow-up

- Earlier CI evidence retained: main `76611ea` passed
  [CI](https://github.com/NeaBouli/pnyx/actions/runs/34026554854) and
  [Security](https://github.com/NeaBouli/pnyx/actions/runs/34026554855);
  PR head `1474195` passed
  [CI](https://github.com/NeaBouli/pnyx/actions/runs/34060126361) and
  [Security](https://github.com/NeaBouli/pnyx/actions/runs/34060126388).
  Head `9dc98f4` also passed both workflows (34061601994/34061601989).
- CodeRabbit completed with comments, not an approval. Kimi independently
  confirmed unread-storage error handling and settings hydration/retry gaps.
  Corrupt unread manifests remain fail-closed; automatic replacement would
  risk discarding prior acknowledgements and is intentionally not applied.
- USB resumed working. Read-only S10 smoke checks reached home, profile,
  notification settings, bill filters, parties and trending. Complete local
  screenshots succeeded. Installed app remains v1.0.31 / 60, not the PR code.
  No data clearing, app replacement, identity changes or real votes occurred.
- Side finding: the installed update banner overlaps the Android status bar;
  current source lacks a top safe-area inset. Keep this as an explicit mobile
  release follow-up, not a claim that all layouts passed. New-build hardware
  acceptance and full automatic event-producer coverage remain open.
- Sol reviewed Kimi's screen/test changes and added recovery across screen
  unmount/remount plus an in-flight toggle guard. Opt-outs remain persisted
  when acknowledgement fails; a bounded retry and explicit retry control
  replace silent failures. Invalid manifests are never reset automatically.
- Final local tests: 308 mobile tests in 30 files, seven image-size and four
  decode-uri-component regressions, TypeScript, diff check and changed-file
  secret scans passed. The screen tests execute real transpiled component
  logic with stubbed hooks/native modules, not an OEM UI renderer. No mobile
  lint script exists. Hardware checks above concern installed code 60 only.
- Direct and F-Droid Android exports passed (1,179 modules each). These are
  bundle checks, not newly signed APK/AAB releases or F-Droid publication.

### 2026-09-07 - Settings Recovery and Signed S10 Acceptance

- The follow-up CodeRabbit finding was valid: a persistent unread-ledger
  failure locked all preference switches. Pending acknowledgements no longer
  lock preferences; retries derive their scope from the currently persisted
  policy, not an obsolete pre-reenable scope. Kimi independently reviewed
  the changes and passed thirteen focused tests plus TypeScript; Sol reran
  all311 mobile tests and all eleven installed security regressions.
- Top system insets are consumed once before inline banners. Signed Direct
  release builds and Android lint passed. A local-only code60 test variant
  exposed the real code61 update banner without changing public version
  metadata. In-place S10 installation succeeded with matching certificate;
  existing verified state survived without uninstall or data clearing.
- On S10/Android12, the banner no longer overlaps the status bar. At font
  scales1.0,1.3 and1.8 it remains readable; at1.8 its action wraps and the
  close control remains reachable. Dismissal and settings navigation work.
  Master/category preferences persist through cold restart and were restored
  to their original values. Bill filters, Trending, parties and POLIS render;
  empty states are not evidence of complete upstream data.
- The device was returned to the unchanged official v1.0.32/code61 APK with
  original installation date and verified state retained; font scale restored
  to1.0. No temporary test binary was published. Final F-Droid Android export
  passed (1,179 modules); no new F-Droid build/catalog publication is implied.
- Side finding: pre-existing custom bottom-tab labels clip at font scale1.8.
  Track a focused accessibility follow-up; do not claim all-screen acceptance.
  Automatic event-producer coverage, Xiaomi/emulator acceptance and protected
  API rollout gates remain open. GH290 is not complete. No production,
  payment, HLR request, vote, message or security-suppression change occurred.

## 2026-09-19 - EKA Audit and Redesign Intake (Append-only)

- Started from clean `origin/main` at
  `6a8ed73a04e029d8d8d6525c0ccdd31f487ec684` in the isolated branch
  `docs/audit-redesign-catalog-20260919`; active fix branches were not touched.
- Reconciled the merged EKA audit reports, consolidated PDF, issue #318 and the
  helper handoff. The audit remains 64 findings: 0 Critical, 1 High, 21 Medium,
  27 Low and 15 Informational. No unchecked finding was marked fixed.
- Independently verified PR #319 as the green EKA-02 candidate and PR #320 as
  the green EKA-32 candidate. #319 has a completed CodeRabbit review with no
  actionable comments. #320 has green CI/Security but CodeRabbit was
  rate-limited, so independent review remains a gate. No merge occurred.
- Verified that GitHub Actions is not currently quota-blocked: the latest
  sampled 30 runs were successful, with no queued, in-progress or failed run.
  The observed review warning is CodeRabbit-specific.
- Imported the supplied redesign handoff unchanged to
  `design/handoffs/ekklesia-redesign-2026-09-16/source/`, outside the public
  `docs/` web root. Archive SHA-256:
  `8e41f707ba410cfd2f982ebdb68b31dfc78fafe0c40283a3b373780ba498c742`.
  The prototype remains reference-only and is not production code.
- Catalogued every EKA ID exactly once, defined bounded task ownership and
  froze the redesign behind canonical-content, CSP/privacy, release-fact,
  accessibility and parity gates in
  `docs/planning/EKA_REMEDIATION_AND_REDESIGN_PLAN_2026-09-19.md`.
- Execution mode is bounded task blocks with target stop. Kimi receives only a
  disjoint review after its announced quota reset; no repeated quota polling or
  duplicate analysis is permitted.
- No application code, public page, database, DNS, secret, IAM, provider,
  production service, store listing or deployment was changed.

## 2026-09-19 - Complete Project Status Checkpoint (Append-only)

- Added the authoritative public checkpoint
  `docs/reports/EKKLESIA_MASTER_PROJECT_STATUS_2026-09-19.md`. It inventories
  the live V1 baseline, release channels, data-quality work, Mobile, Web,
  Dashboard, Forum/SSO, mail, AI, dependency security, all 64 EKA findings,
  all 18 open pull requests, all 17 open issues, the redesign and future gated
  programs.
- Fresh public probes returned HTTP 200 for the landing page, bills, results,
  community, wiki, roadmap, legal page, API health, dashboard login, forum and
  technical mirror. All three public mirrors were online. The API reported
  `1.0.32` / version code `61` with no forced update.
- Reconciled current distribution facts: GitHub Direct APK/AAB v1.0.32 remain
  checksum-verified; Google Play Closed Testing is active but its 12-tester and
  14-day production gate is incomplete; F-Droid publicly offers v1.0.32 ABI
  builds 611-614 with 614 suggested. Greek F-Droid presentation remains open.
- The EKA register remains 64 findings: 0 Critical, 1 High, 21 Medium, 27 Low
  and 15 Informational. PR #319 and PR #320 remain candidates, not completed
  remediation. No finding was closed by writing the checkpoint.
- Five Dependabot alerts remain visible and externally gated where no safe
  compatible patch exists. GitHub Actions is healthy; the earlier allowance
  warning was CodeRabbit-specific.
- Sensitive Play, tracker and finance/operator evidence is retained only in the
  local gitignored supplement
  `docs/agent-bridge/EKKLESIA_MASTER_PROJECT_STATUS_PRIVATE_2026-09-19.md`.
- This was a documentation-only checkpoint. No application code, merge,
  deployment, database, DNS, secret, IAM, provider, payment, store or production
  mutation occurred.

## 2026-09-19 - EKA-02 Closure and EKA-32 Integration Delta (Append-only)

- EKA-02: PR #319 merged normally as `a375d2d`; post-merge CI/Security passed.
  The separately authorized bounded Representative Web overlay and live
  hostile-payload acceptance passed, and issue #318 now marks EKA-02 closed.
- EKA-32: PR #320 merged normally as `942e063`. CodeRabbit's two valid findings
  were fixed in `3e763ed`: forwarded client addresses are accepted only from
  configured trusted proxy CIDRs, and documentation now distinguishes shared
  Redis coordination from bounded per-process memory fallback.
- EKA-32 verification: focused Redis path `27 passed`; full local API suite
  `1019 passed, 2 skipped, 25 xfailed`; diff/compile/scoped-secret checks passed.
  All PR checks and post-merge main CI run `35460470030` plus Security run
  `35460470044` passed.
- Kimi's fresh final review attempt was blocked by its external 5-hour quota and
  changed no files. The final delta received the documented Claude/Sol fallback
  review; CodeRabbit's resolved threads provide the original finding evidence.
- No EKA-32 API rollout or other production, database, DNS, secret, IAM,
  provider, payment or store mutation occurred. EKA-32 remains open in #318
  until separately authorized live acceptance.

## 2026-09-19 - EKA-04 Newsletter Abuse Protection Integration (Append-only)

- PR #325 merged normally as `760845a` without admin bypass. The bounded change
  adds fixed-window limits of 10 attempted DOI emails per source IP/hour and
  three per normalized email/day before token storage or provider calls.
- Rate-limit keys and successful subscription logs use opaque HMAC-derived
  references; plaintext subscriber email addresses are no longer written by
  the successful subscribe path. Validation, confirmed-subscriber behavior,
  double opt-in, pending-token payloads and Reply-To policy remain unchanged.
- Verification passed: focused tests `85 passed, 5 skipped`; an isolated real
  Redis run `17 passed`; the full API suite `1044 passed, 4 skipped, 25 xfailed,
  4 subtests passed`; diff, compile and gitleaks checks also passed.
- Kimi implemented the bounded change under Sol review. Claude and CodeRabbit
  independently reported no blocking or actionable finding. Post-merge main CI
  run `35468720523` and Security run `35468720502` passed completely.
- Evidence is recorded in issue #318 and PR #325. No API rollout, real email,
  database, DNS, secret, IAM, provider, payment or store mutation occurred.
  EKA-04 remains open until a separately authorized API rollout and live
  acceptance verify the production behavior.

## 2026-09-19 - EKA-03 Nullifier Action Proof Integration (Append-only)

- PR #326 merged normally as `5f850e2` without admin bypass. Bill flags now
  require an ACTIVE-identity Ed25519 proof over a domain-separated,
  timestamp-bound payload; vote-status reads have an equivalent signed POST
  contract without URL nullifiers, mirror fallback or unsigned mobile fallback.
- The released Android v1.0.32 legacy GET contract remains available behind the
  reversible `VOTE_STATUS_REQUIRE_SIGNED` gate. Unset and explicit false values
  preserve compatibility; invalid non-empty values log an operator error and
  fail closed by requiring signed reads.
- CodeRabbit's three actionable findings were fixed in `bc85e0a`: only
  PostgreSQL unique-violation SQLSTATE `23505` maps to duplicate-flag HTTP 409,
  invalid cutoff values fail closed, and a vote-status read failure no longer
  prevents subsequent ZK initialization. All review threads are resolved.
- Verification passed: focused review-fix API/CORS tests `88 passed`; full API
  suite `1128 passed, 4 skipped, 25 xfailed, 4 subtests passed`; Mobile `322`
  tests; dependency security regressions `7 + 4`; TypeScript, Expo dependency,
  compile, diff and staged gitleaks checks passed.
- All PR gates passed. Post-merge main CI run `35474984491` and Security run
  `35474984508` passed completely on merge commit `5f850e2`.
- Kimi implemented the bounded source change under Sol review. Its final
  follow-up and Claude's follow-up were externally quota-limited after the
  CodeRabbit fixes; the final delta received the documented Sol review. No
  agent limitation weakened CI or review-thread requirements.
- Evidence is recorded in issue #318 and PR #326. No API rollout, Android
  build/release, database, DNS, secret, IAM, provider, payment, store or other
  production mutation occurred. EKA-03 remains open until the separately
  authorized API rollout, compatible Android release/adoption, cutoff and live
  acceptance sequence completes.

## 2026-09-20 - EKA-05 Push Registration Authentication Integration (Append-only)

- PR #327 merged normally as `9f52c95` without admin bypass. Push registration
  now requires a fresh domain-separated Ed25519 proof from an ACTIVE identity;
  the unauthenticated server fallback was removed.
- Mobile uses a cryptographically random per-install UUIDv4 and signs the exact
  canonical registration payload. The local refresh marker is bound to the
  identity material and cleared with the keys. F-Droid remains free of native
  push registration requirements.
- Server storage uses stable HMAC-derived Redis keys, a 90-day TTL and bounded
  IP/identity limits. Same-value refreshes do not consume identity quota, and
  sends deduplicate legacy plus signed token entries during the transition.
- CodeRabbit's two valid findings were fixed in `d7f15d4`: `timestamp_ms` now
  rejects coerced JSON strings, and token validation rejects trailing data via
  full matching. Both threads are resolved. Claude reported no blocker; Kimi
  implemented the bounded subsystem under Sol review.
- Verification passed: focused API registration tests `48 passed`; full API
  suite `1174 passed, 4 skipped, 25 xfailed, 4 subtests passed`; Mobile `336`
  tests; dependency security regressions `7 + 4`; TypeScript, Expo dependency,
  YAML security, npm audit, compile, diff and gitleaks checks passed.
- All PR gates passed. Post-merge main CI run `35499471240` and Security run
  `35499471252` passed completely on merge commit `9f52c95`.
- Evidence is recorded in issue #318 and PR #327. No API rollout, Mobile
  build/release, database, DNS, secret, IAM, provider, payment, store or other
  production mutation occurred. EKA-05 remains open until the separately
  authorized API rollout, compatible Mobile release/adoption and live
  acceptance sequence completes.

## 2026-09-20 - EKA-06 HLR Cost Protection Integration (Append-only)

- PR #328 merged normally as `0ce4b31` without admin bypass. Invalid Greek
  mobile formats are rejected locally before Redis or a paid provider call.
  Valid attempts are bounded by per-IP minute/day and HMAC-number cooldown/day
  limits, with all four checks and mutations performed atomically in one Redis
  Lua transaction. Redis failure blocks the paid lookup.
- The public HLR status now exposes only coarse availability states. Exact
  balances, usage, provider labels, costs and failover reason remain available
  only through the existing authenticated admin route and dashboard proxy.
- CodeRabbit identified two valid findings: IP-rejected attempts could consume
  number quota, and Finance used two stale response fields. Commit `8c8f8e2`
  made the Redis operation atomic, added the no-partial-mutation regression and
  aligned Finance with `initial` and `cost_per_query_eur`. Kimi reviewed the
  bounded change under Sol integration control.
- Verification passed: focused API tests `67 passed`; dashboard typecheck and
  production build; Python compile and diff checks. All PR checks passed.
  Post-merge main CI run `35503903428` and Security run `35503903422` passed
  completely on merge commit `0ce4b31`.
- Evidence is recorded in issue #318 and PR #328. No API/dashboard rollout,
  paid HLR lookup, database, DNS, secret, IAM, provider, payment, store or other
  production mutation occurred. EKA-06 remains open until a separately
  authorized bounded rollout and live acceptance complete.

## 2026-09-20 - EKA-09 Brevo Webhook Authentication Integration (Append-only)

- PR #329 merged normally as `1a49d47` without admin bypass. The Brevo event
  webhook now requires a dedicated bearer credential before request-body
  parsing or Redis access. Missing runtime configuration fails closed with
  503; missing, malformed or wrong credentials return 401 with zero Redis
  mutations.
- Accepted single and batched event semantics remain unchanged. Post-auth
  processing failures return a fixed public error instead of internal
  exception details. Token material is never logged or returned.
- Verification passed: focused tests `19 passed`; newsletter/webhook sweep
  `126 passed, 5 skipped`; Python compile, diff and staged Gitleaks checks.
  CodeRabbit produced no actionable finding. All PR checks passed. Post-merge
  main CI run `35506581566` and Security run `35506581521` passed completely.
- Evidence is recorded in issue #318 and PR #329. No API rollout, Brevo
  configuration, secret, provider, database, DNS, IAM, payment, store or other
  production mutation occurred. EKA-09 remains open until matching out-of-band
  API/Brevo token configuration, a separately authorized bounded API rollout
  and live acceptance complete.

## 2026-09-20 - EKA-16 Application-Log Privacy Integration (Append-only)

- PR #330 merged normally as `641721d` without admin bypass. Contact success
  logs no longer contain name or organisation, and Brevo/Listmonk failure logs
  no longer include response bodies that can echo submitted personal data.
- Existing privacy-safe `ipref` and `emailref` correlation and provider status
  codes remain. Outbound delivery payloads, consent, rate limits and public
  error contracts are unchanged.
- Seven sentinel-PII regressions and the focused privacy/newsletter sweep passed
  (`115 passed, 5 skipped`). The complete local API suite passed 1,208 tests;
  only the three known localhost-Redis cases failed locally. GitHub's
  Redis-backed API job and all other PR checks passed.
- Kimi implemented the bounded patch under Sol review. A fresh Kimi fallback
  security review approved it; both low test-quality notes were fixed before
  commit. Claude was externally token-limited. CodeRabbit was rate-limited and
  produced no finding; no required gate was bypassed.
- Post-merge main CI run `35509282967` and Security run `35509283003` passed
  completely. Evidence is recorded in PR #330 and issue #318.
- No API rollout, real contact/newsletter send, provider, secret, database, DNS,
  IAM, payment, store or other production mutation occurred. EKA-16 remains
  open until a separately authorized bounded API rollout and live log
  acceptance complete.

## 2026-09-20 - EKA-17 HLR Credential-Name Integration (Append-only)

- PR #331 merged normally as `c18b75f` without admin bypass. The primary
  hlrlookup.com provider now prefers a complete canonical `HLRLOOKUP_*` pair;
  the historical complete `HLR_FALLBACK_*` pair remains a deprecated alias for
  that same primary provider only. The actual hlr-lookups.com fallback remains
  isolated on `HLRLOOKUPS_*`.
- Partial canonical or legacy pairs fail closed, credentials are never mixed
  across naming schemes, and secret values are not logged. Provider routing,
  payload, billing, rate-limit and failover behavior did not change.
- Kimi performed the bounded implementation and an independent review under Sol
  control. Sol resolved every concrete review comment. CodeRabbit's valid
  configuration-inventory finding was fixed before merge; its second pass was
  externally rate-limited without weakening any required gate.
- Local verification: HLR `36 passed`, complete Crypto `48 passed`, affected
  API `88 passed, 1 xfailed`, full redacted Gitleaks scan clean. Post-merge main
  CI `35512008384` and Security `35512008302` passed completely.
- Public evidence: PR #331 and issue #318 comment
  `https://github.com/NeaBouli/pnyx/issues/318#issuecomment-5749951203`.
- No production environment, secret, provider, deployment, database, DNS, IAM,
  payment or store mutation occurred. EKA-17 remains open until a separately
  authorized environment migration and live acceptance.

## 2026-09-20 - R2 Landing Redesign Source Validation (Append-only)

- R2 is implemented on branch `feat/redesign-r2-landing-20260920` from base
  `8f3148cd95ea8381dee336c620166e0adb8e67a6`. The scope is limited to
  `docs/index.html`, local `docs/assets/redesign-v2/` CSS and the R2 validation
  harness; the other 34 allowlisted public HTML pages remain byte-identical to
  the frozen R0 baseline.
- Existing landing copy, link destinations, bilingual pairs, forms, API
  contracts, storage calls, metadata, JSON-LD, event handlers and scripts are
  preserved. The only semantic addition is a bilingual skip link plus `main`
  target; no new external host or CDN dependency was introduced.
- The R2 visual layer applies the approved visible-grid direction with square
  corners, no shadows or gradients, local tokens, explicit section dividers,
  left-aligned hierarchy, responsive controls and the dark footer. It does not
  implement an editorial rewrite or later-page redesign phase.
- Validation passed: parser-backed R2 gate; 73 redesign tests; R1 foundation
  check; diff check; full redacted Gitleaks scan. Headless Chrome passed at
  1440 x 1000 and 360 x 800 with no document horizontal overflow, working
  EL/EN toggle, 44 px visible form/control targets and viewport-contained chat
  and legal panels.
- Local preview API calls were CORS-blocked from the `127.0.0.1` origin as
  expected; no API contract changed and this is not production acceptance.
- Claude Code produced the initial bounded implementation and then became
  `token_limited`. Sol reviewed and completed the validator, responsive fix,
  visual verification and integration preparation. No duplicate implementation
  was performed.
- CodeRabbit's three valid findings were fixed before merge: semantic `main`,
  live parser-backed structure checks, and complete external-import/viewport-
  font negative coverage. The follow-up test total is included above.
- Evidence: `docs/planning/r2/R2_REPORT.md`. No production deploy, server,
  database, DNS, IAM, secret, provider, payment, mobile-store or other runtime
  mutation occurred. R2 remains source-only until protected-branch integration
  and a separately authorized production rollout.

## 2026-09-20 - R3 Wiki-Shell Pilot Source Validation (Append-only)

- R3 pilot scope is limited to `docs/wiki/index.html`, the local
  `docs/assets/redesign-v2/r3-wiki.css` layer and the parser-backed validation
  harness. The other 13 wiki pages and every non-wiki public page remain
  outside this task.
- Existing text, bilingual pairs, links, metadata, analytics, scripts, event
  handlers and inline styles are preserved. The only accepted semantic change
  is a bilingual skip link plus its `main` target; no external asset or host
  was added.
- Validation passed before integration: parser-backed R3 gate; 94 redesign
  tests; R1 foundation check; local resolution of all 17 static pilot links;
  Python compile; diff check; full redacted Gitleaks scan; desktop 1440 x 1000
  and mobile 360 x 800 browser verification.
  Both viewports had no document overflow, no visible control below 44 px,
  working EL/EN switching and a contained legal modal. Normal wheel scrolling
  activated all eight deferred sections without clipping.
- Claude Code was externally token-limited before changing files. Kimi fallback
  was also externally token-limited. Sol performed the bounded implementation,
  review and verification; no duplicate delegated implementation occurred.
- Evidence: `docs/planning/r3/R3_PILOT_REPORT.md`. No production deploy,
  server, database, DNS, IAM, secret, provider, payment, mobile-store or other
  runtime mutation occurred. Full R3 remains open until the pilot passes
  protected integration and the remaining 13 wiki pages complete their own
  bounded parity gates.
