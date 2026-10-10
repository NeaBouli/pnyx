# CI

Workflows: `.github/workflows/ci.yml` (tests and client builds) and `security-audit.yml`
(secret scan, dependency audit). `deploy.yml` is `workflow_dispatch` only and never runs on
the fallback runner. `scraper.yml` is a scheduled data job and is not part of CI.
`t356-browser.yml` is an additional, manually dispatched static-docs browser gate.

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
| T-356 Browser Gate | yes, manual only | browser binaries are installed without sudo; required system libraries must already exist |
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

The Dashboard Client job runs `node --test` on `apps/dashboard/health-shapes.test.mjs`
and `apps/dashboard/overview.test.mjs` (plus the image-codec and client-YAML checks).
They transpile the real `src/lib` sources and cover health payload normalization and the
overview source contract: HLR unavailable vs. zero, initial capacity, timeout cleanup,
bad responses/JSON and hanging-body abort. They do not cover responsive UI, browser or
live verification; those remain separate gates.

## Manual T-356 browser gate

Dispatch `.github/workflows/t356-browser.yml` with `mode: data-only` (the default)
or `mode: full`. The workflow accepts only `refs/heads/main` and task branches matching
`refs/heads/agent/(codex|claude|kimi)/T-[0-9]+`. It has no pull-request trigger or
separate user-supplied checkout ref. This browser run supplements the existing Docs
Redesign Gates; it does not replace their standard-library checks.

The workflow installs the isolated toolchain in `scripts/redesign/browser-tooling`
with `npm ci --ignore-scripts --no-audit --no-fund`. The manifest and lock pin
Playwright and its `playwright-core` dependency to `1.63.0`; browser downloads use
that installed package's CLI. `PLAYWRIGHT_MODULE` explicitly points to its absolute
`node_modules/playwright` directory. Node follows `.nvmrc`; checkout, setup-node and
upload-artifact use full action commit SHAs. Checkout disables persisted credentials
and the workflow token has only `contents: read` permission.
Installation follows the [official Playwright CI guidance](https://playwright.dev/docs/ci);
this custom harness is then run directly, not through Playwright Test.

The harness is executed directly with Node, rather than `playwright test`:
`scripts/redesign/t356_democracy_cycle.browser.cjs`. Both modes use Chromium and
WebKit. `data-only` covers positive and empty Rep/CPLM cases at 1440px
and 390px; `full` also covers the democracy cycle at 1440, 840, 390 and 360px,
reduced motion and error states. It serves `docs/` on loopback, mocks backend
responses and blocks other external page requests. Browser and npm installation
still require their download services; the harness does not use production data.

The job follows `CI_RUNNER` and has a 15-minute limit in `data-only` mode and a
20-minute limit in `full` mode. The harness has an additional 8-minute limit in
`data-only` mode and 12-minute limit in `full` mode. Hosted runners
install Chromium/WebKit with their system dependencies (`--with-deps`). The fallback
runner installs only browser binaries, without sudo or package-manager changes.
Its required Chromium/WebKit system libraries are an external prerequisite;
this workflow does not provision or certify them. A missing library must fail the
run rather than silently skip an engine.

Before the harness starts, the workflow verifies the installed Playwright version
against the lock and checks that both browser executables exist. It makes the local
`docs/` and `scripts/redesign/` checkout read-only for the harness and launches it
with a cleared environment containing only its executable and browser paths.
An always-run step restores checkout owner write permission afterward so a later
fallback job is not left with an unwritable workspace; it deletes no files.

The setup log records npm and browser installation failures. The harness log
includes its preflight checks and preserves assertion failures, exceptions and timeout exits
(`1`, `2` and `124`). A forced termination after the timeout grace period can
instead return `137`. Evidence validation runs even after a failed harness step and
rejects missing or malformed `results.json`, inconsistent counts and missing engine
evidence. `setup.log`, `harness.log`, `results.json` and PNG screenshots are uploaded on success or failure
with three-day retention; an early failure may produce only logs. The Python
contract tests in `scripts/redesign/test_t356_browser_workflow.py` run through the
existing Docs job and need no browser installation.

Adding this workflow and passing its static contracts does not prove a GitHub Actions
browser run. Cold/warm hosted or fallback dispatches must be recorded separately;
no such dispatch or fallback library provisioning is claimed by this change.

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
