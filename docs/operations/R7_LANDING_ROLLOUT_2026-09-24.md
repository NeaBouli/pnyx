# R7 Landing Web-only rollout receipt

Date: 2026-09-24

## Scope and source

- Owner-approved Web-only rollout of PR #351, merged normally as
  `3adb220b523e1f08f0d0b5476d25698c385d420f`.
- The landing owl is about 25% smaller, disclosure headings have one divider,
  and DOM/visual/keyboard order is hero, history, live representation and mood,
  votes, download, collapsed information sections, then newsletter.
- Existing Greek/English copy, data handlers, forms, links, downloads and
  default-closed disclosure behavior were preserved by the R0/R2 contract
  validator. The handler identity regression from CodeRabbit was resolved
  before merge.

## Gates and candidate

- 172 redesign tests, the preservation validator, `git diff --check` and a
  redacted Gitleaks diff scan passed locally. All PR checks passed. The
  post-merge CI run `35977875899` and Security Audit run `35977875850`
  passed for the exact merge commit. CodeRabbit's re-review was rate-limited,
  but its one actionable finding was fixed and regression-tested.
- The server had 20 GB free and no active project build. The exact merge
  archive was used for the Web build; its `docs/index.html` SHA-256 matched
  the Git object (`be5365aa...66c3901`).
- Candidate image: `ekklesia-web:r7-landing-3adb220-20260924T085827Z`.
- Rollback image: `ekklesia-web:rollback-pre-r7-landing-20260924T085827Z`,
  verified to match the pre-rollout Web image ID.
- Protected release directory:
  `/opt/ekklesia/releases/r7-landing-3adb220-20260924T085827Z`.
- The isolated Web canary returned HTTP 200 for 21 routes. Its landing HTML
  matched source byte-for-byte; restart count was 0 and OOM was false.
  Chromium at 360, 768 and 1280 px found the intended section order,
  39/45/60 px owl widths, ten closed disclosures, working `#how` navigation,
  no document overflow and no JavaScript exceptions.

## Rollout and live acceptance

- The existing Compose override chain was preserved and extended with an
  image-only Web override. Only `ekklesia-web` was recreated, using
  `--no-deps --no-build`; the canary was stopped after acceptance.
- Live landing HTML and R5 fidelity CSS match the exact merge source hashes.
  Landing, Community, all 14 Wiki pages and five dynamic Web routes returned
  HTTP 200. All 21 unique same-origin landing links returned 200 after their
  expected redirects, with no missing in-page anchors. Direct APK, Google
  Play testing, F-Droid and Forum destinations returned 200.
- Live Chromium at 360/768/1280 px confirmed the same section order, owl
  widths, ten default-closed disclosures, Wiki navigation, no overflow,
  working disclosure hash navigation and no JavaScript exceptions. Public
  bills, results and CPLM API calls returned 200; absent representation data
  stayed in its honest placeholder state. No real newsletter submission or
  payment was made.
- API health returned 200. Web had zero restarts, no OOM and no fatal/panic/
  unhandled/exception log markers. Every non-Web container retained its
  identity and image. Protected environment and base Compose hashes stayed
  unchanged. No API, database, DNS, secret, IAM, mobile, store, payment or
  other service was changed. No rollback was needed.

## Open findings

- The pre-existing analytics script is blocked by the current Web CSP in
  Chromium. This is associated with open audit item EKA-33: the public
  "0 Cookies / Trackers" claim and analytics treatment need a coordinated
  privacy/content decision before changing the CSP or script. This rollout
  did not alter either.
- The separate representative APK alias remains unpublished/404, as already
  recorded in the R6c receipt. It was not linked as an available binary here.
