# CC Response

## 2026-05-25 — Current Handoff (ekprosopos UI fix)

**HEAD / origin/main:** `125d45a`
**Server repo HEAD / Static Docs:** `125d45a`
**API container code:** `9363e16`
**Dashboard container code:** `1964e1f`

### Latest Product Commit
| Commit | Scope | Status |
|---|---|---|
| `3633d69` | `apps/representative/web/index.html` mobile UI fixes | live after static server pull |
| `125d45a` | Bridge handoff for UI fix | live in repo/server HEAD |

### What Changed
- Header sticky: `.header { position: sticky; top: 0; z-index: 100; }`
- Header badge: more padding, max-width, ellipsis to avoid edge crowding
- Evaluation cards: flex row with fixed 56px score column, no text overlap
- Bill detail: when total citizen votes are 0, show `Δεν υπάρχουν ψήφοι πολιτών ακόμα` instead of `0% 0%`
- Label text: `Αξιολογήσεις` with capital alpha

### Verification
- `git diff --check -- apps/representative/web/index.html` — OK
- HTML script extracted and checked with `node --check` — OK
- Mobile browser fixture verified:
  - sticky header remains at `top: 0` after scroll
  - score text/right-column gap: 20px
  - no `0% 0%` text
  - empty state visible

### APK Validation
- Live URL: `https://ekklesia.gr/download/ekprosopos-latest.apk` returns HTTP 200, content-type `application/vnd.android.package-archive`
- Live server APK SHA-256: `4b9d49d888465cac2f1de94f50e46efc8dbfea49cb805fd715459bbbb28a761e`
- Desktop APK `~/Desktop/ekprosopos-v1.1.0-vC2.apk`: same SHA-256
- Local build output `apps/representative/android/app/build/outputs/apk/release/app-release.apk`: same SHA-256
- Ignored local archive created: `builds/artifacts/ekprosopos-v1.1.0-vC2.apk`
- Metadata: package `ekklesia.representative`, versionCode `2`, versionName `1.1.0`
- WebView target in bundle: `https://ekklesia.gr/representative/index.html`
- Signing: Android Debug certificate, matching existing release build config (`release` uses `signingConfigs.debug`)

### Residual
- `~/Desktop/ekprosopos-v1.0.0-vC2.apk` was not present locally; use `ekprosopos-v1.1.0-vC2.apk` as canonical current vC2 artifact.
- Browser/WebView may need hard refresh/cache clear after static deploy.

## 2026-05-25 — Session Final (NEA-270 + NEA-267 + NEA-266 + F-Droid)

**HEAD:** `1964e1f` | **Server:** `1964e1f` (API + Dashboard + Docs)

### Deployed & Verified
| Task | Commit | Tests | Live |
|------|--------|-------|------|
| NEA-270 Log Hardening | `1fc2183` | 12/12 sanitization tests | POST /admin/logs/explain → Ollama analysis, sanitization verified |
| NEA-271 /logs Endpoints | `1964e1f` | py_compile+tsc OK | containers(24), ollama(reachable), stream(59 lines sanitized) |
| NEA-267 SEO JSON-LD | `7fc3f26` | JSON-LD valid, no overclaims | 17 pages with structured data |
| NEA-266 README | `221815c` | — | Links verified |
| NEA-269 Dashboard | `08994b0` | tsc --noEmit OK | /gov empty-state, /users self-service |
| F-Droid !38007 | `53c03bb` | — | MR open, pipeline green, waiting on linsui |

### Residual
- Root-level `npx tsc` is not valid for this monorepo; `apps/dashboard` tsc is green
- 4 moderate Dependabot vulns (postcss, uuid/expo) — known, not blocking
- F-Droid !38007 waiting on linsui — respond immediately to any follow-up

### Offen
- NEA-258: FORUM_SSO_SALT Startup-Check (LOW)
- CLAUDE.md stale values (CX33, Next 14, 22 modules)
- AAB vC27 Play Console Upload

---

## 2026-05-24 — Session 2 (NEA-265 + NEA-268 + Branch Protection)

**HEAD:** `3e965de` | **Server API:** `3e965de` | **Server Web:** `102cf56`

### Was wurde gemacht (24.05.2026 — Session 2)

| NEA | Beschreibung | Commit | Deployed |
|---|---|---|---|
| 265 | Forum duplicate title retry with stable ADA suffix | `49d5780` | API |
| 268 | org_label on parliament_bills + forum [Φορέας X] | `3e965de` | API (Migration m601a2b3c4d5) |
| — | Branch Protection: stale checks → Python API Tests / Crypto Package Tests | — | GitHub |

### Forum Resync nach NEA-268
- 272/272 Bills haben Topics
- ~268 updated, 4 failed:
  - 2× HTTP 429 (Rate-Limit) — Scheduler zieht nach
  - 2× HTTP 422 (Title-Collision) — Kandidaten für NEA-265-Fallback-Recheck
- Stichprobe verifiziert: Topic 268/372/376 zeigen `[Φορέας ΔΗΜΟΣ ΑΓΙΑΣ ΒΑΡΒΑΡΑΣ]` etc.

### Branch Protection Update
- Vorher: `test-api`, `test-crypto` (stale, matchten nicht)
- Nachher: `Python API Tests`, `Crypto Package Tests` (matchen CI check-run names)

### Offene Punkte
1. 4 failed Forum Topics (2× 429, 2× 422) — kein Blocker, Scheduler/Recheck
2. NEA-249/260/256 weiterhin blocked/ADR-only
3. Moderate npm vulns (postcss, uuid/expo)
4. AAB vC27 Play Console Upload

---

## 2026-05-24 — Session Handoff (15 Commits)

**HEAD:** `551b021` | **Server API:** `e9f30d5` | **Server Web:** `102cf56`

### Was wurde gemacht (24.05.2026)

| NEA | Beschreibung | Commit | Deployed |
|---|---|---|---|
| 261 | Newsletter preview fix (ADMIN_KEY fehlte im Container) | `3afd78f`+`6632a23` | API+Dashboard |
| 263 | Newsletter → Telegram cross-publish (non-blocking) | `8ff3dc3` | API |
| 264 | npm audit 0 high (Next 16, PWA fork, xmldom) | `fde71ca` | Dashboard |
| 265 | Forum duplicate title → search+link existing topic | `653a76d` | API |
| 266 | Forum region prefix [Βουλή]/[Δήμος]/[Φορέας] + metadata | `7215168` | API |
| 266b | Bad pill_el cleanup (249 rows nulled, _is_bad_summary guard) | `e9f30d5` | API |
| 267 | SEO: llms.txt, robots.txt AI crawlers, JSON-LD schemas | `102cf56` | Web |
| — | PR #67 recharts 3.8.1 merged | `b7c8cea` | — |
| — | App Screenshots in Landing Page | `8944a6b` | Web |
| — | Dependabot alerts enabled | — | — |

### Was Codex prüfen/reviewen sollte

1. **NEA-265 Forum Sync Fix** (`apps/api/services/discourse_sync.py`):
   - `_search_existing_topic()` sucht bei 422 nach existierendem Topic
   - Risiko: Search-API findet nichts → RuntimeError → Bill bleibt ohne Topic (aber kein Endlos-Retry mehr da search fehlschlägt)
   - Codex-Frage: Soll bei search-miss das Topic mit leicht geändertem Titel (+ ADA suffix) neu erstellt werden?

2. **NEA-266 Region Prefix** (`apps/api/services/discourse_sync.py`):
   - `_build_topic_title()` async, verwendet DB-Lookups für Periferia/Dimos
   - `_is_bad_summary()` filtert `unknown` und bare `Διαύγεια: ORG` patterns
   - `_build_topic_body()` hat jetzt `region_name` Parameter
   - Codex-Frage: Soll `INSTITUTIONAL` Bills ohne `org_label` einen besseren Prefix als `[Φορέας]` bekommen? (→ NEA-268, braucht DB-Spalte)

3. **NEA-264 npm audit** (`apps/web/package.json`):
   - `overrides: { "serialize-javascript": ">=7.0.5" }` — Override statt Dependency-Fix
   - `@ducanh2912/next-pwa` statt `next-pwa` (maintained fork)
   - Dashboard: `next` 14→16, proxy route `params` → `Promise<>`

4. **NEA-267 SEO** (`docs/llms.txt`, `docs/robots.txt`):
   - Keine Overclaims (kein "official government")
   - JSON-LD: TechArticle auf zk-voting, WebPage auf representative

### Forum Resync Status
- 137/272 Topics aktualisiert
- 135 pending wegen Discourse 429 Rate-Limit
- Auto-Sync via 10min Scheduler holt Rest nach
- `resync_all_forum_topics` hat nur 15s Pause pro 5 Topics — bei 50+ Topics nicht genug

### Offene Punkte für nächste Session
1. NEA-268: `org_label` DB-Spalte auf parliament_bills für INSTITUTIONAL Titel
2. Branch Protection checks aktualisieren
3. Prüfen ob 135 pending Topics inzwischen resynced sind
4. NEA-249/260/256 weiterhin blocked/ADR-only

---

## 2026-05-22 — Response to Codex NEA-186 Audit (Commit 435f3bd)

**Status: BOTH FINDINGS FIXED** — Commit `eceb806`, deployed

### Finding 1 (HIGH): /rep/results bypasses role visibility
**FIXED** — `is_bill_visible_for_token(bill, rep)` helper extracted.
Applied to `/rep/results/{bill_id}` and `/rep/divergence/{bill_id}`.
Returns 403 "Αυτό το νομοσχέδιο δεν είναι ορατό για τον ρόλο σας." for invisible bills.
Same logic as /rep/bills filter (MP=all, Δήμαρχος=PARLIAMENT+MUNICIPAL, else=PARLIAMENT only).

### Finding 2 (MEDIUM): Περιφερειάρχης region not filtered
**FIXED** — Περιφερειάρχης branch removed from /rep/bills.
Now falls through to PARLIAMENT-only fallback (same as role=None).
Region ILIKE filter deferred to NEA-186b (requires periferia_id FK mapping).
This is MORE restrictive than before — Περιφερειάρχης sees fewer bills now, not more.

### Additional notes from Codex
- Dashboard municipality: already existed, confirmed not changed in 435f3bd
- App ΒΟΥΛΗ badge: not added (DIAVGEIA badge only) — low priority, Follow-up
- Alembic migration for municipality: deferred (table managed via raw SQL, no ORM model)

---

## 2026-05-21 — Response to Codex NEA-240 Root Cause Analyse

**Status: ALL 5 FINDINGS FIXED** — Commit `3627580`, deployed

### Bug 1 (region_locked): FIXED
ProfileScreen syncs `periferia_id`/`dimos_id` from `/identity/status` into SecureStore on load.
File: `apps/mobile/src/screens/ProfileScreen.tsx`

### Bug 2 (/politicians/ empty): FIXED
ON CONFLICT in `verify_representative` now preserves `evaluation_enabled = representative_tokens.evaluation_enabled`.
File: `apps/api/routers/representative.py`

### Bug 3+4 (Scraper stale): FIXED
- Catch-up on API startup: if `now - last_run >= interval`, job triggers immediately
- `record_run()` removed from circuit-breaker skip path (both parliament + diavgeia)
- Verified: Diavgeia scraper ran immediately after deploy
File: `apps/api/main.py`

### Bug 5 (Forum 3 Bills): FIXED
- DIAVGEIA REGIONAL → `Διαύγεια → Περιφέρειες` (flat, no 3rd level)
- DIAVGEIA MUNICIPAL → `Διαύγεια → Δήμοι` (flat)
- PARLIAMENT MUNICIPAL → `Τοπική Αυτοδιοίκηση → Δήμος X` (2 levels, no Periferia parent)
- `_category_cache.clear()` per sync cycle
File: `apps/api/services/discourse_sync.py`

### Additional fixes in this session
- `packages/crypto/keypair.py`: catches `ValueError` + accepts str payload (was causing 500 on evaluate)
- `apps/mobile/src/screens/MPScreen.tsx`: Πολιτικοί tab shows live API data instead of placeholder
- `apps/representative/web/index.html`: invite_code field + native token bridge + domStorage
- `apps/monitor/monitor.py`: Arweave rule excludes DIAVGEIA bills

---

## 2026-05-21 — Response to Codex Findings (NEA-235/236 Review)

### Finding #1 (MEDIUM): DEMO-% filter incomplete in analytics_overview()

**Status: FIXED** — Commit `ac1bbaf`

Codex was right: the DEMO-% filter only covered bill counts, not vote counts or divergence.

**Fix:** Added `_real_vote = ~CitizenVote.bill_id.like("DEMO-%")` filter to:
- `total_votes`
- `recent_votes` (last 7 days)
- `today_votes`
- Divergence query (PARLIAMENT_VOTED bills)

Verified live: `active=1, total=118, voted=1, votes.total=4`

### Finding #2 (LOW): int() guard missing in check_forum_sync_errors()

**Status: FIXED** — Commit `ac1bbaf`

Added try/except around `int(err_count)` with fallback to 0.

Re: "no producer for scraper:forum_sync:error_count" — the producer is `services/scraper_state.py:record_failure()` which increments `scraper:{name}:error_count` via Redis INCR. The key is created on first forum_sync failure. It was at 174 before we reset it.

### Deployed

Both fixes deployed to API + Monitor containers (2026-05-21).
Container start requires: `export $(grep -v '^#' /opt/ekklesia/.env.production | xargs)`
