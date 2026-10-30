# Cached public bill data inventory

Every body below passes through `services.public_bill_response.serve_public_bill_body`
after cache lookup or fill. It reads scalar bill IDs from the database using the
shared public visibility predicate. Redis generation and TTL remain optimizations;
neither authorizes a response. Database failures cannot authorize a cached body.

| Cache registration / public route(s) | Bill schema | Serve-time behavior |
| --- | --- | --- |
| `parliament.get_bills` — `/bills` | rows | Remove hidden bill summaries and their vote/relevance counts. |
| `parliament.get_trending` — `/bills/trending` | rows | Remove hidden bill summaries and their vote/relevance counts. |
| `analytics.analytics_overview` — `/analytics/overview` | aggregate | Rebuild bill counts, vote counts, averages and divergence if any contributing visibility changes. |
| `mp.party_ranking` — `/mp/ranking` | aggregate | Rebuild rankings, agreement and analyzed-bill counts. |
| `consensus_results.get_consensus_representation` — `/consensus/representation` | aggregate | Rebuild coverage, geographic counts and consensus views. |
| `analytics.get_cached_representation` — `/analytics/representation`, `/public/representation` | representation | Filter details and `last_bill`; withhold cumulative scores, labels and vote/bill totals if provenance includes a hidden bill, including one outside the 200 detail rows. |
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

Aggregate cache envelopes privately retain the public bill-ID set captured before
calculation. These IDs cover contributors omitted from a truncated detail list and
never appear in public JSON. Legacy aggregates lacking provenance are rebuilt;
legacy history is withheld. Representation filtering copies the body and never
changes its cached source or renews its expiration.

`test_public_bill_cache_inventory.py` enumerates every `public_client_cache`
registration and every inline bill cache boundary. The cache factory requires an
explicit bill schema. Runtime factory tests verify that fresh hits as well as
fills invoke the helper. New registrations require an inventory/schema review.
