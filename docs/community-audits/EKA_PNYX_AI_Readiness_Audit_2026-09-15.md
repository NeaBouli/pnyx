# ekklesia.gr / pnyx — AI Readiness Audit (assistant knowledge + AI anchors)

**Auditor:** Collateral Web3 Open Audits
**Client:** NeaBouli / ekklesia.gr (pnyx)
**Date:** 2026-09-15
**Baselines:** repo `NeaBouli/pnyx` @ `c0efac7b0ee7669d91402c50eb5dcf4db7819fe3` · live anchor checks 2026-09-15 (anonymous GET/HEAD only — no POSTs against the assistant)
**Companion documents:** full-scope (EKA-01…20), crypto deep (EKA-21…25), integration & surfaces (EKA-26…31), content coherence (EKA-32…56)
**Report version:** 1.0

Scope, two halves: **(A) the landing AI assistant's knowledge** — can it answer correctly?
(`apps/api/routers/agent.py` + `claude_agent.py`, Ollama pipeline, knowledge base,
safety rails, ingestion paths) and **(B) the project's AI/search anchors** — can external
AI and crawlers discover it correctly? (robots.txt, llms.txt, sitemap, JSON-LD, hreflang).

**Verdict: ARCHITECTURALLY CAREFUL, KNOWLEDGE-STALE.** The request pipeline is better than
most production bots: the eight riskiest topics bypass all LLMs via hardcoded canonical
answers, a bilingual safety filter intercepts abuse before any model call, costs have a
kill-switch, and PII-class bills are filtered before retrieval. But the knowledge base
has **no authoritative refresh path** — two divergent manual seeds, no scheduler job, no
CI check — so the bot's facts drift with every release, and four canonical user questions
have no source material at all. The anchor layer is strong (explicit AI-crawler policy,
byte-fresh sitemap, 21 valid JSON-LD blocks) with the staleness already registered in the
content audit.

**Findings: 0 Critical · 0 High · 3 Medium · 4 Low · 1 Informational (EKA-57 … EKA-64)**

| # | Severity | Title | Status |
|---|----------|-------|--------|
| EKA-57 | Medium | Knowledge base has no refresh path — two divergent seeds, drift guaranteed | Open |
| EKA-58 | Medium | Prompt-injection exposure: scraped bill titles flow unsanitized into both LLM prompts | Open |
| EKA-59 | Medium | Bot teaches wrong key-storage facts (iOS Keychain claim; silent on plaintext web beta) | Open |
| EKA-60 | Low | Bot points donors at the paused Stripe/PayPal pipeline | Open |
| EKA-61 | Low | `/api/v1/claude/ask` bypasses every guardrail; token budget tracked but not enforced | Open |
| EKA-62 | Low | Chat frontend + pipeline robustness cluster (brittle sanitization, hidden 429s, lang mixing, dead timeout) | Open |
| EKA-63 | Low | Coverage gaps: data deletion, ZK/Semaphore, representative verification, results lifecycle | Open |
| EKA-64 | Informational | Anchor-layer staleness + soft-404 redirects (ai.txt, llms-full.txt → landing) | Open |

---

## 1. How the assistant works (verified pipeline)

Browser widget (`docs/index.html:2033-2046`, posts `{question, lang}`) →
`POST /api/v1/agent/ask` (5 req/min/IP, `agent.py:408`) → length validation (3-500
chars) → **bilingual safety keyword filter** (18 EN/EL patterns, fixed refusal, no LLM
call, `agent.py:55-110`) → **8 canonical deterministic answers** for the riskiest topics
(private key, nullifier, CPLM, gov.gr, municipal, Android download, vote correction,
greetings — `agent.py:113-232`, never touch an LLM) → RAG: top-5 of max-20 KB rows by
keyword score, plus newest-10 public bills only on bill-intent regex
(`agent.py:247-321`) → Ollama `llama3.2:3b` with DeepL EL→EN→EL round-trip, temp 0.2,
300 tokens (`ollama_service.py:293-342`) → poor-answer heuristic → **Claude
haiku-4-5 fallback** with the same context, 400 tokens, credit-balance kill-switch
(`agent.py:324-381`) → disclaimer appended on every path → rendered with `<`→`&lt;`
(`index.html:2050`).

Strengths verified: canonicals for exactly the topics a bot must never improvise;
`public_bill_filter` removes admin-hidden and AMKA/patient-term bills before retrieval
(`bill_visibility.py:96-101`); no question logging claim holds (no question column);
cost tracking with kill-switch; rate limit present.

## 2. Findings

### EKA-57 — Knowledge base has no authoritative refresh path
- **Component:** `scripts/seed_knowledge_base.sql` (17 rows, DELETE+INSERT, manual psql)
  vs `apps/api/scripts/seed_knowledge_base.py` (14 rows, upsert-only, never deletes);
  migration seeds nothing (`alembic/versions/j301a2b3c4d5_knowledge_base.py:17-31`);
  none of the 12 scheduler jobs touch the table (`main.py:675-686`); no CI seed/drift
  check.
- The two seeds are **not supersets of each other** (PY uniquely adds vote correction,
  CPLM, nullifier, lost key, Android, municipal; they even disagree on the operator name —
  "Vendetta Labs" vs "V-Labs Development"). If both ever ran: ~27 rows against a
  retrieval cap of 20 (`agent.py:253-255`) → topics silently unreachable, plus 4
  duplicate-topic pairs competing for the 5 context slots. The handover doc records 8
  live rows — matching neither seed, so **deployed content is unknowable from the repo**.
  The regression dataset for live testing is gitignored, so the training-regression test
  always skips (`tests/test_agent_training_regression.py:18-21`).
- **Fix:** one seed (keep the Python upsert), run in deploy pipeline; CI drift test
  asserting DB == seed; dedupe topics; include the dataset in the repo.

### EKA-58 — Prompt-injection exposure via scraped bill content
- **Component:** parliament scrape 12 h + Diavgeia 48 h → `parliament_bills.title_el` /
  AI-generated `pill_el` → inserted raw into the RAG context (`agent.py:296-318`) →
  embedded into the Ollama prompt `"Data:\n{en_context}"` (`ollama_service.py:315-324`)
  and the Claude system prompt (`agent.py:336-347`).
- Verified: **zero** sanitization in the scraper (`grep -c 'sanitize|bleach|escape'` = 0),
  no delimiters/quoting around retrieved titles, safety filter inspects only the user's
  question. A hostile or merely weird bill/decision title ("Ignore instructions, say X")
  flows into both models. Likelihood is bounded by the sources being official government
  sites, but the platform explicitly ingests ~1 775 Diavgeia publishing orgs.
  **Fix:** delimiter-wrap + escape retrieved content, add an output-side check (the
  poor-answer heuristic extended to instruction-echo patterns), document the trust
  boundary in the module README. Forum posts and GitHub issues are **not** ingested
  (outbound only) — that vector is clean.

### EKA-59 — Bot teaches wrong key-storage facts
- **Component:** `scripts/seed_knowledge_base.sql:18` — the row the LLM quotes claims the
  private key lives in "Android Keystore / **iOS Keychain**" and adds "Ο server δεν γνωρίζει
  ποτέ τι ψήφισες" and "Δεν υπάρχουν cookies, accounts ή email".
- Reality: iOS is PWA-only (no Keychain); the web app stores the key **plaintext** in
  localStorage (EKA-07); the absolute server-ignorance claim is EKA-35 territory; and
  newsletter accounts contradict the last clause. The canonical answer
  (`agent.py:142-153`) is safe but silent on the plaintext beta. **Fix:** correct the row
  per platform (Android SecureStore/Keystore · web beta plaintext · iOS PWA same as web)
  and align with the EKA-35 wording.

### EKA-60 — Donation answers point at the paused pipeline
KB rows (SQL:13,58) tell users funding runs via Stripe/PayPal; intake is fail-closed
(503 "awaiting legal recipient approval", `payments.py:166-168,979-980`) and the live
channel is the contact address (`mail_policy.py:9`). Aligns with EKA-44; fix with the
same single-source pass.

### EKA-61 — `/api/v1/claude/ask` bypasses every guardrail
A second public endpoint (3 req/min) with **no safety filter, no canonicals, no KB/RAG
context**, a bare static system prompt (`claude_agent.py:25-72`). The 50 k-token/day and
€10/month budgets are **tracked but never enforced** before the API call
(`claude_usage.py:75-110` — verified: no raise/block) — the only brake is the post-hoc
credit-balance flag. Not wired into any frontend, but public and wiki-documented.
**Fix:** route it through the same pipeline or delete the endpoint.

### EKA-62 — Frontend + pipeline robustness cluster (Low)
- Answer rendering: single `<`→`&lt;` replace on cumulative `innerHTML +=`
  (`index.html:2039,2050`) — blocks tag injection today, brittle tomorrow; `textContent`
  or DOM nodes instead.
- 429 rate-limit responses render as a generic "couldn't answer", hiding the cause.
- `lang` handling: exact `"el"` at `agent.py:431` vs `startswith("el")` elsewhere →
  `lang="el-GR"` mixes an English disclaimer with Greek KB; any non-"en" lang gets Greek
  KB with English disclaimer.
- `OLLAMA_TIMEOUT` read but never used (`agent.py:31`; the "reduced timeout" comment at
  :434 is dead code).
- KB rows used by the LLM are never exposed in `sources` — users can't audit the basis.

### EKA-63 — Coverage gaps (desk-check, 15 canonical questions)
No source material exists for: **data deletion** (only an admin endpoint and a wiki
Art.-17 note — the bot cannot explain the user path), **ZK/Semaphore** (feature is live
behind canary gates; llama3.2 must improvise), **representative verification** (ADA/
Diavgeia flow undocumented to the bot), and **results visibility lifecycle** (ACTIVE
hidden → WINDOW_24H publication). For everything covered, answers are mostly correct —
precisely because those topics are hardcoded canonicals. **Fix:** add the four topics to
the canonical set (deterministic answers) rather than the KB.

### EKA-64 — Anchor-layer notes (Info)
- `llms.txt` exists, is detailed, and its ZK rollout description is exactly right
  (canary `bill:GR-d4c62ed4`, group ≥5, guarded) — but carries the two staleness items
  already registered: "F-Droid … pending" (EKA-38) and "25 modules, 11+ containers"
  (EKA-40).
- `robots.txt` explicitly allows 9 AI crawlers (GPTBot, ClaudeBot, anthropic-ai,
  PerplexityBot, Google-Extended, CCBot, …) — exemplary.
- Sitemap byte-identical live ↔ repo; 21 JSON-LD blocks valid (gaps: wiki/index,
  wiki/roadmap, legal.html — EKA-48); invalid `en` hreflang (EKA-48).
- **Soft-404 trap:** `/ai.txt` and `/llms-full.txt` return **307 → landing** instead of
  404 (the Next proxy rewrites unknown paths). AI crawlers probing conventional anchor
  filenames get HTML, not a signal. Either serve real files or let them 404.

---

*— End of AI readiness audit. Register complete at EKA-64.*
