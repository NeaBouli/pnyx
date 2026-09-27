# R9 landing divider Web-only rollout receipt

Date: 2026-09-24

## Scope and source

- Owner approved the live switch after PR #358 was merged normally as
  `144ab14daccbb656a737f7f639700833f498dca5`. Required PR checks,
  CodeRabbit review, post-merge CI and Security Audit passed.
- Only the landing verification band's background and bottom section divider
  changed. The public CSS is the exact file from the merge commit, SHA-256
  `ce55b33ff7e94d233a622fe8b0612a3137de3e4d49374da0a86ae4bd9dcc26b9`.
  No copy, data binding, API, Wiki content or other Web asset was edited.

## Build and rollback

- Before the build, the shared host had 19 GB free and no active build. A
  single-file overlay was built on the running R8b Web image, preserving its
  previously released audit content and the existing Compose configuration.
- Candidate: `ekklesia-web:r9-divider-144ab14-20260924T203955Z`, image ID
  `sha256:b59ca3ded4a679e848e98de90460617c4c515ff145eb5f92aa59a5f764ad46b1`.
- Exact previous image retained as
  `ekklesia-web:rollback-pre-r9-divider-20260924T203955Z`, image ID
  `sha256:96abd2651127bb9f76f60c7902d7b79a61c65140cd798229158dde336406f7a0`.
- Protected release directory:
  `/opt/ekklesia/releases/r9-divider-144ab14-20260924T203955Z`. It contains
  the exact CSS, image build recipe, candidate and rollback overrides, and a
  bounded Web-only switch script. All 19 existing Compose files were kept;
  only `web` was recreated with `--no-deps --no-build`.

## Verification

- Before rollout: 180 redesign tests passed locally. The candidate's CSS
  matched the merge commit hash, and an isolated Web canary returned HTTP 200
  for Landing, both language routes, Community, Results, audit and CSS.
- After rollout: public Landing, both language routes, Community, Results,
  Bills, Wiki, audit and CSS returned HTTP 200. The legacy download redirect
  reached its existing APK asset with HTTP 200 via HEAD; no APK was changed.
- Live Chromium at 1280, 840 and 360 px confirmed white verification
  background, a dark 2 px bottom divider, no horizontal overflow or page
  errors. The disclosure started closed and opened on click at 1280 and
  360 px. API health returned HTTP 200.
- The Web container uses the candidate image with zero restarts and no OOM or
  matching error log. Non-Web container identities and protected environment
  and base Compose hashes were unchanged. No rollback was needed.

## Boundary

No API, database, DNS, IAM, secret, mobile, store, payment, provider or other
service was changed. The separate representative APK alias and Democracy
Cycle findings remain outside this layout fix.
