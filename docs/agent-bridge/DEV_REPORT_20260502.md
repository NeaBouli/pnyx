# Dev Report — Dashboard Session 01-02.05.2026
## Erstellt von Claude Code | HEAD: 252eeb8

---

## Session-Zusammenfassung

In zwei intensiven Sessions wurde das ekklesia.gr Admin-Dashboard von Null auf ein funktionales 15-Seiten-Tool gebaut und deployed.

### Was gebaut wurde:

| Seite | Funktion | Status |
|---|---|---|
| Overview | 3 Tabs (Uebersicht/Analytics/Finanzen), 8 Live-Kacheln, Scheduler Jobs | LIVE |
| Analytics | Divergence Trends, Top-10, CPLM History, Representation Score | LIVE |
| Bills | Tabelle, Filter, New-Bill Modal, AI Review, Text Scrape, Export | LIVE |
| Votes | BarChart, PieChart, MP Ranking, Representation | LIVE |
| CPLM | ScatterChart + LineChart 30 Tage | LIVE |
| System | 24 Module Badges, HLR Credits, Arweave, Push, gov.gr Gates | LIVE |
| AI | Ollama/Claude/DeepL Status, 3 Repair Buttons | LIVE |
| Forum | Discourse Version (via Server-Proxy), Bill-Sync Status | LIVE |
| Finance | HLR Credits, Arweave Balance, Payments, Claude Budget | LIVE |
| Stats | Analytics Overview, 4 Phase-2 Platzhalter | LIVE |
| Settings | 5 Tabs (Module/Scraper/Apps/Compass/KB) | LIVE |
| Nodes | Server-Status, Scheduler, Nodes-Tabelle, Register-Modal | LIVE |
| Gov | gov.gr Gates (4 Karten live aus API), Progress | LIVE |
| Users | Phase 2 Platzhalter | PLATZHALTER |
| Logs | Health Panel, Auto-Refresh | TEILWEISE |

### Architektur:
- Next.js 14, Tailwind CSS, recharts
- GitHub OAuth (NextAuth v5) + GITHUB_ALLOWLIST
- 6 Rollen: SUPER_ADMIN, SYSTEM_ADMIN, CONTENT, ANALYST, SUPPORT, NODE_ADMIN
- Sidebar mit 3 Gruppen + Super/Node Toggle
- Server-side Discourse Proxy (/api/discourse)
- Standalone Docker Build (node:20-alpine, Port 3000)
- Traefik Router (dashboard.ekklesia.gr, Let's Encrypt SSL)

---

## Gefixte Bugs (Session):

1. docker-compose: Dashboard unter volumes statt services
2. TypeScript: unknown-to-ReactNode (6 Dateien, mehrere Runden)
3. Dockerfile: fehlender public/ Ordner
4. Traefik: Port 3001 → 3000 (standalone default)
5. NextAuth: AUTH_TRUST_HOST fuer Reverse Proxy
6. CORS: dashboard.ekklesia.gr zu API allow_origins
7. System Module: [object Object] → parsed {name, status}
8. Forum: CORS → Server-side Proxy
9. Ollama: falsches Feld (providers.ollama.status)
10. HLR Progressbar: overflow-hidden + Math.min
11. Deutsche Texte → Griechisch (5 Dateien)
12. gov.gr: "Aktivierungsbedingungen" → Backend-Fix

---

## Offene Items (25 fehlende Dashboard-Features):

### Prioritaet HOCH (vor Public Beta):

| # | Feature | Benoetigt | Seite |
|---|---|---|---|
| 1 | Bill Edit Modal (PATCH /admin/bills/{id}) | Nur Dashboard | bills |
| 2 | Party Votes setzen (POST /admin/bills/{id}/party-votes) | Nur Dashboard | bills |
| 3 | Push Notification senden (POST /notify/send) | Nur Dashboard | system/neue Seite |
| 4 | Log-Analyse (POST /admin/logs/explain) | Nur Dashboard | logs |
| 5 | Diavgeia Scrape ausloesen (POST /admin/diavgeia/scrape) | Nur Dashboard | settings |
| 6 | VAA Thesen verwalten (CRUD) | Backend + Dashboard | settings |

### Prioritaet MITTEL:

| # | Feature | Benoetigt | Seite |
|---|---|---|---|
| 7 | Bill Text manuell setzen (POST /admin/bills/{id}/set-text) | Nur Dashboard | bills |
| 8 | Scraper fetch URL (POST /scraper/fetch) | Nur Dashboard | ai |
| 9 | Scraper bulk import (POST /scraper/import) | Nur Dashboard | ai |
| 10 | Export Divergence CSV + Parties JSON Links | Nur Dashboard | bills |
| 11 | MP Compare Detail (/mp/compare/{party}) | Nur Dashboard | votes |
| 12 | Identity Revoke (admin) | Nur Dashboard | users |
| 13 | Diavgeia Org-Cache Refresh | Nur Dashboard | settings |
| 14 | Newsletter Events aus Redis anzeigen | Nur Dashboard | finance |

### Prioritaet NIEDRIG (Phase 2):

| # | Feature | Benoetigt | Seite |
|---|---|---|---|
| 15 | PayPal IPN Webhook | Backend neu | payments |
| 16 | Force Update Toggle mit Backend-Effekt | Backend PATCH Endpoint | settings |
| 17 | HLR Provider Switch | Backend ENV Toggle | settings |
| 18 | gov.gr Gates manuell setzen | Backend PATCH Endpoint | gov |
| 19 | Claude Budget PATCH | Backend Endpoint | settings |
| 20 | 4 fehlende Scheduler-Jobs im Status | Backend erweitern | system |
| 21 | App Download-Statistiken | Play Console API | stats |
| 22 | Website Besucher | Plausible installieren | stats |
| 23 | Crash Reports | Sentry installieren | stats |
| 24 | Partei-Positionen CRUD | Backend + Dashboard | settings |
| 25 | Node-Sync effektiv implementieren | Backend + Dashboard | nodes |

---

## Bekannte Backend-Bugs:

1. `/api/v1/analytics/votes-timeline` gibt 500 (leere citizen_votes Tabelle, row.vote Enum-Fehler)
2. Discourse about.json liefert keine topic_count/post_count (Discourse-Config oder Version)
3. 4 von 8 Scheduler-Jobs nicht im /scraper/jobs Response (bill_lifecycle, cplm_refresh, greek_topics, forum_sync)

---

## PayPal-Spenden Tracking (Empfehlung):

**Option A — PayPal IPN Webhook (empfohlen):**
- POST /api/v1/payments/webhook/paypal
- PayPal sendet IPN bei jeder Zahlung
- Backend zaehlt in Redis: `paypal:donations:count`, `paypal:donations:total`
- Dashboard zeigt: "PayPal Spenden: X EUR (Y Transaktionen)"

**Option B — PayPal API Polling:**
- PayPal REST API /v1/reporting/transactions
- Alle 6h Transaktionen abrufen
- Filtere nach paypalme/VendettaLabs

**Empfehlung:** Option A (IPN) — einfacher, Echtzeit, kein Polling noetig.

---

## Naechste Session Empfehlung:

1. Top-6 fehlende Features implementieren (Items 1-6)
2. votes-timeline Backend-Bug fixen
3. Scheduler-Jobs vollstaendig im Dashboard anzeigen
4. PayPal IPN Webhook bauen
5. Dashboard UI/UX polieren (responsive, mobile)

---

*Erstellt: 2026-05-02 | Claude Code (Opus 4.6)*
