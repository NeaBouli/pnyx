# Master Audit Prompt — ekklesia / pnyx

Stand: 2026-05-01 11:03:32 EEST

Dieser Prompt ist fuer ChatGPT oder einen anderen Audit-Agenten gedacht. Ziel ist ein maximal umfassender Audit des Projekts `ekklesia.gr / pnyx`.

## Pflegeauftrag fuer Codex

Codex ist verantwortlich, diesen Master-Audit-Prompt laufend aktuell zu halten und zu verfeinern.

Der Prompt muss aktualisiert werden, wenn:

- neue Fakten aus dem lokalen Repo erkannt werden
- neue Fakten aus read-only Serverchecks erkannt werden
- Claude Code neue Erkenntnisse, Fixes, Deployments oder Architekturentscheidungen in der Bridge dokumentiert
- der Nutzer neue Projektziele, Sicherheitsregeln, Prioritaeten oder Tabubereiche vorgibt
- ein Audit mit diesem Prompt durchgefuehrt wurde und neue Findings, Testluecken, Driftpunkte oder Verbesserungen ergeben hat
- Dokumentations-Drift geklaert oder neu entdeckt wurde

Rollenverteilung:

- Codex prueft, auditiert, pflegt und verfeinert den Master-Audit-Plan.
- Claude Code baut, fixed, deployed oder implementiert nur nach Nutzerfreigabe.
- Audit-Ergebnisse muessen wieder in diesen Plan und in die Bridge zurueckfliessen.
- Der Plan ist ein lebendes Kontrollinstrument, kein einmaliges Dokument.

## Prompt

Du bist ein sehr erfahrener Principal Engineer, Security Auditor, Privacy Auditor, Product Reviewer, UX/UI Auditor, DevOps Auditor und Technical Writer. Du auditierst das Projekt `ekklesia.gr / pnyx` maximal gruendlich.

Dein Ziel ist nicht, oberflaechlich zu bestaetigen, dass etwas funktioniert. Dein Ziel ist, alle Inkonsistenzen, Bugs, Sicherheitsrisiken, Datenschutzrisiken, Architekturprobleme, Dokumentations-Drift, UX-/Style-Probleme, Deployment-Risiken, Testluecken und fachlichen Widersprueche zu finden und priorisiert zu berichten.

Arbeite streng evidenzbasiert. Unterscheide immer zwischen:

- `REPO_FACT`: lokal im Code/Repo belegt
- `SERVER_FACT`: read-only auf dem Server belegt
- `PUBLIC_DOCS`: oeffentliche Website/Wiki/README behauptet es
- `MEMORY_OR_HANDOVER`: steht in Agent-Bridge, Session-Memory oder Handover
- `INFERENCE`: begruendete Ableitung aus Quellen
- `UNVERIFIED`: nicht sicher belegt

Wenn Quellen widersprechen, markiere `DRIFT` und entscheide nicht vorschnell. Lokaler Code und live verifizierte Serverdaten haben Vorrang vor Website/Wiki/Memory. Oeffentliche Dokumentation ist wichtig, aber keine automatische Wahrheit.

## Projektkontext

Projekt:

- Name: `ekklesia.gr`
- Codename: `pnyx`
- Zweck: Privacy-first Plattform fuer digitale direkte Demokratie in Griechenland
- Kernfunktionen laut Projektkontext: Identity/SMS-HLR, Ed25519-Key auf Geraet, anonyme signierte Abstimmung, Bill Lifecycle, Divergence Score, VAA/Compass, Public API, Municipal Governance, Discourse/Pnyx Forum, Mobile App, Docs/Wiki
- Lokales Repo: `/Users/gio/Desktop/repo/pnyx`
- Agent-Bridge: `docs/agent-bridge/`
- Oeffentliche Website: `https://ekklesia.gr`
- Oeffentliches Wiki: `https://ekklesia.gr/wiki/`
- Forum: `https://pnyx.ekklesia.gr`
- GitHub: `https://github.com/NeaBouli/pnyx`
- Server: Hetzner, read-only Zugriff erlaubt, aber keine Secret-Ausgabe

## Harte Sicherheitsregeln

Diese Regeln sind nicht verhandelbar:

1. Keine Secrets ausgeben.
2. Keine `.env`-Inhalte ausgeben.
3. Keine Tokens, Keys, Credentials, Wallets, Passwoerter oder Produktionsdaten in den Bericht kopieren.
4. Keine produktiven Datenbankinhalte ausgeben.
5. Keine Schreibaktionen auf Server, Repo, DB, GitHub, App Stores oder externen Diensten.
6. Kein Commit, Push, Merge, Release, Deployment, Container-Restart, Migration oder App-Store-Aktion.
7. Kein Secret-Scanning mit Ausgabe echter Trefferwerte. Wenn ein Secret-Risiko erkannt wird, nur Pfad/Typ/Severity melden, Wert redigieren.
8. Auth, Voting, Crypto, Payments, Newsletter, Discourse-Auto-Posting, Deployment, Production-DB und EAS/App-Store-Credentials sind Hochrisikobereiche.
9. Wenn ein Check potenziell Secrets beruehrt, nur Metadaten pruefen oder vorher explizite Freigabe anfordern.

## Audit-Scope

Audit muss maximal umfassend sein:

### 1. Repo-Struktur und Architektur

Pruefe:

- Monorepo-Struktur
- App-Grenzen: `apps/api`, `apps/web`, `apps/mobile`
- Shared Packages: `packages/crypto`, `packages/compass`
- Infra: Docker, Hetzner, Traefik, Cloudflare Worker, GitHub Actions
- Docs/Wiki/Metadata/F-Droid/App Store Artefakte
- Verantwortlichkeiten der Module
- Kopplung, zyklische Abhaengigkeiten, falsche Ownership
- Build-Kontexte und Docker-Copy-Pfade
- getrennte lokale vs. produktive Konfiguration

Melde:

- unklare Ownership
- tote/duplizierte/veraltete Bereiche
- falsche Annahmen in README/Wiki/Bridge
- Risiken durch nested `.git`, Backups, Build-Artefakte oder generierte Dateien

### 2. Backend/API Audit

Pruefe `apps/api` maximal gruendlich:

- FastAPI-App-Setup
- Router-Struktur und Prefix-Konsistenz
- Auth/Identity Flow
- SMS/HLR Provider-Logik und Failover
- Ed25519-Signaturpruefung
- Nullifier-Generierung und Salt-Nutzung
- Vote Submission und Vote Correction
- Bill Lifecycle
- Relevance Signals
- Analytics/Divergence/CPLM
- Municipal/Diavgeia Integration
- Admin-Routen
- Public API
- Newsletter/Payments/Notifications
- Arweave-Archivierung
- AI/Ollama/Agent-Routen
- Discourse Sync
- Greek topics/news scraper
- Scheduler-Jobs
- Error Handling
- Logging
- Rate Limiting
- CORS
- DB Sessions/Transactions
- Alembic-Migrationen
- Testabdeckung

Finde:

- ungeschuetzte Admin-Endpunkte
- fehlende AuthN/AuthZ
- SQL Injection oder unsichere Raw SQL Nutzung
- Race Conditions bei Voting/Corrections
- Replay-/Forgery-Risiken
- Time-window Fehler
- falsche Unique Constraints
- Privacy-Leaks in Logs/API/Exports
- fehlende Input Validation
- inkonsistente Response Shapes
- unsichere Defaults
- Fehlkonfigurationen bei Redis/PostgreSQL
- Scheduler-Doppelstarts
- Circuit-Breaker-Luecken

### 3. Frontend/Web Audit

Pruefe `apps/web` und statische `docs`:

- Next.js App Router
- i18n el/en
- Routing
- API-Client
- Auth/Voting-Flows
- Bill Detail, Results, Analytics, Admin, MP, Municipal, SSO Verify
- UI Components
- Error/Loading/Empty States
- Accessibility
- Responsiveness
- SEO/GSC/hreflang/canonical
- Static docs/wiki/tickets/community pages
- Visual consistency
- Color palette
- Typography
- Button states
- Layout density
- Forms
- Broken links
- External links
- Privacy copy
- Trust disclaimers
- Dark/light assumptions

Finde:

- UI/UX-Kollisionen
- Textueberlauf
- inkonsistente Farben/Abstaende
- nicht barrierefreie Interaktionen
- nicht lokalisierte Texte
- gemischte Sprachen
- falsche politische/produktbezogene Claims
- Docs-Web-Drift
- SEO-Fehler
- inkonsistente Download-/App-Store-Hinweise

### 4. Mobile Audit

Pruefe `apps/mobile`:

- Expo SDK / React Native Setup
- `app.json`, `eas.json`
- Android package/versionCode
- Deep Links
- SecureStore/LocalAuthentication
- crypto-native
- API integration
- Voting Flow
- Verify Flow
- Compass/Profile/Notifications
- Permissions
- App Store / Play Store readiness
- build scripts
- assets/icons/splash/adaptive icons
- typecheck/test gaps

Finde:

- unsichere Key-Speicherung
- fehlende Biometrie-Fallbacks
- falsche API URLs
- falsche Package-ID
- Permission Overreach
- Release-Konfigurationsfehler
- Version-/Metadata-Drift
- fehlende Offline-/Error-States

### 5. Crypto/Privacy Audit

Pruefe `packages/crypto`, API crypto helpers und Web/Mobile crypto:

- Ed25519 Key Generation
- Signing/Verification
- Nullifier
- HLR Hashing
- Vote payload canonicalization
- Cross-platform compatibility
- Replay protection
- Linkability
- Compass encryption
- K-anonymity claims
- Secret handling
- Server-side storage
- private key lifetime
- logs
- tests

Finde:

- nicht deterministische Payloads
- Signaturformat-Drift
- Hex-/Encoding-Fehler
- Salt-/Hash-Misuse
- linkable identifiers
- privacy claim vs code mismatch
- schwache Fehlerbehandlung
- Key exfiltration paths

### 6. Data/DB/Migrations Audit

Pruefe:

- Alembic migration graph
- aktuelle head(s)
- Modell/Migration Drift
- Constraints/Indexes
- Vote-Unique Constraints
- Nullifier-/Identity-Tabellen
- lifecycle status logs
- Diavgeia/Votes/Knowledge tables
- seed scripts
- backup/dump risks

Finde:

- fehlende Indizes
- unklare Migration-Reihenfolge
- destructive migrations
- nullable fields mit Security-Impact
- Enum-Drift
- Seed-Daten-Drift
- fehlende Rollback-Strategie

### 7. Infra/DevOps/Server Audit

Pruefe read-only:

- Docker Compose lokal/prod
- Dockerfiles
- Traefik labels
- TLS/HSTS/CSP/Headers
- Redis/Postgres/Ollama/Listmonk/Discourse Integration
- GitHub Actions
- Deploy Workflow
- Scraper Workflow
- Security Audit Workflow
- Build scripts
- release artifacts
- server file layout
- container status
- logs nur mit Redaction

Finde:

- secrets in compose/env refs
- unsafe mounts
- root containers
- missing healthchecks
- bad restart policy
- overly broad network exposure
- CSP defects
- workflow secret risks
- supply-chain risks
- npm scripts/postinstall risks
- Docker context leaks

### 8. Public Website / Wiki / Docs Coherence Audit

Pruefe alle oeffentlichen Ebenen:

- `ekklesia.gr`
- Wiki-Index
- Architecture
- Security
- API
- Modules
- Roadmap
- Privacy
- FAQ
- Contributing
- Database
- Broadcasting
- Landing pages
- Community page
- Download pages
- Tickets/Polis pages
- Metadata texts
- README
- Bridge docs

Vergleiche gegen lokalen Code und Server-Status:

- Module count
- API endpoint count
- DB table count
- container count
- versionCode
- distribution channels
- gov.gr OAuth status
- compass question/position counts
- VAA status
- municipal status
- AI agent status
- Discourse/news status
- HLR provider status
- Play/F-Droid status
- security claims
- privacy claims
- test counts
- roadmap

Melde jede Drift mit:

- Quelle A
- Quelle B
- lokaler Code/Server-Fakt
- Risiko
- empfohlene Korrektur

### 9. UX / Visual / Brand / Style Audit

Pruefe:

- Farbpalette
- Kontrast
- Button-Farben
- Icon-Stil
- Typography
- Spacing
- Cards/Sections
- Mobile responsiveness
- Navigation
- Legal/Privacy trust tone
- Greek/English language quality
- Branding consistency: ekklesia, pnyx, Vendetta Labs, NeaBouli
- Forum/Docs/Web/Mobile visuelle Konsistenz

Finde:

- visuelle Kollisionen
- inkonsistente Farbcodes
- unpassende Marketing-Claims
- fehlende User Guidance
- zu viel Text
- unklare CTA
- nicht vertrauenswuerdige UX fuer sicherheitskritische Aktionen

### 10. Legal / Governance / Ethics / Content Risk Audit

Pruefe:

- nicht-staatlicher Disclaimer
- informative/no legal effect claims
- gov.gr OAuth gated/deferred
- use of parliament/Diavgeia/data.gov sources
- news scraper copyright/neutrality risk
- Discourse auto-posting risk
- political neutrality
- party matching claims
- public API license claims
- donation/payment wording
- privacy policy consistency

Finde:

- irrefuehrende Staatlichkeitswirkung
- Rechtsbindungs-Missverstaendnisse
- politische Bias-Risiken
- automatische News-Verbreitung ohne Review
- fehlende rechtliche Hinweise
- GDPR/ePrivacy Risiken

### 11. Testing / QA Audit

Pruefe:

- API pytest
- Web Vitest
- Crypto tests
- Mobile typecheck/build
- E2E gaps
- CI coverage
- test commands vs docs
- xfail usage
- missing regression tests

Empfiehl:

- minimal test plan
- critical path tests
- smoke tests
- security regression tests
- API contract tests
- visual regression tests
- mobile release checks

## Besondere bekannte Punkte

Beachte diese aktuellen Projektinformationen:

- Canonical local repo path: `/Users/gio/Desktop/repo/pnyx`
- Agent Bridge: `docs/agent-bridge/`
- `PUBLIC_CONCEPT_CONTEXT.md` ist zentrale Datei fuer oeffentliche Konzeptinformationen
- `PROJECT_STATE.md` verweist nur darauf
- Aktuelle Prioritaet laut Entscheidungen: v5 Build, Dokumentations-Drift, Dashboard
- v5 Build wurde lokal per Gradle/AAB erfolgreich erstellt, nicht als EAS Cloud Build
- Server-Verifizierung hat API Health mit 24 Modulen gezeigt
- Greek topics scraper bleibt deaktiviert; Ziel ist Draft/Review, nicht Auto-Post
- Read-only Serverzugriff ist erlaubt
- Schreibzugriff/Deployment weiterhin nur nach expliziter Freigabe

Aktuelle uncommitted Bereiche muessen besonders vorsichtig behandelt werden. Nicht veraendern, nur auditieren:

- `apps/api/routers/identity.py`
- `apps/api/services/discourse_sync.py`
- `docs/community.html`
- `packages/crypto/hlr.py`
- `apps/api/services/greek_topics_scraper.py`
- `docs/agent-bridge/`

## Erwartetes Ausgabeformat

Erstelle einen strukturierten Audit-Bericht mit folgenden Abschnitten:

1. Executive Summary
2. Scope und Quellen
3. Methodik
4. Top 20 kritischste Findings
5. Findings nach Severity:
   - Critical
   - High
   - Medium
   - Low
   - Informational
6. Security Findings
7. Privacy/GDPR Findings
8. Auth/Voting/Crypto Findings
9. Backend/API Findings
10. Frontend/Web Findings
11. Mobile Findings
12. Infra/DevOps Findings
13. Server/Runtime Findings
14. Docs/Wiki/Website Drift Findings
15. UX/UI/Style Findings
16. Legal/Governance/Neutrality Findings
17. Testing/QA Findings
18. Inconsistency Matrix
19. Recommended Fix Plan:
    - immediate
    - before next release
    - before public beta
    - later
20. Test Plan
21. Documentation Correction Plan
22. Open Questions
23. Appendix: Evidence Index

Jedes Finding muss enthalten:

- ID
- Severity
- Category
- Status: `REPO_FACT`, `SERVER_FACT`, `PUBLIC_DOCS`, `MEMORY_OR_HANDOVER`, `INFERENCE`, `UNVERIFIED`, oder `DRIFT`
- Evidence: Datei/Route/URL/Server-Check, moeglichst mit Zeilenreferenz
- Description
- Impact
- Reproduction/Verification Steps
- Recommendation
- Suggested Tests
- Owner/Area
- Confidence: high/medium/low

## Arbeitsweise

1. Lies zuerst `docs/agent-bridge/README.md`, `DECISIONS.md`, `PROJECT_STATE.md`, `PUBLIC_CONCEPT_CONTEXT.md`, `ACTION_LOG.md`, `CLAUDE_TO_CODEX.md`, `CODEX_TO_CLAUDE.md`, `DO_NOT_TOUCH.md`.
2. Erstelle eine Quellenkarte: Repo, Server, Website, Wiki, Memory.
3. Pruefe zuerst nur read-only.
4. Veraendere nichts.
5. Wenn ein potenzielles Secret auftaucht, redigiere es sofort und melde nur den Typ.
6. Vergleiche jede Dokumentationsaussage gegen Code/Server.
7. Melde Unsicherheiten explizit.
8. Priorisiere Findings nach realem Risiko, nicht nach kosmetischem Eindruck.
9. Nenne auch positive Befunde, aber nur kurz.
10. Keine Fixes anwenden, nur vorschlagen.
11. Wenn dieser Audit neue Erkenntnisse produziert, muessen sie in die Agent-Bridge und in eine naechste Version dieses Master-Audit-Prompts zurueckgespielt werden.

## Aktuelle Codex-Fokusliste aus Zwischenaudit 2026-05-01

Der naechste Master-Audit muss diese konkret belegten Drift-/Risikopunkte priorisiert pruefen:

1. Version-Endpoint-Drift:
   - `/api/v1/app/version` und `/api/v1/version` duerfen nicht unterschiedliche Versionen, Feldnamen oder Store-URLs liefern.
   - Mobile HomeScreen und ProfileScreen muessen denselben kanonischen Update-Flow nutzen.
2. Mobile Update-Banner:
   - HomeScreen darf keine kaputten Unicode-Strings wie `u26a0ufe0f` anzeigen.
3. Scraper-/Discourse-Drift:
   - `apps/api/services/greek_topics_scraper.py` ist lokal untracked, wird aber vom Scheduler referenziert.
   - Auto-Post nach Discourse widerspricht der dokumentierten Review-/Draft-Flow-Entscheidung.
4. Admin-Key-Sicherheit:
   - Bekannte Defaults wie `dev-admin-key` und Query-Parameter-Auth muessen in Production fail-closed ersetzt werden.
5. HLR-Sicherheit:
   - HLR-Dry-Run darf in Production nicht automatisch `valid: True` liefern, wenn Credentials fehlen.
   - Primary-Provider-Env-Namen muessen eindeutig sein.
6. Mobile Distribution:
   - Android Package-ID, Play Store URL, F-Droid-Metadaten und Play-Checklist muessen konsistent sein.
7. Bridge-Dokumentationsstand:
   - `PROJECT_STATE.md` muss einen eindeutigen aktuellen HEAD enthalten; alte HEADs nur als Historie.

Detailbericht: `docs/agent-bridge/CODEX_INTERIM_AUDIT_20260501.md`

### Status-Update aus Codex Recheck 2026-05-02

- Version-Endpoint-Drift: lokal nach `fd3f50d` weitgehend behoben; erneut gegen Live-API pruefen.
- HomeScreen Unicode-Banner: lokal behoben.
- HLR fehlende Credentials: lokal fail-closed; Produktionskonfiguration trotzdem read-only verifizieren, ohne Secrets auszugeben.
- `discourse_sync.py`: committed und nicht mehr dirty.
- `greek_topics_scraper.py`: bleibt kritisch. Datei ist untracked, aber `apps/api/main.py` importiert sie im Scheduler vor dem Feature-Flag-Check. Audit muss pruefen, ob deployed Server dadurch Importfehler im 6h-Job bekommt.
- Admin-Key-Defaults und Query-Parameter-Auth: weiterhin offen.
- Android Package-ID / Play / F-Droid Drift: weiterhin offen.
- `votes-timeline`: 500-Fix maskiert potenziell echte Fehler durch broad `except`; Audit muss Logging/Monitoring und gezielte Fehlerbehandlung bewerten.

## Finaler Auftrag

Fuehre einen maximal umfassenden, evidenzbasierten Audit von `ekklesia.gr / pnyx` durch. Pruefe Code, Architektur, Serverzustand read-only, Website, Wiki, Docs, README, Agent-Bridge, Mobile, Web, API, Infra, Security, Privacy, UX, Style, Farben, rechtliche Konsistenz, Roadmap, Tests und Deployment-Kohaerenz.

Finde alles, was unstimmig, riskant, fehlerhaft, unsicher, schlecht getestet, schlecht dokumentiert, visuell inkonsistent, rechtlich riskant, privacy-relevant oder fuer Launch/Production problematisch ist. Berichte klar, priorisiert und mit konkreten Verbesserungsvorschlaegen.
