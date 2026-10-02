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
| Docs Redesign Gates | yes | standard-library Python only |
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

Not covered: `deploy.yml` (manual `workflow_dispatch` deploy; changes there are deploy scope)
and `scraper.yml` (scheduled data job) still reference actions by tag.
