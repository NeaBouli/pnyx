# Pnyx / ekklesia.gr Bridge

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
