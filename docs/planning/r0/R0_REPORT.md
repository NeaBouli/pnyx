# R0 baseline inventory report - public docs HTML surface

Status: `BASELINE_INVENTORY` - generated deterministically by
`scripts/redesign/r0_inventory.py`. Do not edit by hand; regenerate.

**This report is a baseline inventory, not a canonical-text approval.**
No wording recorded here is approved as canonical, no audit finding is
closed, and packages H/I wording gates remain open. The report identifies
gaps and risks without changing them.

Scope: 35 tracked public HTML pages under `docs/`,
frozen by `PUBLIC_HTML_ALLOWLIST.txt`. Any new or missing public HTML file
fails regeneration closed until the allowlist is deliberately updated.

## Reproduction

```bash
python3 scripts/redesign/r0_inventory.py          # regenerate artifacts
python3 scripts/redesign/r0_inventory.py --check  # verify byte-for-byte
```

## Surface overview

| Page | lang | Title | Links | Forms/Controls | Scripts (ext/inline) | JSON-LD | External hosts |
|---|---|---|---|---|---|---|---|
| `docs/animation-spec/LANDING_SNIPPETS.html` | - | - | 0 | 0/0 | 1/0 | - | - |
| `docs/community.html` | el | Community — Κοινοτική Πρωτοβουλία \| εκκλησία | 56 | 1/16 | 1/7 | Organization | 2.ekklesia.gr, 3.ekklesia.gr, analytics.ekklesia.gr, api.coingecko.com, api.ekklesia.gr, changenow.io, ekklesia.gr, github.com, mirror.204.168.165.143.nip.io, t.me, twitter.com, wa.me, www.coinex.com, www.facebook.com |
| `docs/demo/admin.html` | el | Node Admin — Demo | 4 | 0/9 | 1/1 | - | - |
| `docs/demo/bills.html` | el | Ψηφοφορίες — Demo Node | 4 | 0/0 | 1/1 | - | - |
| `docs/demo/index.html` | el | Demo Node — ekklesia.gr για Δήμους | 9 | 0/0 | 0/0 | - | - |
| `docs/embed/qr-login.html` | el | QR Login — ekklesia.gr | 0 | 0/1 | 0/2 | - | api.ekklesia.gr, www.w3.org |
| `docs/embed/results.html` | el | Αποτελέσματα — ekklesia.gr | 0 | 0/0 | 0/1 | - | api.ekklesia.gr, ekklesia.gr |
| `docs/embed/vote.html` | el | Ψηφοφορία — ekklesia.gr | 0 | 0/0 | 0/1 | - | api.ekklesia.gr, ekklesia.gr |
| `docs/govgr-dimos.html` | el | gov.gr Επαλήθευση — Σχεδιασμός Alpha 0.1 \| εκκλησία | 23 | 1/26 | 1/1 | WebPage | analytics.ekklesia.gr, api.ekklesia.gr, ekklesia.gr, github.com |
| `docs/index.html` | el | εκκλησία — Ψηφιακή Άμεση Δημοκρατία \| ekklesia.gr | 57 | 1/28 | 2/7 | WebApplication, Organization, WebSite | analytics.ekklesia.gr, api.ekklesia.gr, api.github.com, apps.apple.com, ekklesia.gr, f-droid.org, github.com, play.google.com, pnyx.ekklesia.gr |
| `docs/legal.html` | el | Στοιχεία φορέα \| ekklesia.gr | 18 | 0/1 | 0/1 | - | ekklesia.gr, github.com, vlabs.gr |
| `docs/mirror-setup.html` | el | Mirror Setup — εκκλησία | 4 | 0/1 | 1/1 | - | analytics.ekklesia.gr, github.com |
| `docs/municipality/article.html` | el | Το Σύστημα και η Αχίλλειος Πτέρνα κάθε Αλλαγής — εκκλησία... | 2 | 0/0 | 1/1 | Article | analytics.ekklesia.gr, ekklesia.gr, fonts.googleapis.com |
| `docs/municipality/index.html` | el | Για Δήμους & Αντιπροσώπους — ekklesia.gr | 5 | 0/0 | 1/0 | WebPage | analytics.ekklesia.gr, ekklesia.gr, fonts.googleapis.com, github.com |
| `docs/representative.html` | el | εκπρόσωπος — Η εφαρμογή για Λαϊκούς Αντιπροσώπους \| ekkl... | 16 | 0/1 | 1/1 | WebPage | analytics.ekklesia.gr, ekklesia.gr, github.com |
| `docs/sso-verify.html` | el | Σύνδεση — ekklesia.gr | 4 | 0/2 | 1/1 | - | analytics.ekklesia.gr, api.ekklesia.gr, ekklesia.gr, f-droid.org, github.com, play.google.com |
| `docs/tickets/auth/callback.html` | el | Σύνδεση... — εκκλησία | 1 | 0/0 | 2/1 | - | analytics.ekklesia.gr |
| `docs/tickets/index.html` | el | POLIS — εκκλησία | 13 | 1/14 | 3/2 | WebPage | analytics.ekklesia.gr, api.ekklesia.gr, api.qrserver.com, ekklesia.gr, github.com |
| `docs/votes/active.html` | el | Redirect — εκκλησία | 1 | 0/0 | 1/0 | - | analytics.ekklesia.gr, ekklesia.gr |
| `docs/votes/recent.html` | el | Redirect — εκκλησία | 1 | 0/0 | 1/0 | - | analytics.ekklesia.gr, ekklesia.gr |
| `docs/votes/results.html` | el | Redirect — εκκλησία | 1 | 0/0 | 1/0 | - | analytics.ekklesia.gr, ekklesia.gr |
| `docs/wiki/api.html` | el | API — εκκλησία Wiki — εκκλησία | 26 | 0/2 | 1/2 | TechArticle | analytics.ekklesia.gr, ekklesia.gr, github.com |
| `docs/wiki/architecture.html` | el | Αρχιτεκτονική — εκκλησία Wiki — εκκλησία | 28 | 0/2 | 2/2 | TechArticle | analytics.ekklesia.gr, ekklesia.gr, github.com |
| `docs/wiki/broadcasting.html` | el | Broadcasting — Κοινοποίηση & ΜΜΕ \| εκκλησία | 42 | 0/4 | 1/2 | TechArticle | analytics.ekklesia.gr, api.ekklesia.gr, ekklesia.gr, github.com, pnyx.ekklesia.gr, t.me, twitter.com, www.facebook.com, www.linkedin.com |
| `docs/wiki/contributing.html` | el | Contributing — εκκλησία Wiki — εκκλησία | 26 | 0/2 | 1/2 | TechArticle | analytics.ekklesia.gr, ekklesia.gr, github.com |
| `docs/wiki/database.html` | el | Database — εκκλησία Wiki — εκκλησία | 26 | 0/2 | 1/2 | TechArticle | analytics.ekklesia.gr, ekklesia.gr, github.com |
| `docs/wiki/delete-account.html` | el | Διαγραφή Λογαριασμού \| εκκλησία Wiki | 28 | 0/2 | 1/2 | TechArticle | analytics.ekklesia.gr, ekklesia.gr, github.com |
| `docs/wiki/faq.html` | el | FAQ — Συχνές Ερωτήσεις \| εκκλησία | 30 | 0/2 | 1/2 | FAQPage | analytics.ekklesia.gr, ekklesia.gr, github.com |
| `docs/wiki/index.html` | el | Wiki — Τεχνική Τεκμηρίωση \| εκκλησία | 38 | 0/2 | 1/2 | - | analytics.ekklesia.gr, ekklesia.gr, github.com |
| `docs/wiki/modules.html` | el | Modules — εκκλησία Wiki — εκκλησία | 27 | 0/2 | 1/2 | TechArticle | analytics.ekklesia.gr, api.ekklesia.gr, ekklesia.gr, github.com |
| `docs/wiki/privacy.html` | el | Ιδιωτικότητα & GDPR \| εκκλησία Wiki | 32 | 0/2 | 1/2 | TechArticle | analytics.ekklesia.gr, ekklesia.gr, github.com |
| `docs/wiki/roadmap.html` | el | Οδικός Χάρτης & Συχνές Ερωτήσεις — εκκλησία Wiki | 30 | 0/2 | 1/2 | - | analytics.ekklesia.gr, ekklesia.gr, github.com |
| `docs/wiki/security.html` | el | Ασφάλεια & Κρυπτογραφία \| εκκλησία Wiki | 27 | 0/2 | 2/2 | TechArticle | analytics.ekklesia.gr, ekklesia.gr, github.com |
| `docs/wiki/whitepaper.html` | el | Whitepaper v1.0 \| εκκλησία | 31 | 0/2 | 1/2 | TechArticle | analytics.ekklesia.gr, decidim.org, ekklesia.gr, github.com, pol.is, www.hellenicparliament.gr |
| `docs/wiki/zk-voting.html` | el | ZK Voting — Semaphore \| εκκλησία Wiki | 10 | 0/0 | 1/0 | TechArticle | analytics.ekklesia.gr, ekklesia.gr |

## API / URL contracts visible in markup or scripts

| Endpoint / URL | Pages |
|---|---|
| `/api/v1` | `docs/sso-verify.html` |
| `/api/v1/admin/bills` | `docs/demo/admin.html` |
| `/api/v1/admin/deepl/usage` | `docs/community.html` |
| `/api/v1/agent/ask` | `docs/index.html` |
| `/api/v1/analytics/overview` | `docs/wiki/broadcasting.html` |
| `/api/v1/analytics/representation` | `docs/index.html` |
| `/api/v1/arweave/status` | `docs/community.html` |
| `/api/v1/bills` | `docs/index.html`, `docs/wiki/broadcasting.html` |
| `/api/v1/bills/` | `docs/embed/results.html`, `docs/embed/vote.html` |
| `/api/v1/claude/budget` | `docs/community.html` |
| `/api/v1/contact/ngo` | `docs/community.html`, `docs/govgr-dimos.html` |
| `/api/v1/cplm/aggregate` | `docs/index.html` |
| `/api/v1/export/divergence.csv` | `docs/wiki/broadcasting.html` |
| `/api/v1/health/modules` | `docs/wiki/modules.html` |
| `/api/v1/identity/hlr/credits` | `docs/community.html` |
| `/api/v1/newsletter/stats` | `docs/community.html` |
| `/api/v1/newsletter/subscribe` | `docs/index.html` |
| `/api/v1/payments/public/finance` | `docs/community.html` |
| `/api/v1/payments/status` | `docs/community.html` |
| `/api/v1/polis/qr-session` | `docs/embed/qr-login.html`, `docs/tickets/index.html` |
| `/api/v1/polis/qr-session/` | `docs/embed/qr-login.html`, `docs/tickets/index.html` |
| `/api/v1/polis/qr-vote` | `docs/embed/vote.html` |
| `/api/v1/public/cplm` | `docs/wiki/broadcasting.html` |
| `/api/v1/public/cplm/history` | `docs/wiki/broadcasting.html` |
| `/api/v1/public/mirrors/status` | `docs/community.html` |
| `/api/v1/public/representation` | `docs/wiki/broadcasting.html` |
| `/api/v1/public/scraper/status` | `docs/community.html` |
| `/api/v1/public/stats` | `docs/community.html` |
| `/api/v1/vote/` | `docs/embed/results.html`, `docs/embed/vote.html` |
| `/api/v1/vote/results/in-progress` | `docs/index.html` |
| `/api/v1/vote/results/latest` | `docs/index.html` |
| `/api/v3/simple/price` | `docs/community.html` |
| `https://api.coingecko.com/api/v3/simple/price?ids=arweave&vs_currencies=usd` | `docs/community.html` |
| `https://api.ekklesia.gr` | `docs/embed/qr-login.html`, `docs/embed/results.html`, `docs/embed/vote.html` |
| `https://api.ekklesia.gr/api/v1` | `docs/sso-verify.html` |
| `https://api.ekklesia.gr/api/v1/admin/deepl/usage` | `docs/community.html` |
| `https://api.ekklesia.gr/api/v1/agent/ask` | `docs/index.html` |
| `https://api.ekklesia.gr/api/v1/analytics/overview` | `docs/wiki/broadcasting.html` |
| `https://api.ekklesia.gr/api/v1/analytics/representation` | `docs/index.html` |
| `https://api.ekklesia.gr/api/v1/arweave/status` | `docs/community.html` |
| `https://api.ekklesia.gr/api/v1/bills` | `docs/wiki/broadcasting.html` |
| `https://api.ekklesia.gr/api/v1/bills?status=WINDOW_24H&limit=10` | `docs/index.html` |
| `https://api.ekklesia.gr/api/v1/claude/budget` | `docs/community.html` |
| `https://api.ekklesia.gr/api/v1/contact/ngo` | `docs/community.html`, `docs/govgr-dimos.html` |
| `https://api.ekklesia.gr/api/v1/cplm/aggregate` | `docs/index.html` |
| `https://api.ekklesia.gr/api/v1/export/divergence.csv` | `docs/wiki/broadcasting.html` |
| `https://api.ekklesia.gr/api/v1/health/modules` | `docs/wiki/modules.html` |
| `https://api.ekklesia.gr/api/v1/identity/hlr/credits` | `docs/community.html` |
| `https://api.ekklesia.gr/api/v1/newsletter/stats` | `docs/community.html` |
| `https://api.ekklesia.gr/api/v1/newsletter/subscribe` | `docs/index.html` |
| `https://api.ekklesia.gr/api/v1/payments/public/finance` | `docs/community.html` |
| `https://api.ekklesia.gr/api/v1/payments/status` | `docs/community.html` |
| `https://api.ekklesia.gr/api/v1/polis/qr-session` | `docs/tickets/index.html` |
| `https://api.ekklesia.gr/api/v1/polis/qr-session/` | `docs/tickets/index.html` |
| `https://api.ekklesia.gr/api/v1/public/cplm` | `docs/wiki/broadcasting.html` |
| `https://api.ekklesia.gr/api/v1/public/cplm/history?days=30` | `docs/wiki/broadcasting.html` |
| `https://api.ekklesia.gr/api/v1/public/mirrors/status` | `docs/community.html` |
| `https://api.ekklesia.gr/api/v1/public/representation` | `docs/wiki/broadcasting.html` |
| `https://api.ekklesia.gr/api/v1/public/scraper/status` | `docs/community.html` |
| `https://api.ekklesia.gr/api/v1/public/stats` | `docs/community.html` |
| `https://api.ekklesia.gr/api/v1/vote/results/in-progress` | `docs/index.html` |
| `https://api.ekklesia.gr/api/v1/vote/results/latest` | `docs/index.html` |
| `https://api.github.com/repos/NeaBouli/pnyx-community/issues` | `docs/index.html` |
| `https://api.github.com/user` | `docs/index.html` |
| `https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=` | `docs/tickets/index.html` |

## Gaps and risks (observed, not fixed)

Severity here means redesign-relevance, not audit severity. Every item
is input for later phases; nothing below closes an EKA finding.

### 1. Pages without meta description (13)

- `docs/animation-spec/LANDING_SNIPPETS.html`
- `docs/demo/admin.html`
- `docs/demo/bills.html`
- `docs/demo/index.html`
- `docs/embed/qr-login.html`
- `docs/embed/results.html`
- `docs/embed/vote.html`
- `docs/mirror-setup.html`
- `docs/sso-verify.html`
- `docs/tickets/auth/callback.html`
- `docs/votes/active.html`
- `docs/votes/recent.html`
- `docs/votes/results.html`

### 2. Pages without canonical link (10)

- `docs/animation-spec/LANDING_SNIPPETS.html`
- `docs/demo/admin.html`
- `docs/demo/bills.html`
- `docs/demo/index.html`
- `docs/embed/qr-login.html`
- `docs/embed/results.html`
- `docs/embed/vote.html`
- `docs/mirror-setup.html`
- `docs/sso-verify.html`
- `docs/tickets/auth/callback.html`

### 3. Pages without hreflang alternates (18)

- `docs/animation-spec/LANDING_SNIPPETS.html`
- `docs/demo/admin.html`
- `docs/demo/bills.html`
- `docs/demo/index.html`
- `docs/embed/qr-login.html`
- `docs/embed/results.html`
- `docs/embed/vote.html`
- `docs/legal.html`
- `docs/mirror-setup.html`
- `docs/municipality/article.html`
- `docs/municipality/index.html`
- `docs/representative.html`
- `docs/sso-verify.html`
- `docs/tickets/auth/callback.html`
- `docs/tickets/index.html`
- `docs/votes/active.html`
- `docs/votes/recent.html`
- `docs/votes/results.html`

### 4. Pages without viewport meta (4)

- `docs/animation-spec/LANDING_SNIPPETS.html`
- `docs/votes/active.html`
- `docs/votes/recent.html`
- `docs/votes/results.html`

### 5. Duplicate id attributes (1 page(s))

The entries below are pre-existing baseline defects recorded in
`R0_KNOWN_BASELINE_DEFECTS.json`. They are tolerated exactly as recorded;
any other or new duplicate id fails generation closed.

- `docs/wiki/modules.html`: id `dot-mod02` occurs 2 times

### 6. Inline event handler attributes (224 across 22 page(s))

Inline `on*` handlers constrain a future strict CSP (`script-src`
without `unsafe-inline`) and must be migrated before the CSP gate closes.

- `docs/community.html`: 14 handler(s)
- `docs/demo/admin.html`: 1 handler(s)
- `docs/embed/qr-login.html`: 1 handler(s)
- `docs/govgr-dimos.html`: 10 handler(s)
- `docs/index.html`: 26 handler(s)
- `docs/mirror-setup.html`: 1 handler(s)
- `docs/representative.html`: 1 handler(s)
- `docs/sso-verify.html`: 1 handler(s)
- `docs/tickets/index.html`: 18 handler(s)
- `docs/wiki/api.html`: 5 handler(s)
- `docs/wiki/architecture.html`: 5 handler(s)
- `docs/wiki/broadcasting.html`: 23 handler(s)
- `docs/wiki/contributing.html`: 5 handler(s)
- `docs/wiki/database.html`: 5 handler(s)
- `docs/wiki/delete-account.html`: 5 handler(s)
- `docs/wiki/faq.html`: 62 handler(s)
- `docs/wiki/index.html`: 5 handler(s)
- `docs/wiki/modules.html`: 5 handler(s)
- `docs/wiki/privacy.html`: 5 handler(s)
- `docs/wiki/roadmap.html`: 16 handler(s)
- `docs/wiki/security.html`: 5 handler(s)
- `docs/wiki/whitepaper.html`: 5 handler(s)

### 7. Web storage / cookie usage in inline scripts (4 page(s))

- `docs/index.html`: {"sessionStorage": 6}
- `docs/sso-verify.html`: {"localStorage": 3}
- `docs/tickets/auth/callback.html`: {"sessionStorage": 6}
- `docs/tickets/index.html`: {"sessionStorage": 8}

### 8. Non-inline script resources (30 page(s))

External hosts on the public surface are a privacy/CSP decision input
(EKA-30 family). Hosts observed: 2.ekklesia.gr, 3.ekklesia.gr, analytics.ekklesia.gr, api.coingecko.com, api.ekklesia.gr, api.github.com, api.qrserver.com, apps.apple.com, changenow.io, decidim.org, ekklesia.gr, f-droid.org, fonts.googleapis.com, github.com, mirror.204.168.165.143.nip.io, play.google.com, pnyx.ekklesia.gr, pol.is, t.me, twitter.com, vlabs.gr, wa.me, www.coinex.com, www.facebook.com, www.hellenicparliament.gr, www.linkedin.com, www.w3.org.

- `docs/animation-spec/LANDING_SNIPPETS.html`: /animations/js/motion-observer.js
- `docs/community.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/demo/admin.html`: demo-data.js
- `docs/demo/bills.html`: demo-data.js
- `docs/govgr-dimos.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/index.html`: https://analytics.ekklesia.gr/js/script.js, animations/js/motion-observer.js
- `docs/mirror-setup.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/municipality/article.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/municipality/index.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/representative.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/sso-verify.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/tickets/auth/callback.html`: https://analytics.ekklesia.gr/js/script.js, ../config.js
- `docs/tickets/index.html`: https://analytics.ekklesia.gr/js/script.js, config.js, polis.js
- `docs/votes/active.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/votes/recent.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/votes/results.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/api.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/architecture.html`: https://analytics.ekklesia.gr/js/script.js, ../animations/js/motion-observer.js
- `docs/wiki/broadcasting.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/contributing.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/database.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/delete-account.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/faq.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/index.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/modules.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/privacy.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/roadmap.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/security.html`: https://analytics.ekklesia.gr/js/script.js, ../animations/js/motion-observer.js
- `docs/wiki/whitepaper.html`: https://analytics.ekklesia.gr/js/script.js
- `docs/wiki/zk-voting.html`: https://analytics.ekklesia.gr/js/script.js

### 9. Unresolved in-page anchor targets (0 page(s))

Targets may be created by runtime scripts; treat as review candidates,
not proven defects.

- none

### 10. Asymmetric bilingual attributes (0 page(s))

Elements carrying only `data-el` or only `data-en` cannot switch
language correctly. Text-bearing elements without either attribute are a
separate coverage question for the H/I content gate.

- none

### 11. Script-driven pages without static loading/error/empty markers (20)

Markers may be created at runtime; listed pages need manual state
verification in R2-R5 before migration.

- `docs/community.html`
- `docs/demo/admin.html`
- `docs/demo/bills.html`
- `docs/legal.html`
- `docs/mirror-setup.html`
- `docs/municipality/article.html`
- `docs/representative.html`
- `docs/wiki/api.html`
- `docs/wiki/architecture.html`
- `docs/wiki/broadcasting.html`
- `docs/wiki/contributing.html`
- `docs/wiki/database.html`
- `docs/wiki/delete-account.html`
- `docs/wiki/faq.html`
- `docs/wiki/index.html`
- `docs/wiki/modules.html`
- `docs/wiki/privacy.html`
- `docs/wiki/roadmap.html`
- `docs/wiki/security.html`
- `docs/wiki/whitepaper.html`

### 12. Fixed pixel widths above 360px in styles (0 page(s))

Candidates for horizontal-overflow traps on 360px viewports; each needs
visual confirmation, since most sit inside scrollable or max-width
containers.

- none

## Category parity hashes

Per-page and per-surface SHA-256 hashes for every inventory category are
in `R0_DOCS_SURFACE_INVENTORY.json` (`pages[].hashes` and
`surface_hashes`). They are the stable reference for R2-R5 parity
checks. Surface-level rollup:

| Category | SHA-256 |
|---|---|
| api_contracts | `a2547994047732ddf8dbe66690a97f8d488f8cd989002cefc429bea1986f9e29` |
| bilingual | `45f4cb5540cca05e4d1b2c878cbb1b9b59e6cbdea9816dfe41a9dfe5488d78bf` |
| document | `203f336b89712be0934cf95980e6f57c4dea334c9de37df23fa5bfc0de06ccf1` |
| forms | `bb12ec7297fb7297f1705345833c3bec3f3b707ac7a1a35f4a30e89e7b8535b8` |
| interactions | `ee27e11f9756df08a6425a4b7be72cf397b13c1e67e5ead4864a490b2f17b467` |
| json_ld | `99d426c01a1451c18eea1e8e17b3b5052865d21e5355dbb74ebb0f8f6f93ac8f` |
| links | `93c29831811eb50a2315d1739e7a4428e117b23a4170f682ce1354a282747215` |
| media | `4bbfc41968923f68750d510694f29b201d6316b82db7be4f2844a57db12da2cc` |
| meta | `4c725f19c14232e88713d7e9de52f7a11356d11b8668782d854b80590ffc1049` |
| navigation | `92aac8c771a59f341b4acd130f4049b2bfb798e98a1ea9671a7e6dee8a67fbec` |
| resources | `ffbf24c8cad83c21647f28951ab906f30803bf60ef185a9d6f3137103c8fbcf6` |
| responsive | `2757c0bfe606341419cc99bccb8af211aa93d64218d93350f706fed9221516a4` |
| scripts | `a8f79af7817aaec3db45ed9a5797e7fdac7aff68c71bfe9da0818fdb0d1094c4` |
| seo | `9eb175dbd16cf670c64e453f1b4f33b1934e51031b57901488ebf221aa871ec9` |
| states | `f8254b3b38be90ec5838e228e32977d4267b683c66e624effd527bae7c2c9659` |
| storage | `8085006d2a8f31f2810c0c215638957471388b3197645b2214771907274f02ac` |
| styles | `28bf8af0e82e57bbf627e9327ba3b723a2fd50b7cf065e826013f2cd8305cb53` |
| text | `7e509a816239e2652ccb82a3527656f11e9bf77631fd20f7e2031e6af05cce6c` |

Inventory hash: `614528b2cc2ab79973c3fce7e84040c8a57398df950b51cb4beafe02ec70e290`
