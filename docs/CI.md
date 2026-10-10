# CI

Workflows: `.github/workflows/ci.yml` (tests and client builds) and `security-audit.yml`
(secret scan, dependency audit). `deploy.yml` is `workflow_dispatch` only and never runs on
the fallback runner. `scraper.yml` is a scheduled data job and is not part of CI.

## CI fallback
Linux jobs run on GitHub-hosted runners. When Actions minutes are exhausted, set the repo
variable `CI_RUNNER` to `["self-hosted","Linux","X64","pnyx-ci"]`
(or run `~/agent-fleet/bin/ci-switch.sh hetzner pnyx`). Delete the variable to switch back.
On the fallback runner, `sudo` is not available, the OS is Ubuntu 26.04, and it is Linux only.

Which jobs follow `CI_RUNNER`:

| Job | On fallback | Why |
|---|---|---|
| Crypto Package Tests | yes | the `apt-get` step is skipped there; the PyNaCl wheel bundles libsodium |
| Docs Redesign Gates | yes | standard-library Python and Node checks; no npm dependencies |
| Client Web/Dashboard/Mobile/Representative/Crypto-TS | yes | Node from `.nvmrc` via `setup-node` |
| Python API Tests | no, stays GitHub-hosted | needs the `redis` service container; pnyx has no Docker on the fallback host |
| Secret Detection, Dependency Audit, Security Summary | no, stays GitHub-hosted | rely on the toolchain of the hosted image |

Rules on the fallback runner: jobs that follow `CI_RUNNER` run there only for `push`,
`workflow_dispatch` or same-repo pull requests
(`github.event.pull_request.head.repo.full_name == github.repository`).

**Fork PRs while the fallback is active are not mergeable.** The fallback-capable jobs are
skipped for them, and a skipped job would otherwise look green. The GitHub-hosted job
`Fallback Fork Guard` therefore fails every fork PR while `CI_RUNNER` is set; re-run CI after
switching back (`ci-switch.sh github pnyx`). Every switch is recorded in
`docs/agent-bridge/ACTION_LOG.md`.

## Hardening (ci.yml and security-audit.yml)
- Third-party actions are pinned to full commit SHAs (version in a trailing comment).
- `actions/checkout` runs with `persist-credentials: false`.
- Every job has a `timeout-minutes` limit.
- Client jobs set `NPM_CONFIG_IGNORE_SCRIPTS=true`, because the root `.npmrc`
  (`ignore-scripts=true`) is not read inside `apps/*`.
- Workflow token permissions stay `contents: read`.

## Docs behavior checks

The Docs Redesign Gates job also runs `node --test scripts/public-seo.check.mjs
scripts/static-docs-remote-sinks.check.mjs scripts/redesign/community_payment_status.check.mjs`:
public SEO contracts, static-page remote sinks, and community payment-status behavior.
Node comes from `.nvmrc` through SHA-pinned `actions/setup-node`; these checks use only
the standard library and require no `npm install`. Within `ci.yml`, only the Docs job
uses `fetch-depth: 0`, so the SEO history comparisons have the complete Git history.
SEO and remote-sink checks additionally run in the Web Client job, whose checkout
remains shallow.

## Redis test-service image

The API job pulls the Docker Official Redis image anonymously from ECR Public,
avoiding Docker Hub's anonymous pull quota without adding registry credentials.
Docker documents this [official distribution mirror](https://www.docker.com/press-release/docker-official-images-available-amazon-elastic-container-registry/).

The service is pinned to the Redis `8.10.2-alpine` OCI index
`sha256:3811787313eba226a2ef38658c6ccb91cd5e110edc89c37767de373120a0e5a0`.
ECR manifest inspection and the [Docker Hub metadata](https://hub.docker.com/layers/library/redis/8.10.2-alpine/images/sha256-2d3814be5e9b06a30a0be54770b7e12052e7e79ec85271aefd34875c1f393b23)
matched on 2026-10-09, including the Linux/amd64 manifest
`sha256:2d3814be5e9b06a30a0be54770b7e12052e7e79ec85271aefd34875c1f393b23`.
This is an artifact-identity check, not a comparison with older local caches.

Future Redis updates must explicitly refresh the digest, verify the official-image
provenance, and pass the service healthcheck and API/real-Redis tests. ECR availability
and anonymous quotas remain external dependencies. Runner selection, ports,
healthcheck, workflow permissions and production Redis configuration are unchanged.

All 15 action references across `ci.yml`, `security-audit.yml`, `deploy.yml` and
`scraper.yml` are pinned to full commit SHAs as of PR #520. The deploy and scraper
changes were reference-only; the credentials, permissions and other hardening
claims above remain scoped to `ci.yml` and `security-audit.yml`.
