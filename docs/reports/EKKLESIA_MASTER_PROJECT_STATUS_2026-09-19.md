# Ekklesia master project status - 2026-09-19

Status: `AUTHORITATIVE_CHECKPOINT`
Scope: public, security-safe project status; no private provider, tax, account,
recipient, customer, secret or production credential data
Repository baseline: `origin/main` at
`6a8ed73a04e029d8d6525c0ccdd31f487ec684`
Snapshot window: 2026-09-19, approximately 09:30-10:05 UTC
Post-snapshot integration deltas reconciled through PR #327 merge and green
post-merge checks on 2026-09-20 at approximately 08:29 UTC
Prepared in: draft documentation PR
[#323](https://github.com/NeaBouli/pnyx/pull/323)
Detailed finance and local-worktree evidence: private/local operator records,
not this public report

## 1. Purpose and reading rules

This document is the complete project checkpoint requested by the repository
owner. It distinguishes the running V1 platform, work that is implemented but
not fully accepted, open defects and security findings, external gates, future
roadmap work and locally preserved candidates that are not safe to treat as
integrated code.

The following evidence labels are used:

| Label | Meaning |
|---|---|
| `VERIFIED-LIVE` | Checked against a public production or distribution endpoint during this snapshot. |
| `VERIFIED-REPO` | Checked against current GitHub or the pinned repository baseline. |
| `IMPLEMENTED-NOT-ACCEPTED` | Code exists, but one or more review, device, rollout or evidence gates remain. |
| `OPEN` | A current task or defect remains unresolved. |
| `EXTERNAL-GATE` | Completion depends on an external store, maintainer, upstream project, tester or owner action. |
| `FUTURE-GATED` | Deliberately planned work that must not be treated as a V1 regression. |
| `PRIVATE-GATE` | Detailed evidence belongs in the private VLABS/operator record and is intentionally redacted here. |
| `HISTORICAL` | Useful retained context, but not current authority. |

Priority of sources for this checkpoint:

1. fresh live read-only probes and current store/catalog consoles;
2. current GitHub PRs, issues, actions, releases and Dependabot alerts;
3. the pinned EKA audit reports and issue #318;
4. current repository status and operation receipts;
5. the local gitignored bridge for private or device-only evidence;
6. older TODO or handoff notes only where revalidated.

This report authorizes no merge, deployment, database write, provider write,
payment activation, DNS change, secret change, IAM change or store promotion.

## 2. Executive status

### 2.1 Plain-language verdict

Ekklesia V1 is **online and operational**, but the project is **not completely
finished**.

- The website, API, forum, dashboard login, read-only mirrors and Android
  download endpoints are reachable.
- GitHub CI and Security Audit are green on `main`; 16 PRs remain open after
  the normal merges of #319, #320, #325, #326 and #327.
- Android `v1.0.32` is current on GitHub, Google Play Closed Testing and
  F-Droid.
- The project has no open Critical or High EKA finding. The sole High finding,
  EKA-02, is closed; 21 Medium findings remain evidence-gated, including EKA-32,
  EKA-04, EKA-03 and EKA-05. Their source integrations are complete, but their
  separate rollout, compatibility/adoption and live-acceptance gates remain
  open.
- Google Play production access is externally blocked at 8 of 12 opted-in
  testers, followed by the required qualifying 14-day test period.
- Three mobile acceptance tracks remain: the persistent action ledger and
  real notification delivery, large-font bottom-tab layout, and exact Xiaomi
  installation/HLR/picker acceptance.
- Newsletter consent-to-campaign delivery and live acceptance of the integrated
  abuse guard, the evaluation-v2 cutoff, DMARC evidence, five dependency
  alerts, the full EKA remediation program and the 35-page redesign remain open.
- Voluntary support/payment intake remains disabled. Neither `PRODUCT_READY`
  nor `FINANCE_READY` is granted for that candidate.
- iOS, gov.gr identity and Minima V2 are future gated tracks, not missing V1
  hotfixes.

### 2.2 Current risk view

| Area | Current assessment | Reason |
|---|---|---|
| Public availability | Green | Core pages, API, forum, dashboard login and all three mirrors returned HTTP 200. |
| CI and scheduled automation | Green | Latest 30 sampled Actions runs completed successfully; no Actions quota failure. |
| Android V1 distribution | Green/yellow | v1.0.32 is public in all intended Android channels; Play production gate and OEM acceptance remain. |
| Security audit | Yellow/high attention | 0 Critical, 1 closed High, 21 Medium, 27 Low and 15 Informational findings; 63 register items remain evidence-gated. |
| Vote integrity | Green with follow-up | Existing signature, uniqueness and ZK aggregation protections remain; EKA-01/10/12 still require bounded remediation. |
| Identity/privacy | Yellow | Running design remains fail-closed; client key storage/KDF and several public claims require audit remediation. |
| Data and forum synchronization | Green with quality backlog | Current schedulers and forum sync are healthy; manual Diavgeia mapping and analytics semantics remain. |
| Newsletter/mail | Yellow | Send path works, but consent source and Brevo campaign audience are not yet proven coherent. |
| AI/chatbot | Yellow | Module is healthy, but knowledge, prompt-injection, guardrail and answer-quality findings are open. |
| Dashboard/admin | Green/yellow | Login and module health are live; full authenticated panel acceptance and review follow-ups remain. |
| Finance/support | Safely disabled | No paid product is active; private VLABS gates and immutable candidate evidence remain incomplete. |
| Redesign | Planned only | Design archive is preserved but not wired into production. |

## 3. What "completely finished" means

For this project, completion cannot mean that every future idea has shipped.
It should be evaluated in layers:

### 3.1 V1 operational completion

V1 is operationally complete when:

- all required public and authenticated workflows pass end-to-end;
- all High and release-blocking Medium security findings are fixed or formally
  accepted with evidence;
- all released Android channels behave consistently within their intentional
  channel differences;
- real OEM/device, notification, HLR and accessibility acceptance is complete;
- newsletter, DMARC, forum and data-quality runbooks have current evidence;
- dashboards and administration paths are fully tested, not only reachable;
- current documentation, public claims and release facts are coherent;
- rollback and recovery evidence is current for each deployed component.

### 3.2 Distribution completion

- Direct APK, Google Play and F-Droid remain current and documented.
- Google Play reaches the 12-tester/14-day production-access gate and receives
  a separate, explicit production-track decision.
- F-Droid listing localization is handled within F-Droid's supported locale
  model.
- iOS is either explicitly retained as future work or receives its own signed,
  tested release program.

### 3.3 Audit completion

- every EKA-01..64 checkbox has merged/reverified evidence or a documented,
  owner-approved risk acceptance;
- production-dependent findings also have live evidence;
- a follow-up audit confirms the resulting baseline;
- the public site accurately describes the audit and the fixes without
  claiming open items as complete.

### 3.4 Roadmap completion

Minima V2, gov.gr identity and iOS are separate programs. Their continued
existence in the roadmap must not prevent a truthful statement that V1 is
stable. Conversely, they must not be labeled complete until their own gates
pass.

## 4. Repository and delivery baseline

| Item | Snapshot |
|---|---|
| `origin/main` | `6a8ed73a04e029d8d8d6525c0ccdd31f487ec684` |
| Latest GitHub release | `v1.0.32`, published 2026-09-06 |
| Release commit | `d25d4ee116055ff8395e1305d4f77bf6de414ace` |
| Direct Android version | `1.0.32`, versionCode `61`, channel `direct` |
| Play Android version | `1.0.32`, versionCode `61`, Closed Testing Alpha |
| F-Droid version | `1.0.32`, suggestedVersionCode `614` |
| API version contract | `1.0.32`, code `61`, `force_update=false` |
| Audit baseline | `c0efac7b0ee7669d91402c50eb5dcf4db7819fe3` |
| Audit publication | PR #317, merged as `6a8ed73` |
| Audit register | GitHub #318 |
| Redesign tracker | GitHub #324 |

The latest GitHub release contains the checksum-verified Direct APK and Play
AAB. Its published SHA-256 values remain:

- Direct APK:
  `67e051c549c9e97d1ebfa0a840f4e41216125403bfc5614a79563062154bec56`
- Play AAB:
  `1064bad1d21e80f47b36c331defaf0b501d1d5e72374c431155f782fb3208b24`

## 5. Fresh live operational snapshot

### 5.1 Public endpoints

| Surface | Result | Classification |
|---|---:|---|
| `https://ekklesia.gr/` | HTTP 200 | `VERIFIED-LIVE` |
| `/el/bills` | HTTP 200 | `VERIFIED-LIVE` |
| `/el/results` | HTTP 200 | `VERIFIED-LIVE` |
| `/community.html` | HTTP 200 | `VERIFIED-LIVE` |
| `/wiki/` | HTTP 200 | `VERIFIED-LIVE` |
| `/wiki/roadmap.html` | HTTP 200 | `VERIFIED-LIVE` |
| `/legal.html` | HTTP 200 | `VERIFIED-LIVE` |
| `https://api.ekklesia.gr/health` | HTTP 200 | `VERIFIED-LIVE` |
| `https://dashboard.ekklesia.gr/` | HTTP 200 after redirect to login | `VERIFIED-LIVE` |
| `https://pnyx.ekklesia.gr/` | HTTP 200 | `VERIFIED-LIVE` |
| technical mirror health URL | HTTP 200 | `VERIFIED-LIVE` |

### 5.2 Module health

The public module endpoint returned `overall=ok` and 23 modules:

| Module | Live status | Note |
|---|---|---|
| HLR Identity | `ok` | Provider credits endpoint also healthy. |
| VAA Compass | `ok` | Public claims still require EKA coherence work. |
| Parliament Scraper | `ok` | Last success 2026-09-19 04:00 UTC. |
| Citizen Vote | `ok` | EKA vote correctness follow-ups remain separate. |
| Divergence Score | `ok` | Representation endpoint currently has no qualifying dataset. |
| Analytics | `ok` | Counter semantics need reconciliation; see section 6. |
| Notifications | `ok` | Real delivery/OEM acceptance remains open. |
| Arweave Archive | `ok` | Wallet configured; publication-scope claims need correction. |
| gov.gr OAuth | `deferred` | Correctly future-gated, not active. |
| AI Scraper | `ok` | AI audit package remains open. |
| Public API | `ok` | Documentation and abuse-boundary findings remain. |
| MP Comparison | `ok` | No fresh full authenticated UX acceptance in this snapshot. |
| Relevance + Export | `ok` | No new write exercise performed. |
| Admin Panel | `ok` | Reachability is not full panel acceptance. |
| Municipal Governance | `ok` | Mapping quality backlog remains. |
| Community Donations | `ok` | Technical module health only; intake stays disabled. |
| Newsletter | `ok` | Consent-to-campaign handoff remains open. |
| Push Notifications | `ok` | F-Droid remains push-free by design. |
| Diavgeia Integration | `ok` | Last success 2026-09-17 16:00 UTC. |
| RAG Agent | `ok` | Knowledge/guardrail findings remain. |
| Discourse Forum Sync | `ok` | Last success 2026-09-19 10:00 UTC. |
| Politicians evaluation | `ok` | Evaluation v2 cutoff is separate. |
| Greek Topics Scraper | `disabled` | Deliberate disabled state, not a health failure. |

### 5.3 Mirrors

All three branded read-only mirrors were online and passed their health,
status and API checks:

- `1.ekklesia.gr`
- `2.ekklesia.gr`
- `3.ekklesia.gr`

Observed latency was approximately 1.4-1.6 seconds. This closes the earlier
"mirror looks partially functional" observation for the current snapshot. It
does not turn mirrors into write endpoints; voting, HLR, admin, forum, ZK and
Arweave writes remain primary-only.

## 6. Current data snapshot and data-consistency follow-up

### 6.1 Public aggregate snapshot

| Metric | Current public value |
|---|---:|
| Total public bills | 7,455 |
| Parliament bills | 60 |
| Diavgeia bills | 7,395 |
| Public-stats `active_bills` | 2 |
| Archived bills | 7,433 |
| Arweave-archived bills | 3 |
| Public `total_votes` | 22 |
| Forum bill-topic count reported by public API | 7,455 |
| Scraper total | 7,458 |
| CPLM voters | 5 |
| CPLM votes | 17 |
| CPLM open-end votes | 15 |

The public bills endpoint returned no visible `ACTIVE` or `WINDOW_24H` bill at
the exact snapshot time, and the trending endpoint returned an empty list.
That does not by itself prove an error: the public stats `active_bills` value
may use a broader not-archived definition or include statuses not shown by the
specific queries. The definition must nevertheless be documented or aligned so
the website, API and operators do not present apparently conflicting counts.

### 6.2 Representation counter semantics

Fresh read-only evidence is not internally intuitive:

- platform public stats: `total_votes=22`;
- CPLM: `total_votes=17`, `total_voters=5`;
- cumulative representation: `bills_analyzed=0`,
  `total_citizen_votes=0`, "Not enough data yet".

This is **not evidence that votes were lost**. These endpoints deliberately
consume different eligibility/status datasets. It is an open coherence task to
document the differences, verify each query against a known bill and make the
UI labels explicit. The earlier Telegram/public-results bug that omitted ZK
receipts was fixed and live-verified in commit `5bd6509`; it must not be
reopened without contrary evidence.

### 6.3 Diavgeia municipality mapping

The old GitHub #83 "3/101" blocker was closed after revalidation. The last
verified production dry-run recorded:

- 325 municipalities in scope;
- 297 mapped primary rows already present;
- 263 automatic matches;
- 34 rows needing review;
- 28 unmatched municipalities;
- 1,775 total mapping rows.

The remaining 28 are manual alias/review data-quality cases, not proof that the
current municipality pipeline is broken. Completing them requires:

1. a fresh read-only dry-run against the current organization snapshot;
2. human verification of every proposed alias;
3. an exportable before/after manifest and rollback plan;
4. separate explicit authorization before any database write;
5. post-write API, dashboard and municipality-filter verification.

No database change belongs in the audit/redesign documentation PR.

### 6.4 Forum topic health

Current evidence is healthy:

- public API forum topic count equals the public bill count at 7,455;
- Discourse reports 7,655 total topics and 7,679 total posts, which also include
  non-bill topics;
- forum sync last succeeded during the snapshot;
- Discourse is on `2026.8.0-latest.1`.

The prior alerts for two missing Diavgeia topics and hundreds of refresh
failures are not active in the current snapshot. Sensitive Diavgeia decisions
remain intentionally excluded from public topics. The data catalog and monitor
rules must continue to distinguish an intentional exclusion from a sync
failure.

## 7. Android and store distribution

### 7.1 GitHub/direct channel

Status: `VERIFIED-LIVE`.

- Latest release: `v1.0.32`, versionCode 61.
- Direct APK is public and checksum-verified.
- API and website download contract point to the v1.0.32 release.
- Direct updates require the Direct signing lineage.

### 7.2 Google Play

Status: `EXTERNAL-GATE` for production access.

- Closed Testing Alpha is active with release `61 (1.0.32)`.
- Production is not active.
- The console showed 8 opted-in testers at the snapshot.
- Requirement: at least 12 opted-in testers; 4 more are needed.
- After reaching the threshold, the qualifying closed test must satisfy the
  console's 14-day requirement before production access can be requested.
- Private allowlist membership is not used as a proxy for the active-tester
  count; only the console's opted-in value is reported here.
- Both registered Android package signing keys are confirmed in Developer
  Verification.
- No production-track promotion is authorized by this report.

### 7.3 F-Droid

Status: `VERIFIED-LIVE` for v1.0.32.

- `CurrentVersion: 1.0.32`
- `CurrentVersionCode: 614`
- Four ABI builds, versionCodes 611-614, are in the public catalog.
- The public package page lists v1.0.32 as added on 2026-09-09.
- v1.0.31 codes 601-604 and v1.0.29 codes 581-584 remain historical builds.
- No manual APK upload is required or permitted; F-Droid builds from source.
- The F-Droid site currently has no Greek (`el`) site locale/hreflang for the
  package page, so the visible listing remains English on the default page.
  Greek Fastlane text exists in this repository, but public F-Droid Greek
  presentation requires an upstream-supported localization path.
- F-Droid is intentionally built without Expo/FCM push; local/in-app behavior
  must remain functional without Google services.

### 7.4 Cross-channel installation rule

Direct, Play and F-Droid are independently signed distribution channels. An
APK from one channel is not necessarily an in-place update for another channel.
The app and website must keep this explicit because uninstalling to switch
channels can remove the anonymous local identity and require re-verification.

### 7.5 iOS

Status: `FUTURE-GATED`.

- No public iOS build exists.
- The iOS package identifier difference is known and audit-tracked.
- A public iOS release needs its own key custody, privacy declarations,
  notification behavior, device matrix, store metadata, rollback and release
  acceptance. It is not part of the current Android hotfix queue.

## 8. Mobile app: complete current open work

### 8.1 Unread actions and icon badge - GitHub #290

Status: `IMPLEMENTED-NOT-ACCEPTED`.

Released v1.0.32 has the initial category-aware icon count. It increments for
enabled categories, caps at 99 and clears when the app opens/foregrounds or a
relevant switch is disabled. It does **not** satisfy the complete persistent
per-event ledger.

PR #297 later merged source support for persisted unread state,
deduplication, category preferences and an in-app fallback. Still required:

- connect every intended real event producer;
- prove one increment per stable event ID, including replay behavior;
- reduce only the opened/acknowledged event rather than clearing all;
- real launcher/push delivery acceptance;
- Samsung One UI, Xiaomi MIUI/HyperOS and standard Android emulator matrix;
- separate Play, Direct and F-Droid behavior documentation;
- a new normally reviewed and signed release after acceptance.

### 8.2 Large-font navigation - GitHub #298

Status: `OPEN`.

At Android system font scale 1.8, bottom-tab labels are clipped. Required:

- focused layout correction without globally disabling font scaling;
- 1.0, 1.3 and 1.8 scale checks;
- narrow portrait and landscape checks;
- gesture and three-button navigation checks;
- preservation of routes, active state, touch targets and safe areas;
- unit/full mobile tests, typecheck, native build and device/emulator images.

### 8.3 Xiaomi install, HLR and picker - GitHub #315

Status: `OPEN ACCEPTANCE`, not a request to duplicate PR #291.

Already integrated:

- explicit foreground/background picker colors;
- Greek local `069...` normalization;
- fail-closed fallback HLR handling;
- Direct v1.0.32 publication;
- 24 synthetic HLR-provider regressions plus API usage tests.

Still required from the affected Xiaomi device:

- exact model and Android/MIUI/HyperOS version;
- installed app version and channel;
- installer error code and signature/channel compatibility;
- visible picker selection in onboarding and profile;
- sanitized HLR classification/error code and matching app/API version;
- confirmation that no old incompatible package or cross-signature update is
  being mistaken for a current app failure.

No real phone number, device serial or user identity belongs in public records.
No paid HLR query should be triggered solely to close the ticket without a
separate scoped authorization.

### 8.4 Evaluation v2 migration - GitHub #253

Status: `IMPLEMENTED-NOT-CUT-OVER`.

Score-bound v2 signatures and signed personal reads are merged. Completion
requires:

- deployed API/header-forwarding readiness proof;
- release of a compatible app;
- monitoring of both signed read and signed write adoption;
- an explicitly approved reversible `EVALUATION_REQUIRE_V2=true` cutoff;
- expected upgrade response for old clients;
- current-client prefill/history device verification;
- retirement of the legacy signing export only after stable adoption.

Unsigned compatibility remains a temporary residual exposure. No environment
flip is authorized here.

## 9. Website, landing, wiki and public documentation

### 9.1 Current service state

Core pages are reachable and the roadmap page title is currently "Roadmap &
Frequently Asked Questions" in its Greek presentation. Live availability does
not mean content coherence is finished.

### 9.2 Known public-documentation work

The EKA audit identified a large public-fact drift cluster:

- privacy/analytics/cookie wording;
- compass and server-side history wording;
- statements about whether the server can infer a vote;
- Arweave permanence and publication scope;
- wrong/nonexistent API examples;
- stale distribution and download status;
- conflicting module, endpoint, table, container and cost counts;
- HLR, AI-provider and vote-change contradictions;
- donation/support status;
- ZK status wording;
- legal-entity/data-controller naming;
- Markdown/HTML drift;
- SEO, sitemap, canonical and hreflang defects;
- phantom modules and database-table documentation;
- assorted broken links, duplicate IDs and visual defects.

The master redesign must not copy these stale claims into a new visual shell.
Audit packages H and I must produce the canonical bilingual fact set before the
redesign content freeze.

### 9.3 Public audit transparency

The audit reports are in the repository, but the requested bilingual public
audit/remediation page is not yet live. It must:

- name the audit date and audited baseline;
- state 0 Critical, 1 High, 21 Medium, 27 Low and 15 Informational findings;
- link the immutable reports and issue #318;
- list a fix only after merge and re-verification;
- avoid exposing private operational evidence;
- be linked from Security/Wiki and a suitable transparency/footer location.

## 10. Dashboard and administration

Status: `LIVE WITH ACCEPTANCE FOLLOW-UP`.

Verified now:

- dashboard root redirects to the authenticated login and returns HTTP 200;
- public module health reports the Admin Panel as `ok`;
- HLR primary/fallback counters are served and currently healthy;
- scheduler, DeepL, newsletter, Arweave and other public-safe supporting
  endpoints respond.

Known half-open work:

- the HLR dashboard repair is deployed, but its operation note still records a
  review follow-up and says its four synthetic tests are not wired into CI;
- a future dashboard rollout must reconcile its deployed baseline and record a
  Git rollback tag; the first repair retained only the image rollback evidence;
- five dashboard dependency PRs are open (#308, #310, #311, #312, #313);
- EKA package F must revalidate root/container/tag/admin exposure and public
  admin-adjacent endpoints;
- this snapshot did not perform a new authenticated click-through of every
  dashboard page, filter, mutation, empty state and error path;
- the public `ok` module state is health evidence, not proof that every admin
  control works.

Definition of done for dashboard/admin:

1. current admin route inventory and role/access matrix;
2. deterministic tests for each read/write control;
3. full authenticated browser acceptance on desktop and mobile widths;
4. no secrets, personal data or provider values exposed in UI/logs;
5. dependency PRs reviewed in bounded groups;
6. rollback/source receipt for the deployed dashboard baseline.

## 11. Forum and SSO

### 11.1 Current state

- Discourse is online on `2026.8.0-latest.1`.
- Email, Google and Facebook login options were removed from the intended
  Ekklesia-only flow.
- Desktop QR login and mobile app deep-link login are present.
- The download tiles use the intended 2-by-2 layout, with iOS visibly
  unavailable rather than silently missing.
- SSO signatures, nonce TTL, single-use consumption, logout and stale-session
  handling have deterministic coverage.
- The owner completed a voluntary real-citizen login/logout canary on
  2026-08-24.

The older unchecked TODO and operation receipt that still call this canary
"pending" are stale and should be treated as superseded by the later bridge
evidence.

### 11.2 Remaining forum work

- keep the Discourse patch version under normal upstream monitoring;
- retain the intentional separation between verified forum access and public
  discussion content;
- preserve moderator edits through the content-ownership hash model;
- continue distinguishing sensitive/hidden Diavgeia rows from genuine missing
  forum topics;
- no autonomous multi-agent forum discussion engine is active. The only
  repository evidence is future deliberation/pol.is roadmap material; any such
  system requires a separate safety, disclosure, anti-spam and governance
  design before implementation.

## 12. Newsletter, email and DMARC

### 12.1 Confirmed working pieces

- Owner intent is send-only; Ekklesia does not operate general inbound domain
  mailboxes.
- External reply routing is deployed.
- Double opt-in confirmation and one authorized test newsletter were received
  by the owner on 2026-08-30.
- Live newsletter stats show 5 subscribers and 33 messages sent in the current
  month.
- The monthly scheduler exists; the optional weekly newsletter remains a
  distinct future feature.

### 12.2 GitHub #261 delivery gap

The consent record and Brevo campaign audience are not yet proven coherent.
The last no-write inventory found five confirmed records, three absent from
Brevo, two list matches and no provider-only list records. A code-only guard
exists but has not completed the production repair sequence.

Required sequence:

1. verify the current consent, preference, unsubscribe, complaint, bounce and
   suppression sources;
2. review the guard and deploy it only under a separately bounded API rollout;
3. produce an idempotent no-write reconciliation manifest;
4. prove pending/unsubscribed/suppressed/invalid contacts are excluded;
5. obtain separate approval before any provider contact write;
6. run only a separately authorized controlled recipient test;
7. preserve schedules, list ownership and existing suppression state.

No bulk import, silent resubscribe or live campaign is authorized here.

### 12.3 DMARC

Current evidence remains incomplete:

- one Microsoft aggregate report and one passing message are catalogued;
- the message passed DMARC via aligned Brevo DKIM;
- SPF passed but was not aligned, which is compatible with that Brevo path;
- a representative observation set for every active sending path has not been
  assembled;
- no DMARC enforcement/DNS change should be proposed until that evidence is
  complete.

This is a mail-governance evidence gap, not a current website outage.

## 13. AI, chatbot and autonomous-agent scope

Status: `RUNTIME HEALTHY, QUALITY/SECURITY REMEDIATION OPEN`.

Live evidence:

- AI Scraper and RAG Agent modules report `ok`;
- DeepL usage endpoint is healthy;
- the current Claude-agent budget endpoint reports active status;
- no new live chatbot question was submitted during this status-only audit.

Open EKA package J covers:

- no single authoritative knowledge refresh path;
- scraped titles inserted into prompts without the required sanitization;
- wrong key-storage teaching;
- paused donation links being recommended by the bot;
- a Claude route bypassing the full guardrail/budget path;
- frontend and pipeline robustness gaps;
- missing canonical answers for deletion, ZK, representative verification and
  results lifecycle;
- stale AI anchors and soft-404 redirects.

The previously observed nonsensical answer to a simple greeting is consistent
with these quality gaps. Completion needs canonical bilingual QA fixtures,
prompt-injection regressions, one knowledge source, enforced budgets/guardrails
on every route and verified UI fallback/error behavior.

No autonomous forum-debate swarm is confirmed as deployed. It must not be
enabled as an undocumented substitute for citizen participation.

## 14. Security and dependency status

### 14.1 CI and GitHub Actions

- Latest 30 sampled GitHub Actions runs: all completed successfully.
- Main CI and Main Security Audit are green.
- Current draft status PR CI and Security Audit are green.
- There is no current GitHub Actions run-quota blocker.
- The earlier warning was CodeRabbit's included-review allowance, not Actions.
- Required CI must never be weakened to conserve minutes.

### 14.2 Open Dependabot alerts

Exactly five alerts are open:

| Alert | Severity | Package/path | Current gate |
|---|---|---|---|
| #78 | High | `image-size`, mobile, GHSA-5p2g-fcmc-qvqq | No patched upstream release. |
| #79 | High | `image-size`, mobile, GHSA-w3rx-r6r6-pgpr | No patched upstream release. |
| #80 | High | `image-size`, representative, GHSA-5p2g-fcmc-qvqq | No patched upstream release. |
| #81 | High | `image-size`, representative, GHSA-w3rx-r6r6-pgpr | No patched upstream release. |
| #82 | Medium | `decode-uri-component`, mobile, GHSA-vcc3-ghjq-m6fr | Upstream patch 0.5.0 exists, but the active React Navigation chain has no safe compatible update. |

The existing local security regressions/backports stay visible. Do not dismiss
alerts, force dependency majors or override peer constraints merely to obtain a
green alert count.

### 14.3 Additional upstream gates

- TypeScript 7 remains outside the supported range of the installed
  `typescript-eslint` toolchain.
- `arweave-python-client` still pulls `python-jose`, which still pulls the
  affected `ecdsa`; no compatible upstream removal or patched release is
  available for the current chain.
- The narrowly documented ecdsa exception is a tracked residual risk, not a
  claim that the package is globally safe.

## 15. Independent EKA audit

### 15.1 Totals and status

| Severity | Count | Register state |
|---|---:|---|
| Critical | 0 | None open |
| High | 1 | Closed: EKA-02 source, merge, rollout and live acceptance verified |
| Medium | 21 | Open/evidence-gated |
| Low | 27 | Open/evidence-gated |
| Informational | 15 | Open/evidence-gated |
| Total | 64 | 1 closed; 63 issue #318 boxes remain evidence-gated |

Publishing an audit is not fixing it. A green PR is not deployment evidence.

### 15.2 Remediation package order

| Package | Finding IDs | Completion requirement |
|---|---|---|
| A - Representative XSS | EKA-02 | Complete: PR #319 merged, bounded Web rollout passed hostile-payload live acceptance, #318 closed. |
| B - Global rate limiting | EKA-32 | Integration complete in PR #320; production rollout and live acceptance remain separate. |
| C - Endpoint abuse/privacy | EKA-03/04/05/06/09/16/17/53 | EKA-04 source integration is complete in #325, EKA-03 in #326, EKA-05 in #327 and EKA-06 in #328; their rollout/live gates and the remaining webhook/logging/admin-status findings remain. |
| D - Vote/auth correctness | EKA-01/10/11/12 | Restore Tier-1 validation, deterministic municipal conflict response, dormant gov.gr state design and narrow exception handling. |
| E - Client keys/KDF | EKA-07/08/21/22/23/24 | Canonical formats/KATs, backward-compatible key-storage and KDF migration, explicit phone-entropy risk. |
| F - Runtime/integration | EKA-13/18/19/26/27/28/29/30/31 | Read-only inventory first; then bounded container, subdomain, admin, package-ID and CSP work. |
| G - Browser sinks | EKA-14/15 | Replace residual untrusted HTML sinks and remove dead admin query helpers. |
| H - Canonical claims | EKA-25/33/34/35/36/45/47/54/55 | One approved bilingual fact set for privacy, analytics, compass, votes, Arweave, retention, translations and ownership. |
| I - Public docs/release facts | EKA-37/38/39/40/41/42/43/44/46/48/49/50/51/52 | Correct API, distribution, count, cost, roadmap, donation, SEO and page defects from current manifests. |
| J - AI knowledge/guardrails | EKA-57..64 | One knowledge source, prompt sanitization, uniform budgets/guardrails, QA and UI hardening. |
| K - Evidence closure | EKA-20/56 | Reverify and close historical/strength records with immutable evidence. |

Execution order remains:
`A -> B -> C/D/G -> E -> F -> H -> I -> J -> K`.

### 15.3 Full finding register

The following list is intentionally complete so no audit item disappears from
the checkpoint.

#### High

- [x] EKA-02 - representative WebView stored-XSS surface with live token; fixed,
  merged, deployed through the bounded Web overlay and live-accepted.

#### Medium

- [ ] EKA-01 - Tier-1 advisory validation dead code/signature mismatch.
- [ ] EKA-03 - PR #326 (`5f850e2`) requires ACTIVE-identity Ed25519 proofs for
  bill flags and adds signed POST vote-status reads. The released unsigned GET
  remains behind a reversible cutoff; closure awaits API rollout, compatible
  Android release/adoption, cutoff and live acceptance.
- [ ] EKA-04 - dedicated newsletter limits and HMAC-only identifiers are merged
  in PR #325 (`760845a`); closure awaits separately authorized API rollout and
  live acceptance.
- [ ] EKA-05 - PR #327 (`9f52c95`) requires fresh ACTIVE-identity Ed25519
  proofs for push registration and uses random per-install UUIDv4 identifiers,
  stable HMAC Redis keys, bounded limits and token expiry. Closure awaits API
  rollout, compatible Mobile release/adoption and live acceptance.
- [ ] EKA-06 - PR #328 (`0ce4b31`) adds local format rejection, atomic
  Redis-backed HLR limits, fail-closed paid-provider protection and a coarse
  public status contract; closure awaits bounded API/dashboard rollout and live
  acceptance.
- [ ] EKA-07 - web Ed25519 private key in plaintext localStorage.
- [ ] EKA-08 - compass profile plaintext localStorage fallback.
- [ ] EKA-21 - three diverging nullifier-root KDF implementations.
- [ ] EKA-32 - global limiter is now enforced in merged source (`942e063`),
  but closure awaits separately authorized API rollout and live acceptance.
- [ ] EKA-33 - "0 analytics" claims conflict with Plausible.
- [ ] EKA-34 - compass never-on-server wording conflicts with stored history.
- [ ] EKA-35 - server vote-knowledge statement is overstated.
- [ ] EKA-36 - Arweave permanence claims exceed actual publication scope.
- [ ] EKA-37 - wrong/nonexistent wiki API endpoints and invalid curl example.
- [ ] EKA-38 - distribution, Apple and representative download drift.
- [ ] EKA-40 - inconsistent module/endpoint/table/container counts.
- [ ] EKA-42 - FAQ contradictions on AI, HLR and vote-change behavior.
- [ ] EKA-46 - Markdown/HTML wiki drift.
- [ ] EKA-57 - no authoritative AI knowledge refresh path.
- [ ] EKA-58 - prompt injection through unsanitized scraped titles.
- [ ] EKA-59 - chatbot teaches wrong key-storage facts.

#### Low

- [ ] EKA-09 - unauthenticated Brevo webhook.
- [ ] EKA-10 - municipal vote race returns 500 rather than 409.
- [ ] EKA-11 - dormant gov.gr OAuth state stored in process memory.
- [ ] EKA-12 - broad signature-verification exception handling.
- [ ] EKA-13 - root containers and mutable image tags.
- [ ] EKA-14 - residual unescaped sinks in static documentation.
- [ ] EKA-15 - dead admin-key query helpers shipped in Web client.
- [ ] EKA-16 - personal data in application logs.
- [ ] EKA-22 - missing cross-implementation crypto KATs.
- [ ] EKA-26 - unrelated third-party app on an Ekklesia subdomain.
- [ ] EKA-27 - dangling/dead subdomains and exposed test host.
- [ ] EKA-28 - publicly reachable Listmonk/Plausible login panels.
- [ ] EKA-30 - broad static/wiki CSP with `unsafe-inline`.
- [ ] EKA-39 - conflicting annual-cost totals.
- [ ] EKA-41 - TrueRepublic described as a live chain.
- [ ] EKA-43 - ZK described both as live Beta and coming Alpha.
- [ ] EKA-44 - donation/support status described as live despite gate.
- [ ] EKA-45 - three conflicting IP-retention descriptions.
- [ ] EKA-47 - visible Greek text differs from `data-el` claims.
- [ ] EKA-48 - legal/JSON-LD/Twitter/hreflang SEO gaps.
- [ ] EKA-49 - stale sitemap dates and incorrect canonical target.
- [ ] EKA-50 - phantom MOD-13/MOD-17 documentation.
- [ ] EKA-51 - duplicate IDs/links, footer, icon and badge defect cluster.
- [ ] EKA-52 - MOD-25 and database-table status inconsistencies.
- [ ] EKA-60 - bot points users to paused support processors.
- [ ] EKA-61 - Claude ask route bypasses full guardrails/budget.
- [ ] EKA-62 - chatbot frontend/pipeline robustness cluster.
- [ ] EKA-63 - chatbot coverage gaps for sensitive platform topics.

#### Informational

- [ ] EKA-17 - inverted HLR credential environment names.
- [ ] EKA-18 - dev compose publishes datastores with default credentials.
- [ ] EKA-19 - Android/iOS package-ID drift.
- [ ] EKA-20 - re-baseline the May master audit.
- [ ] EKA-23 - phone-number entropy bounds every nullifier KDF.
- [ ] EKA-24 - test-only `computeNullifier` export in web bundle.
- [ ] EKA-25 - server-derived political positions vs client-only framing.
- [ ] EKA-29 - dependency alert/PR backlog.
- [ ] EKA-31 - verified-wiring register.
- [ ] EKA-53 - public DeepL usage route under admin prefix.
- [ ] EKA-54 - inconsistent legal-entity naming.
- [ ] EKA-55 - "no owner" rhetoric vs named controller.
- [ ] EKA-56 - verified strengths register.
- [ ] EKA-64 - stale AI anchors and soft-404 redirects.

## 16. Current open pull requests

There are 16 open PRs after #319, #320, #325 and #326 merged normally. The table
below is a point-in-time maintenance inventory; green automation alone is not
merge authorization.

| PR | Scope | Head | Current action |
|---:|---|---|---|
| #323 | Audit/redesign catalog and this checkpoint | `docs/audit-redesign-catalog-20260919` | Keep draft until documentation review completes. |
| #322 | sentry-sdk 2.68.1 -> 2.69.1, API | `7cf34566...` | Review and merge separately if compatible. |
| #321 | Alembic 1.19.1 -> 1.20.0, API | `c36ab8b0...` | Review migration tooling compatibility; separate merge. |
| #313 | Next 16.3.3 -> 16.3.4, dashboard | `4a1e29c3...` | Bounded dashboard dependency wave. |
| #312 | @types/react-dom 19.2.5 -> 19.2.7, dashboard | `bd05730c...` | Batch only with compatible dashboard checks. |
| #311 | autoprefixer 10.5.4 -> 10.5.5, dashboard | `b1fdddb5...` | Review with PostCSS/dashboard build. |
| #310 | postcss 8.5.26 -> 8.5.28, dashboard | `b0e2f99e...` | Review with Autoprefixer/dashboard build. |
| #309 | Vitest 4 -> 5, Web | `1381e16e...` | Major test-tool migration; do not auto-merge. |
| #308 | Next ESLint plugin 16.3.3 -> 16.3.4, dashboard | `33e8366a...` | Align with dashboard Next patch. |
| #307 | @types/react-dom 19.2.5 -> 19.2.7, Web | `9962822f...` | Small Web type update after review. |
| #306 | Arweave JS 1.15.7 -> 2.0.1, Web | `694ce14d...` | Major; requires API/behavior/security compatibility review. |
| #305 | lucide-react 1.37.0 -> 1.41.0, Web | `6049ce0c...` | UI regression review. |
| #304 | rapidfuzz 3.14.5 -> 3.14.6, API | `00fd89da...` | Verify Diavgeia matching regressions. |
| #303 | anyio 4.14.2 -> 4.15.1, API | `1ad41148...` | Verify async/API suite. |
| #302 | Stripe 15.6.0 -> 15.6.1, API | `d102d9cd...` | Finance-sensitive; real SDK adapter defect is not solved by this bump. |
| #301 | Next 16.3.3 -> 16.3.4, Web | `5403e9d9...` | Review with Web/PWA/browser matrix. |

Recommended PR order:

1. #321/#322 low-scope API maintenance;
2. coherent Dashboard patch group;
3. coherent Web patch group;
4. major #306 and #309 only as separate migration tasks;
5. #302 only after the finance adapter boundary is isolated.

## 17. Current open GitHub issues

There are 17 open issues:

| Issue | Class | Remaining definition of done |
|---:|---|---|
| #324 | Redesign epic | Execute R0-R5 only after canonical content and audit gates; no information loss. |
| #318 | Audit register | Close or accept every EKA-01..64 item with evidence. |
| #315 | Mobile acceptance | Exact Xiaomi install/HLR/picker evidence. |
| #298 | Accessibility | Large-font bottom-tab correction and device matrix. |
| #290 | Mobile notifications | Full event ledger, delivery matrix and new release. |
| #261 | Newsletter | Consent-safe Brevo handoff and controlled evidence. |
| #253 | Evaluation security | v2 client adoption and reversible cutoff. |
| #216 | Minima V2 epic | Gates G1-G5; V1 remains baseline. |
| #217 | V2 research | Maxima delivery and mobile resource measurements. |
| #218 | V2 PoC | Synthetic transport, receipts and deduplication. |
| #219 | V2 PoC | KISS root anchoring and independent verifier. |
| #220 | V2 ADR | Identity/proof/key model after PoC evidence. |
| #221 | V2 design | Bulletin board, federation and data availability. |
| #222 | V2 build | Isolated repository/CI only after G1. |
| #223 | V2 release | Parity, migration, rollback and rollout gates. |
| #141 | gov.gr Alpha | Privacy-preserving holder verification after official API/eSeal, DPIA and review. |
| #138 | gov.gr security design | Official credential choice, threat model and no-PII prototype. |

## 18. Finance and voluntary support

Public status: `PRIVATE-GATE`, intake disabled.

- Ekklesia has no premium function, membership, advertisement entitlement or
  digital good tied to support.
- Support is intended as voluntary private support without consideration.
- No paid product is currently active.
- Public support controls and payment intake must remain disabled.
- `PRODUCT_READY`: not granted.
- `FINANCE_READY`: not granted.
- The private finance handoff remains unresolved. Its exact evidence request,
  candidate defect and operator responsibilities are recorded only in the
  private operator channel and the local gitignored supplement.
- Any future candidate must prove fail-closed payment, refund, reversal,
  dispute and community-access behavior in isolation before either gate can
  change.

No private recipient, account, provider or tax details may be copied into this
repository. Finance coordination remains separate through the private VLABS
operator.

## 19. Redesign status

Status: `CATALOGED, NOT IMPLEMENTED`.

- The supplied redesign ZIP is preserved byte-for-byte outside the public web
  root.
- Source ZIP SHA-256:
  `8e41f707ba410cfd2f982ebdb68b31dfc78fafe0c40283a3b373780ba498c742`.
- Thirteen imported source files match the handoff bytes.
- The prototype is a visual reference, not a wired application.
- It contains stale or audit-sensitive claims and external CDN dependencies;
  it cannot be copied directly into production.
- The current public surface has 35 HTML files, including 14 wiki pages and
  three embeds.

Execution phases:

1. R0 - canonical page/content/function inventory;
2. R1 - isolated tokens/assets/header/footer foundation;
3. R2 - landing page parity migration;
4. R3 - wiki shell, pilot page, then all wiki pages;
5. R4 - remaining public pages in bounded groups;
6. R5 - embeds with preserved host/SSO contracts.

Acceptance requires exact information/function parity, bilingual completeness,
360px/desktop/accessibility checks, CSP/privacy review, link/SEO/schema checks,
loading/empty/error states and no prototype-only `support.js` dependency.

Owner visual inputs still needed before the corresponding design phases:

- use or replace the supplied Pnyx drawing;
- authoritative SVG logo;
- diagram recoloring/embedding decision;
- representative-app screenshot publication decision.

These inputs do not block audit packages A-G.

## 20. Future gated programs

### 20.1 Ekklesia V2 on Minima

Status: `FUTURE-GATED`, V1 protected.

- G0 architecture/threat/privacy review is complete.
- Only #217-#219 are executable Phase-1 synthetic evidence tasks.
- #220-#223 remain blocked until their preceding gates pass.
- No real identities, votes, production data, token economy or V1 deployment
  change is authorized.
- Current architectural hypothesis is hybrid: sparse roots on Minima,
  Maxima as candidate transport, off-chain Ed25519/Groth16 verification and a
  public bulletin board with durable append-only publication.
- V2 may not replace or retire V1 without a separate reversible decision.

### 20.2 gov.gr identity

Status: `FUTURE-GATED`.

Needs official integration or verified eSeal path, holder binding, replay and
revocation design, DPIA/legal basis, no persistent PII, credential migration,
independent security/privacy review and sandbox canary. HLR remains only a
Greek-number network/status gate; it does not prove identity, SIM possession,
citizenship, residence or electoral eligibility.

### 20.3 Optional product backlog

- weekly newsletter proposal (distinct from the implemented monthly job);
- broader direct app/web forum auto-SSO beyond the current
  Discourse-initiated flow;
- historical federation/demo-node scopes that must be re-triaged rather than
  inferred complete;
- future deliberation/pol.is work;
- public iOS release.

## 21. Tracker and repository hygiene

### 21.1 Linear

Fresh Linear status could not be verified because the current connector
requires OAuth reauthentication. This is a tracker-maintenance blocker, not a
runtime outage. Last-known references such as NEA-262, NEA-185, NEA-167,
NEA-113 and NEA-422 must be rechecked after reconnection before changing their
state.

### 21.2 Local worktrees

The local environment contains many historical worktree registrations,
including prunable missing temporary worktrees and several dirty retained
candidates. Two especially broad local candidates contain mixed, uncommitted
payment/readiness/notification work and are not safe merge sources.

Required hygiene task:

1. inventory each worktree and ownership;
2. preserve uncommitted user/agent work;
3. map any unique useful diff to an issue and immutable base;
4. extract only bounded reviewed patches into fresh branches;
5. prune registrations or delete files only under separate explicit approval;
6. never merge the broad dirty worktrees wholesale.

The exact local paths and counts remain in the gitignored private supplement.

## 22. Ordered completion program

This is the recommended execution order. Only one bounded package should be
`in_progress` at a time.

### Block 1 - Close the immediate High security candidate (complete)

- PR #319 received final review, regressions and sink inventory.
- Normal protected merge, post-merge CI/Security, bounded Web rollout and live
  acceptance completed; EKA-02 is closed in #318.

### Block 2 - Establish the API rate-limit baseline (integration complete)

- PR #320 passed review, middleware/proxy/CORS/fallback regressions, 1,019 local
  API tests, focused Redis tests, normal merge and post-merge CI/Security.
- A separately scoped API rollout and live acceptance are still required before
  checking EKA-32 in #318.

### Block 3 - Endpoint abuse/privacy package

- EKA-04 source integration is complete in PR #325: fixed-window DOI limits,
  HMAC-only rate-limit/log references and focused/real-Redis/full-suite evidence
  are green. A separate API rollout and live acceptance remain required.
- EKA-03 source integration is complete in PR #326: bill flags require an
  ACTIVE-identity Ed25519 proof, signed vote-status reads use POST bodies, and
  the released GET contract remains behind a reversible cutoff. A separate API
  rollout, compatible Android release/adoption, cutoff and live acceptance are
  still required.
- EKA-05 source integration is complete in PR #327: push registration requires
  a fresh ACTIVE-identity Ed25519 proof, random per-install UUIDv4 identifiers,
  stable HMAC Redis keys and bounded limits/expiry. A separate API rollout,
  compatible Mobile release/adoption and live acceptance are still required.
- Split the remaining EKA-06/09/16/17/53 work by subsystem.
- Preserve client compatibility and fail-closed identity behavior.
- No real HLR, newsletter, push or provider writes during synthetic tests.

### Block 4 - Vote/browser correctness

- EKA-01/10/11/12 and EKA-14/15 in bounded PRs.
- Do not alter governance semantics.
- Run complete vote/signature/municipal/SSO/browser regressions.

### Block 5 - Mobile acceptance and release

- Fix #298.
- Complete #290 event-producer and OEM matrix.
- Obtain #315 affected Xiaomi evidence and correct only the proven cause.
- Build/sign/test Direct, Play and F-Droid source variants.
- Publish a new release only after all three tickets' required evidence for the
  included scope is complete.

### Block 6 - Identity/KDF migration design

- Canonical formats and cross-client known-answer vectors first.
- Threat model and compatibility plan.
- No identity reset, silent key migration or production cutover.

### Block 7 - Newsletter and mail closure

- Deploy/review consent guard in a bounded API release.
- No-write reconciliation.
- Separate approved provider write and controlled test if needed.
- Header/unsubscribe/suppression evidence.
- Complete DMARC observation before policy changes.

### Block 8 - Evaluation v2 cutoff

- API readiness, compatible client release, adoption monitoring, reversible
  cutoff and legacy retirement.

### Block 9 - Runtime/admin/dependency maintenance

- EKA package F inventory.
- Dashboard full authenticated acceptance.
- Merge safe dependency patches in coherent groups.
- Keep majors #306/#309 separate.
- Retain upstream watches for image-size, decode-uri-component, ecdsa and TS7.

### Block 10 - Canonical content and AI

- Packages H and I establish the bilingual fact set.
- Public audit page.
- Package J knowledge/guardrail work and chatbot QA.
- Only then freeze redesign content.

### Block 11 - Redesign

- Execute R0-R5 with a target stop after every phase.
- No content removal or functional rewiring without explicit evidence.

### Block 12 - Finance candidate

- Extract the real-SDK normalization fix from the mixed local tree into one
  immutable branch.
- Focused plus full API tests and independent review.
- Private VLABS handoff under the existing request ID.
- Keep intake disabled until both readiness gates match the same immutable
  version.

### Block 13 - External and future gates

- Recruit four additional real Play testers, then satisfy the 14-day gate.
- Reauthenticate Linear and reconcile retained issues.
- Resolve F-Droid Greek listing through supported upstream localization.
- Start only approved V2 Phase-1 synthetic tasks.
- Keep gov.gr and iOS gated until their prerequisites exist.

## 23. Owner/external inputs still required

| Input | Needed for | Current consequence |
|---|---|---|
| Four additional opted-in Play testers | Google production-access test | Production request remains disabled. |
| Exact affected Xiaomi evidence | #315 acceptance | Do not guess or release another workaround. |
| Redesign visual choices | Relevant redesign phases | Does not block security packages. |
| Private finance evidence package | VLABS route assessment | Support intake remains disabled. |
| Explicit database authorization after reviewed dry-run | 28 Diavgeia mapping cases | No DB write. |
| Linear OAuth reauthentication | Fresh tracker reconciliation | GitHub remains current public authority. |
| Separate approval for any production rollout | Every deploy/restart/recreate | Code merge does not imply deployment. |

## 24. Items that are not current blockers

- GitHub Actions quota: currently healthy.
- Mirror outage: all three mirrors are online in this snapshot.
- F-Droid version publication: v1.0.32 is public.
- Forum software update: current official monthly patch is installed.
- Old Telegram ZK count bug: fixed and previously live-verified.
- Old Forum SSO real-login canary: completed by the owner on 2026-08-24.
- Google Android developer verification: package registered and both signing
  keys confirmed.
- Payment activation: safely disabled; not a runtime availability blocker.
- Minima/gov.gr/iOS: future programs, not conditions for maintaining V1.

## 25. Final completion checklist

V1 can be described as fully stabilized only when all of the following are
true:

- [x] EKA-02 High closed with merge and applicable runtime evidence.
- [ ] Release-blocking Medium EKA findings closed or formally accepted.
- [ ] Remaining EKA register processed with evidence and follow-up audit.
- [ ] #290 notification ledger/delivery accepted on required matrix.
- [ ] #298 large-font navigation accepted.
- [ ] #315 exact Xiaomi acceptance completed.
- [ ] #253 evaluation v2 cutoff completed.
- [ ] #261 newsletter handoff completed without consent regression.
- [ ] DMARC observation set complete before enforcement decision.
- [ ] Dashboard authenticated workflow matrix complete.
- [ ] Vote/representation/CPLM counter semantics verified and documented.
- [ ] 28 Diavgeia mapping cases re-dry-run and either completed or explicitly
      catalogued as unresolved with evidence.
- [ ] Five Dependabot alerts resolved only through safe compatible fixes, or
      remain visibly tracked with current upstream evidence.
- [ ] Safe dependency PRs integrated; major upgrades separately validated.
- [ ] Canonical bilingual facts replace conflicting public claims.
- [ ] Chatbot knowledge, injection, guardrail and QA package complete.
- [ ] Public audit/remediation page live and truthful.
- [ ] Redesign R0-R5 complete with content/function/accessibility parity.
- [ ] Google Play 12-tester/14-day gate complete and production decision made.
- [ ] Linear tracker reauthenticated and reconciled.
- [ ] Dirty local candidates triaged without loss or wholesale merge.
- [ ] Voluntary-support candidate remains disabled unless identical-version
      `PRODUCT_READY` and `FINANCE_READY` are both granted.

Future roadmap programs are complete only under their own gates:

- [ ] public iOS release, if still desired;
- [ ] gov.gr Alpha identity design and canary;
- [ ] Minima V2 G1-G5, without weakening or silently retiring V1.

## 26. Source references

- [Audit register #318](https://github.com/NeaBouli/pnyx/issues/318)
- [Redesign epic #324](https://github.com/NeaBouli/pnyx/issues/324)
- [Audit/remediation intake plan](../planning/EKA_REMEDIATION_AND_REDESIGN_PLAN_2026-09-19.md)
- [Community audit index](../community-audits/README.md)
- [Project status](../STATUS.md)
- [Current TODO](../TODO.md)
- [Release-gate receipt](../operations/RELEASE_GATES_2026-09-06.md)
- [Newsletter delivery audit](../operations/newsletter-delivery-audit.md)
- [DMARC observation gate](../operations/dmarc-observation-gate.md)
- [Forum SSO lifecycle](../operations/forum-sso-lifecycle.md)
- [Android v61 release receipt](../operations/ANDROID_V61_RELEASE_2026-09-05.md)
- [GitHub release v1.0.32](https://github.com/NeaBouli/pnyx/releases/tag/v1.0.32)
- [F-Droid package](https://f-droid.org/packages/ekklesia.gr/)

## 27. Checkpoint rule

This file is the project midpoint checkpoint as of 2026-09-19. Later work
must not silently rewrite historical evidence. Update it through reviewed,
dated deltas or replace it with a newer dated master checkpoint that links
back here.

## Post-checkpoint delta - EKA-06 source integration

Recorded at 2026-09-20 after the normal protected merge:

- PR #328 merged as
  `0ce4b31bf11f6e6c223e198f9168a54b14112e57` without admin bypass.
- Invalid Greek mobile formats are rejected locally before Redis or provider
  access. Valid attempts use HMAC-derived number buckets plus IP buckets, with
  all cooldown/day/minute checks and updates in one atomic Redis Lua operation.
  Redis failure blocks the paid HLR lookup.
- The public credits route exposes only coarse service state. Exact usage,
  balances, provider labels, costs and failover details are confined to the
  existing authenticated admin route and dashboard proxy.
- CodeRabbit's two valid findings were fixed in `8c8f8e2`: rejected IP attempts
  no longer consume number quota, and Finance reads the current exact-schema
  fields. Kimi reviewed the bounded change under Sol integration control.
- Focused API tests passed 67 tests; dashboard typecheck and production build,
  Python compile and diff checks passed. PR CI run `35503704091` and Security
  run `35503704107` passed. Post-merge main CI run `35503903428` and Security
  run `35503903422` passed completely.
- Public evidence: `https://github.com/NeaBouli/pnyx/pull/328`. Issue #318
  receives the source evidence while keeping EKA-06 unchecked.
- EKA-06 still requires a separately authorized bounded API/dashboard rollout
  and live acceptance before closure. No API/dashboard rollout, paid HLR
  lookup, database, DNS, secret, IAM, provider, payment, store or other
  production mutation occurred in this source-integration task.
