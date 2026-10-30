# Cached public bill data inventory

Every body below passes through `services.public_bill_response.serve_public_bill_body`
after cache lookup or fill. One database statement reads listed IDs and results-visible
IDs, including ACTIVE/HIDDEN and complete-choice/source small-cell checks. The
visibility snapshot has zero TTL: each serve reads current scalar columns, bypassing
stale ORM state. Redis generation and body TTL remain optimizations;
neither authorizes a response. Database failures cannot authorize a cached body.

| Cache registration / public route(s) | Bill schema | Serve-time behavior |
| --- | --- | --- |
| `parliament.get_bills` — `/bills` | rows | Remove hidden bill summaries and their vote/relevance counts. |
| `parliament.get_trending` — `/bills/trending` | rows | Remove hidden bill summaries and their vote/relevance counts. |
| `analytics.analytics_overview` — `/analytics/overview` | aggregate | Rebuild bill counts, vote counts, averages and divergence if any contributing visibility changes. |
| `mp.party_ranking` — `/mp/ranking` | aggregate | Rebuild rankings, agreement and analyzed-bill counts. |
| `consensus_results.get_consensus_representation` — `/consensus/representation` | aggregate | Rebuild coverage, geographic counts and consensus views. |
| `analytics.get_cached_representation` — `/analytics/representation`, `/public/representation` | representation | Rebuild the entire body if listing or result visibility shrinks, including contributors outside the 200 detail rows. Withhold the response if rebuilding fails. |
| `cplm.get_cplm_cached` — `/cplm/aggregate`, `/public/cplm` | aggregate | Rebuild political position, vote/voter counts and trend. Previous trend snapshots are also checked. |
| `cplm.get_cplm_history` — `/cplm/history`, `/public/cplm/history` | history | Drop snapshots containing hidden bills or missing provenance. |
| `voting.get_results` — `/vote/{bill_id}/results` | point | Deny hidden bills after reading cached totals and population components; preserve current result visibility and small-cell checks. |
| `parliament.get_bill_summary` — `/bills/{bill_id}/summary` | point | Deny hidden bills, including on Redis summary hits. |
| `zk.get_zk_scope_status` — `/zk/scopes/{vote_scope_id}/status` | point | Deny hidden production bill scopes after cached status reads. Existing isolated synthetic canary eligibility remains checked separately. |
| `zk.get_current_zk_root_members` — `/zk/roots/{vote_scope_id}/members` | point | Deny hidden production bill scopes after cached membership verification. Same isolated canary policy. |
| `evaluation.list_politicians`, `get_questions`, `get_scores` — `/politicians/`, `/{ada_number}/questions`, `/{ada_number}/scores` | independent | Representative tokens, evaluation questions and evaluation scores contain no bill titles, votes or bill aggregates. Current politician eligibility is checked separately. |
| `municipal.list_periferies`, `list_dimos_by_periferia` — `/periferia`, `/periferia/{id}/dimos` | independent | Administrative regions, municipalities and populations contain no bill-derived data. |
| `polis_tickets.list_tickets` — `/polis/tickets` | independent | Ticket IDs, titles and ticket votes are independent of parliamentary bills. |

Paths above have the `/api/v1` prefix. Regional population values reuse the
`results_cache` storage but are geographic data; the final bill result still
passes through the point guard. The ZK membership cache stores verified member
tuples; its public response also passes through that guard.

Other public Redis/process caches hold mirror health, translation usage,
newsletter subscriber statistics and finance provider values, with no bill-derived
response fields. Bill exports, `/public/bills`, `/public/bills/{id}/results`,
divergence trends, top divergence, per-bill analytics and MP comparisons calculate
responses from current database reads instead of caching bodies.

Each aggregate build captures one visibility snapshot before calculation. ORM queries
use `snapshot_bill_filter()`; raw SQL uses `snapshot_raw_filter()` with bound IDs.
A bill published after capture cannot enter that calculation. Vote queries record
actual result contributors, including contributors outside truncated detail lists.

The private envelope contains `_public_bill_ids` (the captured listing domain used
by the calculation), `_public_bill_results_ids` (votes actually used), and the body.
CPLM trends retain both current and previous contributors. These IDs never appear
in public JSON. Every serve checks both sets against a current DB snapshot. An
unsafe aggregate is rebuilt through the existing bounded single-flight, with a
10-second serve deadline; it is never returned or partially subtracted. An unsafe
history entry is withheld. Legacy entries missing either set cannot be served.
Redis outages calculate from DB; failed DB checks propagate.

`test_public_bill_cache_inventory.py` enumerates every `public_client_cache`
registration and every inline bill cache boundary. The cache factory requires an
explicit bill schema and the guard requires both contributor keys for aggregates
and history. Runtime factory tests verify that fresh hits as well as
fills invoke the helper. New registrations require an inventory/schema review.
