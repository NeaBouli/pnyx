# EKA remediation and redesign intake plan - 2026-09-19

Status: `CATALOG_ONLY`

No audit fix, redesign implementation, merge, deployment, database change or
provider change is authorized by this document. It records the verified state
and prepares bounded work packages for an explicit later start.

## Baseline and sources

- Repository baseline: `origin/main` at `6a8ed73a04e029d8d8d6525c0ccdd31f487ec684`.
- The complete EKA audit series is merged in PR
  [#317](https://github.com/NeaBouli/pnyx/pull/317) and pinned under
  `docs/community-audits/`.
- The authoritative finding register is issue
  [#318](https://github.com/NeaBouli/pnyx/issues/318). Its EKA-01..64 boxes
  remain evidence-gated. EKA-02 is closed; EKA-32, EKA-04, EKA-03, EKA-05,
  EKA-06 and EKA-09 are integrated but remain open until their separately
  authorized rollout, client-adoption where applicable, provider configuration
  where applicable and live-acceptance evidence is complete.
- The consolidated 29-page PDF was checked for completeness and visually
  rendered during intake. The repository Markdown reports remain the source
  for ticket-level evidence and line references.
- The helper report was treated as a lead, not authority. Its claims about
  PRs #317, #319 and #320 were independently checked against GitHub.
- The redesign archive is preserved unchanged under
  `design/handoffs/ekklesia-redesign-2026-09-16/source/`. Its import record
  contains the source hash and explicit non-production status.

Audit totals: **64 findings - 0 Critical, 1 High, 21 Medium, 27 Low and
15 Informational**.

## CI and review capacity

GitHub Actions is not currently blocked by a run quota:

- on 2026-09-19 the latest 30 repository runs were completed successfully;
- no run was queued, in progress or failed in that sample;
- PRs #319, #320, #325, #326 and #327 merged normally with green post-merge CI
  and Security Audit. PRs #328 and #329 subsequently merged with the same green
  post-merge gates; maintenance PRs #321 and #322 retain green candidate checks.

The warning seen during PR #320 was a **CodeRabbit included-review limit**, not
a GitHub Actions limit. CodeRabbit's completed review identified two valid
findings; both were fixed in `3e763ed` and both threads are resolved. A fresh
Kimi final pass remained externally quota-limited, so the final delta received
the documented Claude/Sol fallback review before normal merge.

PR #326 later received three actionable CodeRabbit findings. All were fixed in
`bc85e0a`, all review threads were resolved and the candidate plus post-merge
checks passed. Kimi and Claude follow-up invocations were externally
quota-limited, so Sol performed the documented final-delta review without
duplicating implementation.

PR #327 received two actionable CodeRabbit findings. Strict integer validation
and full-token matching were fixed in `d7f15d4`; both review threads were
resolved. Kimi implemented the bounded subsystem under Sol review, Claude found
no blocker, and focused, full API, Mobile, security plus post-merge checks all
passed.

If an Actions quota becomes constrained later:

1. do not rerun unchanged successful jobs;
2. validate locally before the first push;
3. keep one behavior change per PR and push only reviewed revisions;
4. batch compatible dependency maintenance rather than opening duplicate runs;
5. reserve full matrix runs for candidate heads and post-merge verification;
6. never weaken or skip required CI to conserve minutes.

## Token-efficient execution policy

The project should not use a broad, open-ended autonomous goal for this
remediation. Work proceeds as bounded task blocks:

1. exactly one package is `in_progress`;
2. the package names files, acceptance criteria and required tests before work;
3. Kimi receives a disjoint analysis, implementation or review scope and does
   not repeat Sol's work;
4. focused tests run during development; the full affected matrix runs once at
   the integration gate;
5. evidence is appended to the bridge once, not rediscovered every turn;
6. target stop activates as soon as the package definition of done is met.

This workflow reduces repeated repository scans and duplicate test runs. Model
reasoning settings do not provide a reliable per-task token cap; an explicit
block and, when desired, an explicit token budget are the reliable controls.

## Relevant security and maintenance pull requests

| PR | Scope | Verified state | Gate |
|---|---|---|---|
| #317 | Audit publication, EKA-01..64 | Merged as `6a8ed73`; checks green | Complete |
| #319 | EKA-02 representative WebView stored-XSS | Merged as `a375d2d`; post-merge checks and bounded live acceptance green | Complete; EKA-02 closed in #318 |
| #320 | EKA-32 global rate-limit middleware | Merged as `942e063`; review findings fixed; local/hosted verification green | Integration complete; production rollout/live acceptance remain separate |
| #325 | EKA-04 newsletter abuse protection | Merged as `760845a`; focused, real-Redis, full API, review and post-merge checks green | Integration complete; production rollout/live acceptance remain separate |
| #326 | EKA-03 nullifier-bound action proofs | Merged as `5f850e2`; full API/mobile/security verification, resolved review threads and post-merge checks green | Integration complete; API rollout, Android adoption, cutoff and live acceptance remain separate |
| #327 | EKA-05 authenticated push registration | Merged as `9f52c95`; full API/mobile/security verification, resolved review threads and post-merge checks green | Integration complete; API rollout, compatible Mobile release/adoption and live acceptance remain separate |
| #328 | EKA-06 HLR cost and public-status protection | Merged as `0ce4b31`; atomic-limit regression, dashboard build and all PR/main checks green | Integration complete; bounded API/dashboard rollout and live acceptance remain separate |
| #329 | EKA-09 Brevo webhook authentication | Merged as `1a49d47`; focused and newsletter/webhook tests, review and all PR/main checks green | Integration complete; matching out-of-band API/Brevo configuration, bounded API rollout and live acceptance remain separate |
| #330 | EKA-16 application-log privacy | Merged as `641721d`; sentinel-PII regressions, focused suite, review and all PR/main checks green | Integration complete; bounded API rollout and live log acceptance remain separate |
| #331 | EKA-17 HLR credential environment names | Merged as `c18b75f`; pair-isolation regressions, independent review and all PR/main checks green | Integration complete; production environment migration and live acceptance remain separate |
| #321 | Alembic 1.20.0 dependency update | Open, clean, checks green | Independent dependency maintenance; do not mix with EKA fixes |
| #322 | sentry-sdk 2.69.1 dependency update | Open, clean, checks green | Independent dependency maintenance; do not mix with EKA fixes |

The catalog intake itself merged or deployed nothing. The #319, #320, #325,
#326, #327, #328, #329, #330 and #331 rows record later bounded task blocks;
#320, #325, #326, #327, #328, #329, #330 and #331 have not been deployed.

## Remediation packages

Every audit ID has exactly one primary package. Cross-links may exist, but work
must not be duplicated across packages.

| Package | Findings | Scope and exit gate | Risk / dependency |
|---|---|---|---|
| A - Representative XSS | EKA-02 | Complete: #319 merged, bounded Web rollout accepted, #318 updated. | High package closed with source, integration and live evidence. |
| B - Global rate limiting | EKA-32 | Integration complete: #320 proves middleware order, 429 CORS, test isolation, Redis/fallback behavior and trusted-proxy semantics. Production rollout remains separate. | Medium/high blast radius; live evidence still required. |
| C - Auxiliary endpoint abuse and privacy | EKA-03, EKA-04, EKA-05, EKA-06, EKA-09, EKA-16, EKA-17, EKA-53 | EKA-04 source integration is complete in #325. EKA-03 is integrated in #326 with a compatibility-gated unsigned-read retirement path. EKA-05 is integrated in #327 with signed identity-bound registration and random per-install device IDs. EKA-06 is integrated in #328 with atomic HLR limits and a coarse public status contract. EKA-09 is integrated in #329 with fail-closed Brevo webhook authentication. EKA-16 is integrated in #330 with PII/provider-body log redaction and sentinel regressions. EKA-17 is integrated in #331 with canonical/legacy credential-pair isolation and fail-closed partial configuration. Their rollout/live gates and the remaining admin-status finding stay separate. | Depends on B's global baseline and existing client compatibility. HLR/provider writes remain forbidden. |
| D - Vote and dormant-auth correctness | EKA-01, EKA-10, EKA-11, EKA-12 | Restore Tier-1 validation, convert municipal races to deterministic conflict handling, define dormant gov.gr state storage before activation, narrow signature exceptions. | Security-sensitive; no governance semantics change. |
| E - Client keys and nullifier KDF | EKA-07, EKA-08, EKA-21, EKA-22, EKA-23, EKA-24 | Publish canonical formats and known-answer tests first; then plan backward-compatible key-storage and KDF migration. Record the accepted phone-entropy residual risk explicitly. | High crypto/identity risk; requires Kimi plus strengthened Sol review before code. No identity reset. |
| F - Runtime and integration surface | EKA-13, EKA-18, EKA-19, EKA-26, EKA-27, EKA-28, EKA-29, EKA-30, EKA-31 | Reverify inventory, dependency backlog, container/user/tag posture, subdomain ownership, admin exposure, package IDs and CSP. Record the verified-wiring evidence separately. | Read-only inventory first. DNS, containers, IAM and production need separate authorization. |
| G - Residual browser sinks | EKA-14, EKA-15 | Replace remaining remote-data HTML sinks with safe DOM construction and remove dead admin-query helpers with focused browser regressions. | Must precede broad redesign migration. |
| H - Canonical privacy and ownership claims | EKA-25, EKA-33, EKA-34, EKA-35, EKA-36, EKA-45, EKA-47, EKA-54, EKA-55 | Approve one bilingual canonical fact set for analytics, compass, vote visibility, Arweave, retention, translations, operator/entity language and community ownership. | Content/legal accuracy gate; must finish before redesign text freeze. |
| I - Public documentation and release facts | EKA-37, EKA-38, EKA-39, EKA-40, EKA-41, EKA-42, EKA-43, EKA-44, EKA-46, EKA-48, EKA-49, EKA-50, EKA-51, EKA-52 | Correct API examples, distribution status, cost/count manifests, roadmap/FAQ/donation wording, HTML-source drift, SEO/sitemap, module/database facts and page defects from authoritative generated manifests where practical. | Depends on H and a fresh release/inventory snapshot. No payment activation. |
| J - AI knowledge and guardrails | EKA-57, EKA-58, EKA-59, EKA-60, EKA-61, EKA-62, EKA-63, EKA-64 | Create one refreshable knowledge source, sanitize untrusted prompt inputs, align privacy/donation answers, apply guardrails and budgets to every route, harden UI/error behavior, add canonical QA coverage and fix AI anchors/soft 404s. | Depends on H/I canonical facts. No paid-provider or autonomous-forum activation. |
| K - Evidence-only closure | EKA-20, EKA-56 | Reverify the historical baseline and strengths register, link immutable evidence, and close as recorded rather than pretending they are code defects. | Documentation-only after related packages settle. |

Recommended order: **A -> B -> C/D/G -> E -> F -> H -> I -> J -> K**.
Packages C, D and G may be developed in separate worktrees after B is stable,
but each still receives one integration owner and one final verification chain.

## Ticket and bridge rules

- Issue #318 remains the only 64-checkbox audit register.
- Each package above gets one bounded GitHub tracking issue or existing PR link;
  implementation PRs close only the EKA IDs they actually verify.
- A checkbox is updated only after merge plus affected main-branch checks. A
  production-dependent finding also needs live evidence before closure.
- Side findings go into a separate issue and do not enlarge an active PR.
- Public bridge entries contain only technical status. Private finance,
  provider, identity or operational values remain outside this repository.

## Public audit transparency plan

The website should disclose the audit, but only after the public wording and
status source are trustworthy. The future bounded content package will:

1. add a bilingual audit/remediation page under the wiki;
2. state the audit date, audited baseline, auditor attribution and original
   counts without claiming that an open finding is fixed;
3. link the immutable reports and public register #318;
4. list completed fixes only from merged, reverified PRs;
5. link the page from Security/Wiki and an appropriate footer/transparency
   location without exposing private operational evidence.

This disclosure is planned, not yet published.

## Redesign inventory and freeze

The current public surface contains 35 HTML files:

- core/landing: `docs/index.html`, community, representative, municipality,
  gov.gr design, legal, mirror setup, demo and ticket/SSO pages;
- voting pages: active, recent and results;
- 14 wiki pages: index, architecture, security, API, database, modules,
  privacy, ZK voting, broadcasting, delete-account, contributing, whitepaper,
  roadmap and FAQ;
- three embeds: QR login, vote and results;
- the animation reference page.

The redesign source is a visual specification, not a replacement tree. Its
implementation sequence is frozen as follows:

1. **R0 - canonical inventory:** snapshot every page's Greek/English content,
   links, forms, scripts, API contracts, structured data and responsive states;
   complete packages H/I before text freeze.
2. **R1 - isolated foundation:** local assets, tokens, header/footer and base
   states in a feature branch; no page content removal and no external CDN
   added without CSP/privacy approval.
3. **R2 - landing reference:** migrate `docs/index.html` only and compare every
   content block and live behavior with the inventory.
4. **R3 - wiki shell:** migrate the shell plus one pilot page, then all 14 pages
   only after visual, accessibility, link and content parity gates pass.
5. **R4 - remaining public pages:** community, representative, municipality,
   gov.gr design, demo, legal, mirror, tickets, SSO and vote lists in bounded
   groups.
6. **R5 - embeds:** preserve host contracts; adjust only approved typography,
   colors and radius after embedded-flow tests.

No phase starts automatically after the previous phase. Each requires explicit
`approved_for_execution` status and target stop.

## Redesign acceptance gates

- No existing information or functional link is lost; audit-corrected wording
  is the canonical source of truth.
- Greek and English remain complete and semantically paired.
- API data, forms, chat/newsletter entry, empty/loading/error states and
  language switching work without prototype `support.js`.
- Desktop and 360px mobile screenshots pass; no clipping or horizontal page
  scroll; keyboard focus and 44px targets remain visible.
- External assets and scripts comply with the final CSP/privacy decision.
- JSON-LD, metadata, sitemap, canonical and hreflang output pass automated
  checks.
- Embeds and SSO retain their contracts.
- Required tests and visual comparisons pass before any deployment proposal.

## Open owner inputs for the redesign

1. Use the supplied Pnyx drawing or replace it with a higher-resolution image.
2. Provide an authoritative SVG logo if available.
3. Decide whether to recolor/embed the existing animated diagrams.
4. Decide whether representative-app screenshots should be public.

These choices do not block audit packages A-G. They block only the relevant
redesign visuals.

## Current stop point

- Audit and helper work catalogued; Package A is closed, Package B is integrated
  with its production gate still open, and Package C's EKA-04, EKA-03, EKA-05
  EKA-06 and EKA-09 source subsystems are integrated with their rollout/live
  gates still open.
- CI limitation correctly classified; all
  #319/#320/#325/#326/#327/#328/#329 integration checks passed.
- Design source preserved outside the public web root.
- No redesign code or public content changed.
- Kimi's independent catalog review remains deferred by its external quota. The
  EKA-32 final delta used the documented Claude/Sol fallback review; EKA-04 was
  implemented by Kimi and independently reviewed by Claude, CodeRabbit and Sol.
  EKA-03 was implemented by Kimi; its initial Claude review approved, its three
  CodeRabbit findings were fixed, and quota-limited follow-up agents were
  replaced by the documented final Sol review. EKA-05 was implemented by Kimi
  under Sol review; Claude found no blocker and CodeRabbit's two valid findings
  were fixed before the normal merge. EKA-06 was implemented and reviewed with
  Kimi under Sol control; CodeRabbit's two valid findings were fixed before the
  normal merge and main verification. EKA-09 was implemented by Kimi under Sol
  control, independently reviewed without a blocker, and merged after
  CodeRabbit plus the complete protected verification chain passed.

Next executable action requires a separate exact choice: either the bounded
**Package B API rollout/live acceptance**, the bounded **EKA-04 API rollout/live
acceptance**, the staged **EKA-03 API/Android/adoption/cutoff sequence**, the
staged **EKA-05 API/Mobile/adoption/live-acceptance sequence**, the bounded
**EKA-06 API/dashboard rollout/live acceptance**, the bounded
**EKA-09 API/Brevo configuration and rollout/live acceptance**, the bounded
**EKA-16 API rollout/live log acceptance**, the bounded **EKA-17 production
environment migration/live acceptance**, or specification of EKA-53 as the
next Package C subsystem. None starts automatically from this document.
