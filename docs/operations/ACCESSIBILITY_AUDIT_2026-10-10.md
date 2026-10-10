# Accessibility audit — 2026-10-10

Status: **partial live audit; bounded label fix locally verified, not deployed**.
Anonymous Chromium inspection found actionable issues; this is not a complete
accessibility or WCAG-conformance claim.

## Evidence and method

Initial raw evidence: `/private/tmp/T9046-axe-live.json`, timestamp
`2026-10-10T05:48:40.965Z`. Chromium `153.0.8010.12`, Playwright `1.63.0`,
axe-core `4.13.0`; widths 390 and 1280 pixels, EL and EN.
Corrected detail evidence: `/private/tmp/T9046-detail.json`.
Local candidate evidence: `/private/tmp/T9046-candidate.json`.
The browser used no session and permitted only GET, HEAD and OPTIONS requests.
Language changes on static pages used the actual EL/EN control.
Owner receipt identifies the deployed web build as `550549c7`; the new candidate
is based on main `d24ef97c` and is not deployed. The receipt is not an independent
container/build-identity check performed by this audit.

Raw `lang` stores the observed DOM language, overwriting the requested language
for static pages. This report uses `currentLang` for landing, community and wiki,
and `lang` for application routes. EN static cases still reported DOM `lang=el`;
that discrepancy remains open and must not be hidden by relabelling the JSON.

## Live coverage

Cells are **axe rule occurrences / affected nodes**, not unique product defects.
All 24 successful cases returned HTTP 200 and recorded no document overflow.
The initial 20 also recorded no page errors and zero blocked write attempts;
the detail JSON does not record those fields. Only inspected states are covered.

| View | 390 EL | 390 EN | 1280 EL | 1280 EN |
|---|---|---|---|---|
| Landing `/` | 3 / 7 | 3 / 7 | 3 / 7 | 3 / 7 |
| Bills `/{lang}/bills` | 2 / 4 | 2 / 4 | 2 / 5 | 2 / 5 |
| Results `/{lang}/results` | 2 / 5 | 2 / 5 | 1 / 5 | 2 / 6 |
| Community `/community.html` | 2 / 6 | 2 / 7 | 2 / 11 | 2 / 11 |
| Wiki `/wiki/` → `/wiki/index.html` | 3 / 4 | 3 / 4 | 2 / 3 | 2 / 3 |
| Bill detail `/{lang}/bills/{id}` | 4 / 11 | 4 / 11 | 3 / 12 | 3 / 12 |

The initial detail discovery expected an absolute href; the actual bill links
are relative. This was a probe error, not a site defect; all four corrected
cases passed navigation. Public ID: `DIAV-9%CE%9F%CE%92446%CE%A8%CE%962%CE%9D-5`.

## Findings and bounded fix

- **P2: landing `#nlType` has no accessible name.** Axe impact is `critical`,
  reproduced in all four landing cases. This control selects subscriber **type**
  (Citizen, Press, etc.), not newsletter frequency. The candidate adds hidden
  `span#nlTypeLabel` and `aria-labelledby`: “Τύπος συνδρομητή” / “Subscriber type”.
  Default `citizens`; values `citizens`, `press`, `parties`, `public_bodies`,
  `ngos`, `government` and the existing submission payload are unchanged;
  no form behavior, source JavaScript or layout change is intended.
- **Contrast remains open:** 24 rule occurrences / 119 nodes. Measured ratios
  include 2.34, 2.45 and 2.48, plus 1.72, 2.53 and 2.60. Check each affected
  element against its recorded size/weight threshold before choosing colors.
- **Wiki scrollable region:** `.code-block` is not keyboard focusable at 390px
  in both languages (`serious`, two occurrences / two nodes).
- **Heading order:** 16 occurrences / 24 nodes across landing, community, wiki
  and detail (`moderate`). **Landmark coverage:** 11 occurrences / 11 `.fixed`
  nodes across bills/results/detail (`moderate`). Both remain open.
- **P2 follow-up: detail SVG image alternative:** `svg-img-alt` is `serious`,
  two occurrences / two nodes at 390px, targeting `svg[height="200"]`.
- **Static language semantics:** requested EN does not update the observed HTML
  language in this run. This requires its own scoped fix and validation.

Totals: 24 cases / 59 rule occurrences / 162 nodes. Incomplete contrast checks
affect two landing nodes and ten detail nodes; these need manual assessment.

## Candidate evidence

Six local states cover EL→EN→EL at both widths: actual accessible names match,
focus succeeds, no overflow and zero `select-name` violations; externals blocked.
Root reports 325 Python docs tests OK (two optional skips, 17.974s), plus 116/116
Node checks on v24.19.0 (no skips, 10.09s); exact CI Node 22.23.3 remains a gate.
No gate exception, R0 or script-pin change. This candidate is not production.

## Remaining validation

Data-ready and fallback states, modal states, complete keyboard/focus behavior,
screen-reader behavior, devices and WebKit remain **needs-validation**.
No production deployment, provider mutation, newsletter submission, vote,
identity action or release was performed by the audit. Keep findings open until
their specific candidate and, where relevant, deployed flows are verified.

## T-9047 / T-9048 bundled candidate follow-up

The existing draft PR #534 includes the keyboard code-region fix and the safe
follow-ups; #533's subscriber-name change is already on main. This candidate
is **not deployed**. Static text colors are narrowly scoped; heading levels
preserve their visual styling; real QR SVGs have localized names. The global
SSE display is a named region, not a modal. Static EL/EN controls now also set
`document.documentElement.lang`. No data, API, money or navigation behavior changes.

Local evidence: `/private/tmp/T9048-local-axe.json` (Chromium 153.0.8010.12,
Playwright 1.63.0, axe 4.13.0). Six routes × EL/EN × 390/1280 = 24 HTTP-200
cases, zero reported axe violations, zero page errors, zero page overflow,
zero attempted writes and no language mismatches. API/SSE/QR data are synthetic
offline fixtures, not a production data or authentication check. Twelve
incomplete node checks remain for manual validation; full keyboard/modal,
screen-reader, real-device and deployed validation remain open. Quick Start
additionally passed EL→EN→EL, Tab/Shift-Tab, inset focus and scrolling in both
Chromium and WebKit, including the stabilized 650ms-after-focus rerun.

The initial fixture run exposed eight further detail contrast targets. Those
were fixed with darker text on light surfaces and lighter count labels on the
dark results surface; the final 24-case rerun passes. Initial source-test parsing
mistook a comment mentioning `<style>` for an element; HTMLParser now collects
real style elements without weakening color assertions. Local Render tests use
cached Vitest 4.1.11/jsdom 29.1.1; the local dev build uses Next 16.3.1 and Node
24.19.0. The exact lockfile matrix, full green head CI and gio-dd cross-review
remain mandatory merge gates. Immutable R0 and general preservation rules remain
unchanged; only the affected exact fingerprints and UTC sitemap hashes update.
