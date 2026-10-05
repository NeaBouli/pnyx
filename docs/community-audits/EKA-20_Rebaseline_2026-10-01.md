# EKA-20 follow-up — 2026-05-03 master-audit findings re-checked (2026-10-01)

Addendum to the [Full-Scope Security Audit](EKA_PNYX_Full_Scope_Audit_2026-09-15.md) §EKA-20.
The pinned 2026-09-15 report is unchanged; this file records the source-level status
of the ten historical findings. Checked against `main` at `7fe46b56` plus PR #388 at head
`7abc5857`; the merge commit of #388 will be recorded here when this addendum merges.
Source review only, without live probes or production access.

| Prior finding | 2026-09-15 status | 2026-10-01 status | Evidence |
|---|---|---|---|
| PNYX-CRIT-01 admin keys in URLs | Fixed | **Closed** | `apps/api/dependencies.py::verify_admin_key` accepts only `Authorization: Bearer`; no `admin_key` query path in `apps/api` |
| PNYX-CRIT-02 public web admin key | Fixed | **Closed** | no `admin_key`/`ADMIN_KEY` in `apps/web/src`; CI gate in `scripts/static-docs-remote-sinks.check.mjs`; the dashboard uses the server-side proxy `apps/dashboard/src/app/api/proxy/[...path]/route.ts` |
| PNYX-HIGH-01 votes-timeline broad-except | Partial | **Closed** (#388) | votes-timeline exposes a structured degraded state with focused contract tests |
| PNYX-HIGH-02 documentation drift | Re-assessed in the content audit | **Open, tracked elsewhere** | carried by EKA-33…56 of the content-coherence audit; partly fixed (#374–#377); the remaining items stay open in register #318 |
| PNYX-HIGH-03 secret-bearing files | Clean | **Closed** | no secret-class files in the tree; `.env.production.template` holds only empty values or placeholders |
| PNYX-MED-01 Ollama/RAG live verification | Covered by the integration audit | **Not verifiable from source** | requires live access; source-side hardening merged in #373 (EKA-58/61/62) |
| PNYX-MED-02 logs/explain wiring | Fixed | **Closed** | API: `apps/api/routers/admin.py` `/logs/explain`, `/logs/containers`, `/logs/ollama`, `/logs/stream`; dashboard: `apps/dashboard/src/app/(dashboard)/logs/page.tsx` calls `/api/proxy/admin/logs/containers`, `/logs/stream` and `POST /logs/explain` through the server-side proxy |
| PNYX-MED-03 greek_topics_scraper | Resolved | **Closed** | module removed; `main.py::scheduled_greek_topics` imports defensively |
| PNYX-MED-04 docs innerHTML | Partial (EKA-14) | **Closed** | EKA-14/15 fixed in #368; remote-sink CI gate |
| PNYX-MED-05 package-ID drift | Open (EKA-19) | **Open** | `apps/mobile/app.json`: Android `ekklesia.gr`, iOS `gr.ekklesia.app`; the canonical iOS ID is an owner decision |

Summary: 7 closed, 2 open (HIGH-02 documentation cluster, MED-05 package ID) and 1 only
verifiable live (MED-01).
