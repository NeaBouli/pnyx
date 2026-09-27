# R5 Landing production rollout receipt

Date: 2026-09-21

## Scope

This was the separately authorized Web-only production rollout of merged PR
#339 at commit `9d9e0c2d992844eba6c0acd8531b598a810ae0d5`.

The release brings the public Landing page into structural and visual parity
with the approved design handoff while preserving the existing public copy,
forms, links, downloads, language behavior, live-data contracts and scripts.
No API, database, DNS, secret, IAM, Wiki, Community, Dashboard, forum, mobile
application, store, payment, provider or other service was changed.

## Integration gates

- PR #339 was merged normally after all required and optional CI/Security jobs
  passed. The post-merge CI run `35573024283` and Security Audit run
  `35573024351` also passed completely.
- The local parser-backed R5 validator passed, all 134 redesign tests passed,
  `git diff --check` was clean and the redacted Gitleaks scan found no leaks.
- CodeRabbit's five inline findings and one Tier 3 data-integrity finding were
  fixed before merge. Claude's independent read-only review returned
  `APPROVE` with no blocker.

## Preflight and build

- The host had 20 GB free and no active project build was detected.
- The candidate was built from an exact archive of the merged commit; hashes
  for `docs/index.html` and the R5 stylesheet matched the Git object.
- Candidate image:
  `ekklesia-web:r5-landing-9d9e0c2-20260921T073213Z`
- Rollback image:
  `ekklesia-web:rollback-pre-r5-landing-20260921T073213Z`
- Protected release directory:
  `/opt/ekklesia/releases/r5-landing-9d9e0c2-20260921T073213Z`
- An isolated temporary container returned HTTP 200 for all 21 acceptance
  routes. Its Landing and R5 stylesheet matched source byte-for-byte; it had
  zero restarts and was not OOM-killed.

## Rollout

- The complete existing Compose override chain was preserved and extended by
  one image-only Web override.
- Only `ekklesia-web` was recreated with `--no-deps --no-build`.
- The first readiness command used `curl | grep -q` under `pipefail`. The
  early-closing `grep` made `curl` return a write error even though the
  candidate was healthy, so the fail-closed guard automatically restored the
  rollback image. No non-Web service was changed.
- The same already verified candidate was then recreated with a corrected
  file-based readiness check. One transient HTTP 502 occurred during the
  container replacement; the bounded readiness loop then succeeded.

## Live acceptance

- Landing, Community, all 14 Wiki pages and five dynamic public-data routes
  returned HTTP 200.
- Live Landing HTML and the R5 stylesheet matched the merged source files
  byte-for-byte.
- Real-browser checks passed at 1440 x 1000 and 360 x 800. Both viewports had
  no document-level horizontal overflow and no broken loaded images.
- Desktop navigation stayed on one line; the Forum grid rendered four columns
  on desktop and one column on mobile. The opened mobile chat panel stayed
  inside the viewport at `left=16`, `right=329`.
- The R5 stylesheet was loaded, Tier 3 correctly remained `-` when real
  representation data was unavailable, and browser error/warning logs were
  empty.
- The Web container runs the candidate image with zero restarts and was not
  OOM-killed. Its recent logs contain no fatal, panic, unhandled or exception
  marker.
- API health passed. Every non-Web container retained the same identity and
  image. Protected environment and base Compose hashes remained unchanged.

## Rollback

The exact prior Web image remains available under the rollback tag above,
together with an image-only rollback Compose override and the before/after
evidence in the protected release directory.

The final R5 rollout did not require rollback.
