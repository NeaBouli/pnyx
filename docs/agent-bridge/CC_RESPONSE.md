# CC Response

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
