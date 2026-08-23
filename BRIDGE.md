# Pnyx / ekklesia.gr Bridge

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
