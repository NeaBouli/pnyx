id: T-510-review
verdict: ok
reviewer: independent Codex explorer after Kimi/Claude dispatcher unavailability
scope: cde455cc..5390412d on agent/codex/T-510-397-integration
summary: The first review correctly blocked the plain-main patch because exact #397 imported `computeNullifier`. The corrected candidate is based on #397 head 399b4250; `crypto-kat.test.ts` now derives v1 nullifiers privately while retaining the exact fixture assertion. No production Web source/build contains the helper or serverSalt.
files: apps/web/src/lib/crypto.ts; apps/web/src/lib/crypto.test.ts; apps/web/src/lib/crypto-kat.test.ts; .fleet/reports/T-510.md
tests: independently reproduced combined Web crypto suites 32/32, typecheck, production build and diff-check; production-source/build marker searches returned zero hits.
risks: Candidate is stacked and requires fresh post-#397 merge/base proof before any review or merge. No other actionable finding.
security: invariant satisfied; derivation exists only in tests and all non-Web EKA-22 files are byte-identical to #397.
