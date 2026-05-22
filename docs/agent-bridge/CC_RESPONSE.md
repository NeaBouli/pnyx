# CC Response

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
