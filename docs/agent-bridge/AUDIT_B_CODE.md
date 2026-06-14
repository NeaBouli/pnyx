# AUDIT BLOCK B — Code Security & Architecture Audit

Date: 2026-05-23  
Agent: Codex  
Scope: `apps/api/routers/`, DB/Alembic consistency, monitor self-healing, repo hygiene, Arweave/privacy, ADR consistency.  
Mode: read-only product audit; this file is the only intended change.

## Executive Summary

Overall posture: improving, but not clean enough to call security-hard.

Strong points:
- Central admin dependency `verify_admin_key()` is fail-closed in production and rejects query-param admin keys.
- CORS is explicit, no wildcard origins.
- Main vote path in `voting.py` uses Ed25519 signatures and region scope checks.
- NEA-186b representative visibility now uses deterministic `periferia_id` FK matching, not fuzzy text.
- NEA-250 evaluation region-locking is applied only to POST submit/update, leaving public reads unaffected.
- Arweave MOD-08 currently publishes aggregate snapshots only; no individual votes or `nullifier_hash` in `build_audit_trail()`.
- Monitor has hardcoded T2 allowlist (`ekklesia-api`, `ekklesia-web`) and 2h forum-resync T1 cooldown.

Main risks:
- Some identity-adjacent endpoints still treat `nullifier_hash` or `public_key_hex` as sufficient authority without a fresh signature.
- Schema drift is acknowledged but still unresolved for fresh rebuilds.
- A few admin-namespaced finance/usage endpoints are public.
- Security audit CI soft-fails dependency audit commands.

---

## Findings

### [HIGH] [API Security] Discourse SSO callback does not prove key possession

Details: `POST /api/v1/sso/discourse/callback` accepts only `nonce` and `public_key_hex`, then looks up an active `IdentityRecord` and issues a Discourse SSO payload. There is no Ed25519 challenge/signature proof in the callback. Possession of a known public key is enough to complete SSO for that identity during a live nonce window. The callback also uses `identity.nullifier_hash` as Discourse `external_id`, plus derived username/email.

File: `apps/api/routers/sso.py:76-146`

Recommendation: Require a signed challenge in the callback, matching the QR pattern in `polis_qr.py`: store a challenge with the nonce, require `signature_hex`, verify with `public_key_hex`, then build the Discourse payload. Consider deriving `external_id` as `HMAC(FORUM_SSO_SALT, nullifier_hash)` rather than raw nullifier hash.

### [HIGH] [API Security] Municipal Diavgeia vote endpoint accepts nullifier without signature

Details: `POST /api/v1/municipal/vote` accepts `ada`, `nullifier_hash`, and `vote`; it verifies only that the nullifier belongs to an active identity and matches the decision `dimos_id`. Unlike the main parliamentary vote path, there is no Ed25519 signature over the vote payload. Anyone who obtains a valid nullifier can cast a municipal vote for that identity.

File: `apps/api/routers/municipal.py:178-231`

Recommendation: Add `signature_hex` to `DecisionVoteRequest` and verify payload such as `municipal:{ada}:{vote}:{nullifier_hash}` against `identity.public_key_hex` before duplicate check/insert. Keep the existing dimos scope check.

### [MEDIUM] [API Security] Relevance signal endpoint accepts nullifier without signature

Details: `POST /api/v1/votes/{bill_id}/relevance` accepts `nullifier_hash` and `signal`; it verifies identity existence but not possession of the private key. This is lower-impact than a content vote, but it can alter relevance/citizen-priority signals for any leaked nullifier.

File: `apps/api/routers/voting.py:116-119`, `apps/api/routers/voting.py:525-565`

Recommendation: Add `signature_hex` to `RelevanceRequest` and verify a stable payload like `relevance:{bill_id}:{signal}:{nullifier_hash}`.

### [MEDIUM] [Privacy] Personal receipt and compass endpoints use nullifier as bearer secret

Details: `GET /api/v1/votes/{bill_id}/receipt` returns full `nullifier_hash`, vote choice, timestamp, and HMAC receipt based solely on `X-Nullifier`. `GET /api/v1/votes/compass/personal` returns personal CPLM history based solely on `X-Nullifier`. If a nullifier leaks via client logs, screenshots, QR/browser flows, or forum SSO coupling, these endpoints expose personal vote/position history without a fresh signature.

File: `apps/api/routers/voting.py:570-609`, `apps/api/routers/voting.py:702-727`

Recommendation: Require signed read receipts for personal endpoints, e.g. `receipt:{bill_id}:{nullifier_hash}:{nonce}` and `compass:{nullifier_hash}:{nonce}`. At minimum, stop returning the full nullifier in receipt responses.

### [MEDIUM] [API Security] Admin-namespaced finance endpoints lack admin auth

Details: Three endpoints under `/api/v1/payments/admin/finance/*` are publicly callable despite the `admin` path segment. `server_costs()` can call Hetzner and returns server name/type/cores/RAM/disk/status/location/monthly EUR and public IPv4. BTC/LTC endpoints return address balances and tx counts. `/admin/finance/overview` is protected, but the component endpoints are not.

File: `apps/api/routers/payments.py:424-523`

Recommendation: Add `Depends(verify_admin_key)` to `/admin/finance/server`, `/admin/finance/btc`, and `/admin/finance/ltc`, or move them under clearly public transparency paths with intentionally reduced fields. Avoid exposing Hetzner server inventory publicly.

### [MEDIUM] [Database Schema] Alembic history still does not reproduce production schema

Details: `SCHEMA_DRIFT_NOTES.md` documents that migration `b501c2d3e4f5_mod16_municipal.py` creates `decisions.id` as `String(60)`, while production DB and SQLAlchemy model use `Integer`. It also states local `alembic upgrade head` produces the wrong schema. Recent NEA-242/NEA-186b columns were added by server SQL/raw-table paths and are not represented in Alembic migration history. Fresh DB rebuilds remain unsafe.

File: `apps/api/alembic/SCHEMA_DRIFT_NOTES.md:1-71`, `apps/api/routers/representative.py:104-240`, `apps/api/models.py:491-498`

Recommendation: Create a new schema-baseline ADR and migration plan. Either reset Alembic baseline from current production schema or add corrective migrations for drift and recent raw-table additions (`audit_log`, `identity_records.source`, `representative_tokens.periferia_id/dimos_id`, `rep_invitations.periferia_id/dimos_id`, municipality/source additions). Do not rely on manual server SQL for future reproducibility.

### [MEDIUM] [CI / Repository Hygiene] Security audit workflow soft-fails dependency audits

Details: `security-audit.yml` runs `npm audit`, `cargo audit`, and `pip-audit` with `|| true`, so high-severity dependency findings will not fail CI. It also only checks root `package.json` for npm audit, missing `apps/web/package.json`, `apps/dashboard/package.json`, `apps/mobile/package.json`, etc. GitHub Dependabot Alerts API returned disabled/403 for this repo during audit.

File: `.github/workflows/security-audit.yml:41-73`

Recommendation: Make high/critical dependency audit findings fail CI at least on PRs to `main`. Audit all package manifests in the monorepo, not just root. Enable Dependabot alerts or document why they are intentionally unavailable.

### [LOW] [API Abuse] Public API key generation has no explicit endpoint-level rate limit

Details: `POST /api/v1/public/keys/generate` creates Redis-stored API keys without using `rate_limit_check`. The app has SlowAPI configured, but this endpoint does not use the explicit public API limiter used by data endpoints. A client can create many API keys and then use each key as its own `identifier` in the in-memory limiter.

File: `apps/api/routers/public_api.py:60-112`

Recommendation: Add a Redis-backed creation cooldown per IP and/or per prefix, and rate-limit by real client IP even when an API key is supplied. Consider admin approval or short-lived research keys if abuse appears.

### [INFO] [Documentation / Repository Hygiene] Root README and CLAUDE.md are stale

Details: README still references Next.js 14, Hetzner CX33, modules count `22` in the Status table, API tests `106 passed`, GitHub Release `v1.0.0`, and F-Droid MR `#37087`. Current bridge state references Next 16, CX43, 25 modules, vC27, and F-Droid MR `!38007`. Root `CLAUDE.md` is a generic master audit prompt rather than current pnyx project context (`v10.0`, 25 modules, current endpoints).

File: `README.md:55-115`, `README.md:130-160`, `CLAUDE.md:1-30`

Recommendation: Update README/CLAUDE in a docs-only pass after security fixes. Keep public claims aligned with bridge/ADR state, especially NEA-249 as Proposed/Blocked rather than in-build.

---

## Section Notes

### B1 API Security

Admin protection is generally good for `apps/api/routers/admin.py`, `scraper.py` mutating imports, `diavgeia.py` admin routes, `notify.py` send, `notifications.py` test publish, `representative.py` invite management, and `admin_account.py`. The highest concern is not SQL injection; most raw SQL uses bound parameters. The recurring weakness is identity proof on endpoints that accept `nullifier_hash`/`public_key_hex` without a fresh Ed25519 signature.

CORS is explicit in `apps/api/main.py:525-537`. Docs/OpenAPI are disabled in production. Error handling uses `HTTPException` for expected cases; no obvious stack-trace response path found in reviewed routers.

### B2 Database Schema Consistency

Indexes exist for core vote paths (`identity_records.nullifier_hash`, `citizen_votes.nullifier_hash`, `citizen_votes.bill_id`, evaluation unique constraints). The biggest risk is migration reproducibility, not runtime query performance. Reserved SQLAlchemy attribute `metadata` has been fixed in model code via `details = Column("metadata", JSONB, ...)`.

### B3 Monitor & Self-Healing

Monitor contains 15 checks in `run_checks()`. T1 has Redis locks; forum resync has 2h TTL. T2 has hardcoded allowlist and max restart count. ADMIN_KEY is used only as a header and not logged. Lifecycle stuck alerts have per-bill alert cooldown. Remaining design note: direct-T3 alerts without recovery can still notify every monitor interval for some alert types; acceptable but noisy if a non-recoverable condition persists.

### B4 GitHub Repository Hygiene

Open PRs: only Dependabot PR `#67` (`recharts` 2.15.4 -> 3.8.1) is open. Dependabot alerts are disabled/403 through GitHub API. `.gitignore` covers `.env`, production env, Arweave wallets, JWK, Play keystore, build outputs and node/python caches. Current working tree has unrelated local dirty/untracked files not touched by this audit.

### B5 Arweave & Privacy

`build_audit_trail()` publishes bill metadata, lifecycle status logs, party votes, aggregate citizen vote counts, divergence score and parliament result. It does not include individual votes, `nullifier_hash`, phone numbers, public keys, or signatures. Note: `governance_level` and Arweave tag are currently hardcoded to `NATIONAL`; this is a data-quality issue for DIAVGEIA/regional records, not a privacy leak.

### B6 ADR Consistency

Only one ADR file exists: `docs/adr/NEA-249-zk-voting-v2-semaphore-hybrid.md`. Status remains non-production for global users: Android proving works on S10 and GH#112 hidden canary passed end-to-end, but production ZK flags remain off. Global rollout is gated on security review, Arweave/publication policy for public verifier payloads, tally/UI policy, and staged release.
