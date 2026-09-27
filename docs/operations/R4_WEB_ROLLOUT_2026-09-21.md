# R4 web production rollout receipt

Date: 2026-09-21

## Scope

This was the separately authorized Web-only production rollout of merged PR
#337 at commit `5a8d25cdb9674f9d580d212c649a9bb44d6e27c8`.

The release activates the already integrated R2 Landing design, the R3 Wiki
design, the R4 Community shell, the single responsive public-data header and
the bounded mobile chat containment correction. Existing Landing and Community
content, forms, scripts, links, API/storage contracts and external hosts remain
covered by the frozen R0 preservation gates.

No API, database, DNS, secret, IAM, Dashboard, forum, store, payment, provider,
mobile application or other service was changed.

## Preflight

- PR #337 was merged normally and post-merge CI run `35537949079` and Security
  Audit run `35537949175` passed.
- Remote `main` resolved to the exact target commit without changing the clean
  production checkout.
- The host had 20 GB free and no active project build was detected.
- The exact previous Web image was retained under the rollback tag below.
- Protected environment and base Compose hashes and every non-Web container
  identity, image, state, restart count and OOM state were recorded.
- The candidate was built from an exact archive of the merge commit and passed
  an isolated temporary-container check. All 21 target routes returned HTTP
  200, all static pages and R2/R3/R4 assets matched source byte-for-byte, and
  the candidate had zero restarts and was not OOM-killed.

## Rollout

- Candidate image:
  `ekklesia-web:r4-web-5a8d25c-20260920T235900Z`
- Rollback image:
  `ekklesia-web:rollback-pre-r4-web-5a8d25c-20260920T235900Z`
- Protected release directory:
  `/opt/ekklesia/releases/r4-web-5a8d25c-20260920T235900Z`
- The complete existing Compose override chain was preserved and extended by
  one image-only Web override.
- Only `ekklesia-web` was recreated with `--no-deps --no-build`.
- One transient HTTP 502 occurred during container replacement. The bounded
  readiness loop then succeeded and every subsequent probe passed.

## Acceptance

- Landing, Community, all 14 Wiki pages, five dynamic public-data routes and
  the R2/R3/R4 stylesheets returned HTTP 200.
- Landing, Community, all 14 Wiki pages and the three redesign stylesheets
  matched the staged target files byte-for-byte.
- Real Chrome checked all 21 pages at 360x800 and 1280x720. Neither viewport
  had document-level horizontal overflow, broken loaded images or a failed
  resource request.
- The mobile Landing chat stayed inside the viewport at `left=16`, `right=344`;
  desktop stayed inside at `left=881`, `right=1241`.
- Landing and Community each expose one redesigned header, one main landmark
  and one footer. Community loads the R4 stylesheet. Dynamic public-data pages
  expose the single consolidated global navigation.
- An additional live check in the in-app browser confirmed the new Landing,
  loaded images, one-line navigation and an in-viewport open chat panel.
- The Web container runs the candidate image with restart count zero and was
  not OOM-killed. Its logs contain no fatal, panic, unhandled or exception
  marker.
- API health passed. Every non-Web container retained the exact same ID, image,
  state, restart count and OOM state. Protected environment and base Compose
  hashes remained unchanged.

## Rollback

The exact prior Web image is retained under the rollback tag above, together
with an image-only rollback Compose override in the protected release
directory. A rollback would recreate only `ekklesia-web` through the preserved
Compose chain and repeat the same route and invariant checks.

No rollback was required.
