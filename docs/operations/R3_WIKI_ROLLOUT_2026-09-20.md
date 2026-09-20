# R3 wiki production rollout receipt

Date: 2026-09-20

## Scope

This was the separately authorized Web-only production rollout of merged PR
#335 at commit `b5000e76f2a5c6e87741d4613494845dcdb32112`.

The release changed only the 14 static wiki HTML files and these four local R3
assets inside the existing Web image:

- `tokens.css`
- `foundation.css`
- `r3-wiki.css`
- `r3-faq-accessibility.js`

No API, database, DNS, secret, IAM, Dashboard, forum, store, payment, provider
or other service was changed.

## Preflight

- PR #335 was merged normally and post-merge CI and Security Audit passed.
- The production checkout was clean. Remote `main` resolved to the exact target
  commit without changing the checkout or deploying unrelated source.
- The existing production Web image was retained as the immutable base.
- The server had 20 GB free and no active project build was detected.
- All protected environment and base Compose hashes were recorded.
- An initial candidate build using a bare image ID failed before any service
  switch because Docker treated it as a registry reference. Production stayed
  unchanged. The successful build used the existing local immutable image tag,
  after verifying that it resolved to the same image ID.
- The successful candidate passed an isolated temporary-container check: all
  14 wiki routes returned HTTP 200 and their response hashes matched the target
  commit byte-for-byte. The temporary container had zero restarts and was not
  OOM-killed.

## Rollout

- Candidate image:
  `ekklesia-web:r3-wiki-b5000e7-20260920T195518Z`
- Rollback image:
  `ekklesia-web:rollback-pre-r3-wiki-20260920T195518Z`
- Protected release directory:
  `/opt/ekklesia/releases/r3-wiki-b5000e7-20260920T195518Z`
- The existing Compose override chain was preserved and extended by one
  image-only Web override.
- Only `ekklesia-web` was force-recreated with `--no-deps --no-build`.
- One transient HTTP 502 occurred during container replacement. The bounded
  readiness loop then succeeded and no later probe failed.

## Acceptance

- All 14 public wiki HTML routes and all four R3 assets returned HTTP 200 and
  matched the staged target files byte-for-byte.
- Real Chrome checked all 14 pages at 1440x1000 and 360x800. All 28 combinations
  had one R3 header, one `main#main`, one R3 footer, three local R3 stylesheets,
  no broken images and no document-level horizontal overflow.
- `zk-voting.html` correctly retained its intentional no-hero layout; the other
  13 pages each retained one hero inside `main#main`.
- The live FAQ exposed 57 focusable button-semantic controls with valid linked
  answers. Enter opened the first item and Space closed it while
  `aria-expanded` stayed synchronized.
- The Web container runs the candidate image with restart count zero and was
  not OOM-killed.
- API health passed. Every non-Web container retained the same ID, image,
  running state, restart count and OOM state.
- Protected environment and base Compose hashes remained unchanged. The Web
  log scan found no fatal, panic, unhandled or exception marker.

## Rollback

The exact prior Web image is retained under the rollback tag above, together
with an image-only rollback Compose override in the protected release
directory. Rollback would recreate only `ekklesia-web` through the unchanged
Compose chain and repeat the same route and invariant checks.

No rollback was required.
