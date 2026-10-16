# ekklesia.gr / pnyx — Content Coherence Audit (landing + wiki + docs pages)

**Auditor:** Collateral Web3 Open Audits
**Client:** NeaBouli / ekklesia.gr (pnyx)
**Date:** 2026-09-15
**Baselines:** repo `NeaBouli/pnyx` @ `c0efac7b0ee7669d91402c50eb5dcf4db7819fe3` (all 35 audited pages byte-identical live ↔ repo where served; sampled) · live link/endpoint checks 2026-09-15 (anonymous GET/HEAD only)
**Companion documents:** full-scope (EKA-01…20), crypto deep (EKA-21…25), integration & surfaces (EKA-26…31), AI readiness (register continues EKA-57+)
**Method:** claim extraction by three parallel auditors (≈190 checkable claims), then lead verification of every proposed finding at the exact file:line and against live probes
**Report version:** 1.0

Scope: every public content page — landing `docs/index.html`, `community.html`,
`govgr-dimos.html`, `representative.html`, `legal.html`, all 14 wiki HTML pages, the 10
markdown wiki sources, `tickets/`, `municipality/`, plus technical surface (links, sitemap,
robots, llms.txt, SEO/meta/JSON-LD/hreflang). One security finding discovered during
verification is included here (EKA-32) because it changes the meaning of several published
claims.

**Verdict: SUBSTANTIAL DRIFT on a honest foundation.** The platform's gating language is
exemplary where it matters most (gov.gr design-only, ZK canary, no fake numbers in vote
counters), and the newest pages carry accurate crypto descriptions. But the marketing
surface contradicts itself and the code on the platform's three most sensitive promises —
tracking, political-profile storage, and result permanence — while counts (modules,
endpoints, tables, costs) drift across up to four different values per metric.

**Findings: 0 Critical · 0 High · 10 Medium · 11 Low · 4 Informational (EKA-32 … EKA-56)**

| # | Severity | Title | Status |
|---|----------|-------|--------|
| EKA-32 | Medium | No global rate limit is enforced — slowapi middleware never registered | Open (security) |
| EKA-33 | Medium | "0 Cookies · Trackers · analytics" claims contradict Plausible script on the same pages | Open |
| EKA-34 | Medium | Compass "never on server / never leaves device" false on two axes | Open |
| EKA-35 | Medium | "The server doesn't know what you voted" overstated vs the site's own privacy modal | Open |
| EKA-36 | Medium | Arweave permanence claims ("every result", "no central log") exceed the real publication scope | Open |
| EKA-37 | Medium | Wiki API reference documents 7 nonexistent/wrong endpoints; curl example would fail 422 | Open |
| EKA-38 | Medium | Distribution-status drift: F-Droid label 3 versions stale, llms.txt "pending" though live, dead Apple-store link, ekprosopos APK 404 | Open |
| EKA-39 | Low | Four conflicting annual-cost totals across pages | Open |
| EKA-40 | Medium | Count chaos: modules 25/22/23, endpoints 16/70+/~188, tables 9/18/15+/24, containers 9/11+ | Open |
| EKA-41 | Low | TrueRepublic presented as live archival chain in FAQ; bridge is disabled and V2-future | Open |
| EKA-42 | Medium | FAQ self-contradictions: AI providers, HLR providers, vote-change rule, HLR meaning | Open |
| EKA-43 | Low | ZK presented as both "live (Beta)" and "coming (Alpha)" on the same landing page | Open |
| EKA-44 | Low | Donation status: landing lists Stripe under "Beta — now"; intake is gated closed | Open |
| EKA-45 | Low | Privacy modals drift across pages (three IP-retention variants) | Open |
| EKA-46 | Medium | Systematic markdown↔HTML wiki drift (MD uniformly staler) | Open |
| EKA-47 | Low | i18n defect: visible Greek text differs from `data-el` attribute on key claims | Open |
| EKA-48 | Low | SEO gaps: legal.html bare, 4 pages missing JSON-LD/twitter/hreflang, invalid en-hreflang | Open |
| EKA-49 | Low | Sitemap lastmod stale on 21/22 entries; municipality canonical points at redirect URL | Open |
| EKA-50 | Low | Phantom modules MOD-13/MOD-17 shown in wiki (one as active) | Open |
| EKA-51 | Low | Defect cluster: duplicate ids/links, wrong footer links, invisible icon, stale comment, badge miscounts | Open |
| EKA-52 | Low | MOD-25 status three-way inconsistent; database.html documents nonexistent tables | Open |
| EKA-53 | Informational | `/api/v1/admin/deepl/usage` public by design under an admin prefix | Open |
| EKA-54 | Informational | Legal-entity naming inconsistent across pages | Open |
| EKA-55 | Informational | "No owner" rhetoric vs named data controller in legal.html | Open |
| EKA-56 | Informational | Verified-consistent register (strengths) | Recorded |

---

## 1. Findings

### EKA-32 — No global rate limit is enforced (security, found during content verification)
- **Component:** `apps/api/main.py:67` (limiter with `default_limits=["60/minute"]`) vs
  `main.py:738-751` (only `CORSMiddleware` registered)
- slowapi enforces `default_limits` only through `SlowAPIMiddleware`; it is never added.
  Effective limits today: `agent/ask` 5/min, `claude/ask` 3/min (decorators), plus the
  custom Redis limiters on `contact` (3/h), `public/*` (100/1000), keygen (5/h). **Every
  other endpoint — vote, identity/verify, newsletter subscribe, flag — has no working
  rate limit at all.** This upgrades EKA-04/EKA-06 likelihood to high and contradicts the
  wiki's published "Rate Limit: 60 req/min/IP" (api.html:216). **Fix:** add
  `app.add_middleware(SlowAPIMiddleware)` or per-router decorators; then correct the wiki.

### EKA-33 — "0 trackers/analytics" vs Plausible on the same pages
- `docs/index.html:473` (also community:286, govgr-dimos:201, representative:32) loads
  `analytics.ekklesia.gr/js/script.js` while the same page's hero tile (:535-536) and
  JSON-LD (:441) claim "0 — Cookies · Trackers" / "No cookies, no tracking".
- `docs/wiki/faq.html:163` loads the script; :348 and its own JSON-LD (:738) answer
  "Κανένα cookie, κανένα tracking, κανένα analytics."
- `docs/wiki/privacy.html:180` loads it; :377 states the platform uses no
  "cookies, tracking, analytics ή διαφημίσεις". `security.html:181` same pattern.
  Plausible is self-hosted and cookieless — defensible — but the absolute wording is
  factually false and GDPR-sensitive. **Fix:** either drop the absolute claims
  ("no third-party trackers; first-party, cookieless Plausible") or remove the script.

### EKA-34 — Compass privacy claims false on two axes
- Claims: `index.html:954` "Κρυπτογραφημένη τοπικά, ποτέ στον server";
  `roadmap.html:383-384` "100% στη συσκευή … ούτε στον server μας … AES-256";
  `faq.html:268/480/930`, `Modules.md:16` "client-only, AES-256-GCM".
- Reality (code-verified): (1) plaintext localStorage fallback when no identity key exists
  (`storage.ts:86-96,117`, EKA-08); (2) the server **derives and stores** per-nullifier
  political positions from cast votes (`cplm_history`, `services/cplm.py`) and serves them
  via `POST /compass/personal` (EKA-25). **Fix:** reword to describe derivation
  ("positions are also computable server-side from your public votes") and the fallback.

### EKA-35 — "Ο server δεν γνωρίζει τι ψηφίσατε" (index.html:1484)
The site's own privacy modal (:1547) lists stored votes ("Ψήφοι (ανώνυμα YES/NO/ABSTAIN)"),
and govgr-dimos.html:720 carries the accurate formulation ("doesn't know WHO voted — only
WHAT was voted"). The landing sentence inverts the truth at the most sensitive point of
the funnel. **Fix:** adopt the govgr-dimos wording site-wide.

### EKA-36 — Arweave permanence overstatements
- `index.html:979` "Κάθε αποτέλεσμα αρχειοθετείται μόνιμα"; `govgr-dimos.html:499`
  "αποτελέσματα κάθε ψηφοφορίας … Κανένα κεντρικό log — μόνο blockchain";
  `representative.html:106,141,156,183` (×4).
- Reality: publication on PARLIAMENT_VOTED bill trails + ZK receipts for groups ≥5;
  canary receipts never published; ACTIVE-bill results hidden; and the server DB is of
  course the primary store. "No central log — only blockchain" is simply false.
  **Fix:** scope the claim ("final parliamentary results and eligible ZK receipts").

### EKA-37 — Wiki API reference errors (developer-facing)
`docs/wiki/api.html`: documents `GET /politikoi`, `/politikoi/{id}`,
`POST /politikoi/{id}/evaluate`, `GET /politikoi/{id}/my-evaluation` (:318-321) — real
prefix is `/api/v1/politicians` (`evaluation.py:28`); `POST /rep/consent` and
`GET /rep/evaluation` (:317,:322) do not exist (real: `/rep/my-scores` et al.);
`GET /identity/status/{hash}` (:223) — real: `POST /api/v1/identity/status`; the vote
curl example (:328-336) uses `choice`/`signature`/`public_key` where the schema requires
`vote`/`signature_hex` and no public key — it would fail 422. Additionally the MOD-25
rows are marked "Planned" contradicting modules.html (`Beta`). **Fix:** regenerate the
table from the OpenAPI schema in CI.

### EKA-38 — Distribution-status drift
- `index.html:1349-1351` F-Droid tile: green "Available" with **v1.0.29 · vC584** — live
  F-Droid serves 1.0.32 (codes 612-614, added 2026-09-09; verified against
  f-droid.org/packages/ekklesia.gr/). Availability is now true; the label is 3 versions
  stale, and `llms.txt:36` ("F-Droid's independent build remain pending") is stale in the
  opposite direction. (`wiki/faq.html:442`, `roadmap.html:470` hedge text likewise
  outdated.)
- `index.html:1092` "iOS App" button links `apps.apple.com/app/discourse-hub/id1442328667`
  — **dead** (App Store 404, iTunes Lookup `resultCount:0` in US+GR storefronts).
- `download/ekprosopos-latest.apk` — **404**, linked from `index.html:1027` and
  `representative.html:173`, and documented as deployed in
  `docs/download/APK_MANIFEST.md:12`.
- **Fix:** single source of truth for store states (like the app-version endpoint), then
  point every tile at it.

### EKA-39 — Four conflicting annual-cost totals
`faq.html:409` ~250€/yr · `faq.html:826` (own JSON-LD) ~93.30€ · `whitepaper.html:305-308`
~93.30€ · `Whitepaper.md:307-309` ~200-300€/yr (CX21). Also internally:
community.html:728 "~250€/έτος" vs :686 "Σύνολο/έτος: ~€130-200"; HLR cost 0.006€ (:526)
vs $0.002 (:684); "15€ = 2500 credits" vs "Αρχικά: 2499". Transparency pages undermine
themselves. **Fix:** one cost table, generated or at least single-sourced.

### EKA-40 — Count chaos (PNYX-HIGH-02 still material)
| Metric | Published values | Verified |
|---|---|---|
| Modules | "25" (index:215, community:46, llms.txt:47, wiki/api.html:216, modules.html:182, whitepaper.html:247) · "22" (wiki/index.html:260, same page says 25 at :215) | 23 live keys in /health; spec text "25 modules, 23 live" |
| API endpoints | "16" (index:1146) · "70+" (index:215,259, api.html, whitepaper.html:247) | ~188 (32 routers) |
| DB tables | "9" (Database.md:10) · "18" (database.html meta:7) · "15+" (index:219,261) · "13" (index:1166) | 24 `__tablename__` + migration-only polis tables |
| Containers | "9" (wiki/index.html:263) · "11+" (llms.txt:47) | 8 services in prod compose |
**Fix:** the 2026-05-03 audit's recommendation stands — a generated `PROJECT_FACTS`
artifact consumed by all pages.

### EKA-41 — TrueRepublic as live chain in FAQ
`faq.html:253` and its JSON-LD (:642): snapshots "αρχειοθετούνται μόνιμα στο Arweave **και
στο TrueRepublic/PNYX blockchain**" (present tense). Code: `TRUEREPUBLIC_ENABLED: "false"`
(docker-compose.yml:42); Roadmap/Whitepaper place the bridge in V1/V2; Whitepaper.md:295
even mislabels it as MOD-08 (which is Arweave). **Fix:** future tense + correct module id.

### EKA-42 — FAQ self-contradictions
- AI: visible answer `faq.html:401` lists "Claude Haiku (Anthropic API — automatic
  fallback)"; its own JSON-LD (:818) claims "Κανένας εμπορικός πάροχος AI API — όλα
  τρέχουν σε δικό μας server." Both cannot hold (claude_usage.py confirms haiku-4-5 API).
  Related cross-page drift: index.html:984 credits Ollama+DeepL for Q&A/summaries vs
  community.html:631 crediting Claude Haiku for the same jobs.
- HLR providers: `faq.html:368` names "HLR Lookups / Melrose Labs / Telnyx" — code has
  hlrlookup.com (primary) and hlr-lookups.com (fallback); Melrose optional, Telnyx absent.
- Vote change: `faq.html:238` (WINDOW_24H + OPEN_END — matches voting.py:467-483) vs
  `faq.html:495` ("final after the window") — wrong for the main vote path.
- HLR meaning: JSON-LD (:682) says HLR checks "whether a Greek SIM is active" while the
  page's own visible text (:305/:310) carefully says it does not prove SIM possession.
- Section badge counts wrong: 8→9, 5→6, 6→10 actual items; the Semaphore item (:295) sits
  under the wrong header.

### EKA-43 — ZK both live and future on one page
`index.html:1003/:1204` "Semaphore ZK Proofs — guarded Parliament rollout live" (Beta
column) vs :1010-1013 "Zero-Knowledge Proofs — μαθηματικά αποδείξιμο" under "Alpha —
Σύντομα". Both defensible (base layer live, full verifiability future) but presented as
flat contradictions. **Fix:** name the layers.

### EKA-44 — Donation status
`index.html:1196` lists "Stripe Δωρεές" under "Beta — Τώρα"; community.html:347 says
donations are "προσωρινά σε παύση" with six grayed buttons; code gates intake on
`PAYMENTS_INTAKE_GATE == "legal_recipient_confirmed"` (payments.py:166-168) — i.e. paused
is the deployed truth. **Fix:** align the landing roadmap tile.

### EKA-45 — Privacy-modal drift
community.html:977 (short variant): "we store no IP address"; govgr-dimos.html:487:
"last octet anonymized in all logs"; index.html:1546-1550: current long variant
(Argon2id v2 + SHA256 anchor, Hetzner EU, k≥10). Three retention claims, one truth.
**Fix:** one modal include, shared across pages.

### EKA-46 — Systematic MD↔HTML wiki drift
The markdown sources are uniformly staler than their HTML siblings: `Security.md:34,72` /
`Privacy.md:25` / `Database.md:14` still "SHA256(phone+salt)"-only (HTML pages correctly
say Argon2id v2 + SHA256 anchor); `Database.md:10` "9 tables"; `API.md:9` bare-domain base
URL (real: api.ekklesia.gr); `Privacy.md:18` "Email ❌ not requested" (newsletter exists);
`Home.md:16` "F-Droid 1.0.29 public"; `Architecture.md` lists all 6 apps while
architecture.html:214-223 shows 3. **Fix:** generate one from the other or mark MD as
source-of-truth and sync in CI.

### EKA-47 — i18n defect: `data-el` ≠ visible Greek
On several key claims the visible Greek differs from the `data-el` attribute the language
toggle restores — i.e. the text a user sees first is not the text the site's own i18n
system considers canonical: `index.html:562` (the "number deleted immediately" clause
exists only in data-el), `:1013` (gov.gr detail only in data-el), `representative.html:93,
101,102,118,180-183` (incl. a missing "δεν αποθηκεύεται"), `govgr-dimos.html:231`.
**Fix:** sync initial render with data-attributes in CI (diff test).

### EKA-48 — SEO gaps
`legal.html` has no og/twitter/hreflang/JSON-LD at all (the only metadata-bare public
page); `wiki/index.html` and `wiki/roadmap.html` lack JSON-LD; `representative.html`,
`municipality/*.html`, `tickets/index.html`, `wiki/zk-voting.html` lack twitter cards;
hreflang `el`/`en`/`x-default` on index/community/govgr all point to the same URL — there
is no distinct English document (language is a JS toggle), so the `en` alternate is
invalid. (Positives: titles unique, canonical+description on all public pages, all 21
JSON-LD blocks parse valid.)

### EKA-49 — Sitemap hygiene
21 of 22 `lastmod` values predate the real last commit of the file (sample: index.html
sitemap says 2026-05-22, git says 2026-09-06). `municipality/` canonical/og:url point at
the directory URL that 308→307-redirects; harmless but sloppy for crawlers. **Fix:**
generate lastmod from `git log -1` in CI.

### EKA-50 — Phantom modules
`wiki/modules.html:238` shows MOD-13 "Relevance Voting" with an active dot + "Alpha";
:232 MOD-17 "Planned". Neither exists in the runtime registry. (Relevance lives inside
MOD-14; docs assign it MOD-13/14 in three places.)

### EKA-51 — Defect cluster (each verified)
Duplicate `id="dot-mod02"` (modules.html:225-226) · duplicate "FAQ" nav links
(community.html:306+308) · "24 Ώρες" footer links to `/el/bills` without
`?status=WINDOW_24H` (community:957, govgr-dimos:766; index:1524 does it right) · App
Store SVG `fill="white"` on white card — invisible (index:1319) · stale comment
"DEAKTIVIERT bis User-Release (2026-04-09)" above the live download section
(index:1307) · FAQ badge miscounts and misplaced Semaphore item (EKA-42) ·
`Contributing.md:41` leaks an absolute developer path (`/Users/gio/TrueRepublic`).

### EKA-52 — MOD-25 status three-way inconsistent
modules.html:249 / Modules.md:39 / roadmap.html / runtime: **Beta (live)** ·
api.html:316-322 + database.html:232-234: **"Planned"** — and database.html documents
nonexistent table names (`representative_consent`, `citizen_evaluation`) while omitting
the real live ones (`politician_evaluations`, `evaluation_questions`).

### EKA-53 — `/api/v1/admin/deepl/usage` public by design (Info)
Returns live DeepL quota anonymously (23,845/500,000 at probe time) with a docstring
"no auth needed — no sensitive data". Exposure is intentional; the `/admin/` prefix makes
it look like a misconfiguration in every future review. Consider moving under `/public/`.

### EKA-54 — Entity naming inconsistent (Info)
"V-Labs IT Solutions & Development" (index, community, legal) vs "V-Labs Development"
(govgr-dimos, representative) vs "Vendetta Labs" (legal trading name, CLAUDE.md copyright).
Pick one legal + one trading name and use them uniformly.

### EKA-55 — "No owner" rhetoric vs data controller (Info)
Landing/community: "Δεν ανήκει σε κανέναν" ("belongs to no one"); legal.html:134-146 names
a sole-proprietorship operator and data controller (and :146 itself acknowledges the
community split). The legal page resolves it correctly; the marketing absolute invites
the wrong reading. Suggest "kein Eigentümer der Plattform-Idee — Betreiber/Verantwortlicher
siehe legal".

### EKA-56 — Verified-consistent register (Info, excerpt)
 gov.gr gating language across all pages is exemplary (design-only, DPIA, sandbox,
 "no credentials today") · 78 non-MOD-25 endpoints in api.html verified real ·
 9,810,040 electorate · 332 municipalities / 13 regions · 38/8 VAA · 48 compass questions ·
 k≥10 identical in code and docs · Argon2id-v2+SHA256-anchor wording correct on all HTML
 security/privacy pages · vote-chain error codes (403/400/401/409) exact · Semaphore
 guarded-rollout description exact (group ≥5, canary never published, PSE ceremony, no
 own ceremony) · CPLM ±0.05/6h/CC-BY exact · APK v1.0.32/vC61 direct + Play-pending +
 iOS-PWA exact · F-Droid availability (per live store) true · double opt-in exact ·
 honest empty-states in vote counters ("Δεν προβάλλονται δοκιμαστικοί αριθμοί") ·
 robots/sitemap exclusion logic consistent · no broken internal anchors (0) · 65/70
 external links live.

---

*— End of content coherence audit. Register continues EKA-57+ (AI readiness).*
