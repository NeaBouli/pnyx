<!--
@wiki-page API
@update-hint Update on new endpoints or changes. Keep the endpoint tables in sync with docs/wiki/api.html; apps/api/tests/test_wiki_api_reference.py checks both against the FastAPI OpenAPI schema.
@ai-anchor WIKI_API
-->

# API Documentation

Base URL: `https://api.ekklesia.gr/api/v1` (Production) | `http://localhost:8000/api/v1` (Dev)

Swagger UI: `http://localhost:8000/docs`

All paths below are relative to the base URL.

## MOD-01: Identity

| Method | Endpoint | Description |
|---|---|---|
| POST | `/identity/verify` | HLR Greek-number network-status check without SMS (not identity proof) → Ed25519 Keypair |
| POST | `/identity/revoke` | Revoke key |
| POST | `/identity/status` | Verification status (JSON body: `nullifier_hash`) |

## MOD-02: VAA

| Method | Endpoint | Description |
|---|---|---|
| GET | `/vaa/statements` | 38 positions (el/en) |
| GET | `/vaa/parties` | 8 parties |
| POST | `/vaa/match` | Matching algorithm |

## MOD-03: Parliament

| Method | Endpoint | Description |
|---|---|---|
| GET | `/bills` | All bills (filter, pagination) |
| GET | `/bills/{id}` | Detail + AI summaries |
| GET | `/bills/trending` | By relevance score |
| POST | `/bills/{id}/transition` | Lifecycle transition (admin) |
| POST | `/bills/admin/create` | Create new bill (admin) |

## MOD-04: CitizenVote

| Method | Endpoint | Description |
|---|---|---|
| POST | `/vote` | Submit vote (Ed25519 signed) |
| GET | `/vote/{id}/results` | Results + Divergence Score |
| POST | `/vote/{id}/relevance` | Up/Down signal |

## MOD-06: Analytics

| Method | Endpoint | Description |
|---|---|---|
| GET | `/analytics/overview` | Platform statistics |
| GET | `/analytics/divergence-trends` | Divergence trends over time |
| GET | `/analytics/top-divergence` | Top bills by divergence |
| GET | `/analytics/votes-timeline` | Voting timeline |
| GET | `/analytics/bill/{id}` | Analytics for one bill |
| GET | `/analytics/info` | Analytics endpoint docs |

## MOD-07: Notifications

| Method | Endpoint | Description |
|---|---|---|
| GET | `/notifications/status` | Notification system status |
| GET | `/notifications/stream` | SSE live stream |
| WS | `/notifications/ws` | WebSocket for mobile |

## MOD-08: Arweave

| Method | Endpoint | Description |
|---|---|---|
| GET | `/arweave/status` | Arweave wallet status |
| GET | `/arweave/bill/{id}` | Arweave TX-ID for a bill |

## MOD-09: gov.gr OAuth (deferred)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/auth/govgr/status` | gov.gr OAuth activation gates |
| GET | `/auth/govgr/login` | OAuth login (stub) |
| GET | `/auth/govgr/callback` | OAuth callback (stub) |
| GET | `/auth/govgr/family/verify` | Liquid democracy stub |
| GET | `/auth/govgr/info` | gov.gr docs |

## MOD-10: AI Scraper

| Method | Endpoint | Description |
|---|---|---|
| GET | `/scraper/status` | AI scraper provider status |
| GET | `/scraper/test` | Scraper test without DB |
| GET | `/scraper/parliament/latest` | Scrape hellenicparliament.gr |
| POST | `/scraper/fetch` | Scrape + Ollama → DB (admin) |

## MOD-11: Public API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/public/info` | Public API docs |
| GET | `/public/stats` | Platform statistics (public) |
| GET | `/public/bills` | Bills (CC BY 4.0) |
| GET | `/public/bills/{id}/results` | Results (public) |
| GET | `/public/vaa/parties` | Parties (public) |
| POST | `/public/keys/generate` | API key (no account needed) |
| GET | `/public/keys/status` | API key status |

## MOD-24: CPLM

| Method | Endpoint | Description |
|---|---|---|
| GET | `/public/cplm` | CPLM — Political Mirror (X/Y) |
| GET | `/public/cplm/history` | CPLM historical snapshots |
| GET | `/public/representation` | Parliament representativeness |

## MOD-12: MP Comparison

| Method | Endpoint | Description |
|---|---|---|
| GET | `/mp/parties` | Parties with parliamentary presence |
| GET | `/mp/ranking` | Ranking of convergence with citizens |
| GET | `/mp/compare/{abbr}` | Party vs citizen majority |
| GET | `/mp/bill/{id}` | Party votes for a bill |
| GET | `/mp/info` | MP comparison docs |

## MOD-14: Data Export

| Method | Endpoint | Description |
|---|---|---|
| GET | `/export/info` | Export endpoint docs |
| GET | `/export/bills.csv` | Bills + results CSV |
| GET | `/export/results.json` | Results JSON |
| GET | `/export/divergence.csv` | Divergence ranking CSV |
| GET | `/export/parties.json` | Parties JSON |

## MOD-15: Admin

| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin/dashboard` | Admin dashboard |
| GET | `/admin/bills` | Admin bill list |
| POST | `/admin/bills` | Create bill |
| PATCH | `/admin/bills/{id}` | Update bill |
| POST | `/admin/bills/{id}/review` | AI summary review |
| POST | `/admin/bills/{id}/party-votes` | Set party votes |
| GET | `/admin/stats` | Admin statistics |
| POST | `/notifications/test/publish` | Publish test event |

## MOD-16: Municipal

| Method | Endpoint | Description |
|---|---|---|
| GET | `/periferia` | Regions (periferies) |
| GET | `/periferia/{id}/dimos` | Municipalities of a region |
| GET | `/decisions` | Decisions (filter) |

## MOD-21: Diavgeia

| Method | Endpoint | Description |
|---|---|---|
| GET | `/municipal/{id}/decisions` | Diavgeia decisions of a municipality |
| GET | `/regions/{id}/decisions` | Diavgeia decisions of a region |
| POST | `/admin/diavgeia/scrape` | Manual scrape (admin) |
| POST | `/admin/diavgeia/refresh-orgs-cache` | Org cache refresh (admin) |
| GET | `/scraper/jobs` | Scraper job status (Redis) |
| GET | `/consensus/representation` | Aggregate Diavgeia results by municipality, region, and nationwide |

## MOD-22: RAG Agent

| Method | Endpoint | Description |
|---|---|---|
| POST | `/agent/ask` | RAG agent — citizen Q&A (5 req/min) |
| GET | `/bills/{id}/summary` | AI bill summary (Redis cache 7d) |
| POST | `/admin/logs/explain` | Ollama log analysis (admin) |
| POST | `/admin/scraper/heal-status` | Auto-healing status (admin) |

## MOD-19: Newsletter

| Method | Endpoint | Description |
|---|---|---|
| POST | `/newsletter/subscribe` | Newsletter subscribe |
| GET | `/newsletter/stats` | Newsletter stats |

## MOD-20: Push Notifications

| Method | Endpoint | Description |
|---|---|---|
| POST | `/notify/register` | Push token registration |

## MOD-25: Politikoi

| Method | Endpoint | Description |
|---|---|---|
| GET | `/politicians/` | Representatives who enabled evaluation |
| GET | `/politicians/{ada_number}/questions` | Evaluation questions |
| POST | `/politicians/{ada_number}/evaluate` | Submit evaluation (-5 to +5 per question, Ed25519 signed) |
| GET | `/politicians/{ada_number}/my-evaluation` | My evaluation |
| GET | `/politicians/{ada_number}/scores` | Public evaluation scores |
| POST | `/rep/enable-evaluation` | Representative consent to evaluation (representative app) |
| GET | `/rep/my-scores` | Representative's own evaluation scores (representative app) |

## Example

```bash
# Cast a vote. The server looks up the public key by nullifier_hash;
# the private key never leaves the device.
#   BILL_ID         id of a bill from GET /bills
#   NULLIFIER_HASH  64-hex value returned by POST /identity/verify
#   SIGNATURE_HEX   Ed25519 signature over "$BILL_ID:YES:$NULLIFIER_HASH"
curl -X POST https://api.ekklesia.gr/api/v1/vote \
  -H "Content-Type: application/json" \
  -d '{
    "bill_id": "'"$BILL_ID"'",
    "vote": "YES",
    "nullifier_hash": "'"$NULLIFIER_HASH"'",
    "signature_hex": "'"$SIGNATURE_HEX"'"
  }'
```
