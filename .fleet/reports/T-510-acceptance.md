id: T-510-acceptance
status: ok
worker: codex
branch: agent/codex/T-510-397-integration
summary: Lead acceptance of EKA-24 after correcting the architecture map and the first review's #397 integration blocker. Final code head 5390412d removes the server-salt-accepting product export and keeps both legacy and EKA-22 derivation strictly test-local. Exact #397 is an ancestor and its non-Web files are unchanged.
files: mapped architecture/report artefacts; apps/web/src/lib/crypto.ts; apps/web/src/lib/crypto.test.ts; apps/web/src/lib/crypto-kat.test.ts; T-510 implementation/review reports
tests: npm ci -> 0 vulnerabilities; repo-pinned Node 22.13.0 combined crypto suites -> 32 passed; typecheck -> pass; production build -> pass; source/build searches -> 0 forbidden hits; diff-check -> pass; independent review -> ok.
risks: Stacked on #397 and must not merge first. After #397 merges, rebase and prove the final post-base delta again. No browser/live verification because no rendered runtime flow changed.
security: EKA-24 invariant satisfied in the local candidate; no secret, KDF, key storage, fixture/vector, API/Mobile/packages, dependency, config, data, production or deployment change.
next: Keep local and unpublished. If publication capacity is later opened, create only a Draft with explicit #397 dependency and no CodeRabbit request; enter the serial review queue only after earlier PRs and an allowance reset.
