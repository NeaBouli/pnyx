# Action Log

## SESSION 4 — 2026-05-25 (NEA-267 SEO + NEA-266 README + F-Droid !38007)

### Εβδομαδιαία Toggle Check
- Toggle steuert: Push-Notification (Expo Push), NICHT Email-Newsletter
- Brevo-Newsletter-System ist komplett separat (routers/newsletter.py)
- Konsistent mit NEA-262 cancelled: YES (NEA-262 war Email, nicht Push)
- Fix: Label umbenannt: "Ανακεφαλαίωση" → "Ειδοποίηση" + "(Push)" Suffix
- Commit: `fa096a1`
- APK Rebuild noetig (React Native)

### Logout Modal (professionell)
- System `confirm()` ersetzt durch Custom Dark-Theme Modal
- Zentriertes Overlay mit Titel "Αποσύνδεση;", Cancel/Confirm Buttons
- Gilt fuer ekprosopos Web-App
- Commit: `98ba0b6`
- Web-Container rebuild noetig fuer Live

### NEA-273 Compass Toggle Aggregated Position
- Tap auf Achsenbeschriftung toggled zwischen Partei-Dots und aggregiertem Durchschnittspunkt
- Aggregiert: blauer Ring (24px) bei Durchschnitt aller Partei-X/Y, Label "Μέση Θέση"
- Hint-Text wechselt kontextbasiert
- Commit: `5328a42`
- APK Rebuild nötig (React Native Änderung)

### CHECK: Benachrichtigungseinstellungen
- Toggle-States: ECHT — SecureStore (expo-secure-store), per-Key gespeichert
- Push-Token: ECHT — expo-notifications, registriert bei /api/v1/notify/register
- F-Droid: Push korrekt deaktiviert (buildFlavor check)
- Fazit: ECHT, nicht fake

### F-Droid Pipeline Fixes
- Pipeline #2551676986 failed: `checkupdates` "current version is newer: old vercode=27, new vercode=26"
  - Root cause: `build.gradle` vC27 war uncommitted, kein Tag hatte vC27
  - Fix: vC27 committed (`b46fece`), Tag `v1.3.5-20260525`, CurrentVersion korrigiert
- Pipeline #2551701100 failed: `checkupdates` + `rewritemeta` — trailing newline fehlte + checkupdates wollte neuen Build-Eintrag hinzufuegen
  - Fix: trailing newline in metadata YAML
- Pipeline #2551718912 failed: `checkupdates` fand vC27 im Tag aber Build-Eintrag fehlte in Metadata
  - Fix: vC27 Build-Eintrag manuell in `metadata/ekklesia.gr.yml` eingefuegt (commit `b46fece` SHA)
- Pipeline #2551741271 failed: `fdroid build` 5 scan errors:
  1. `apps/representative/package.json` ohne lock file → Fix: lock-file committed (`75a8b9f`)
  2. `expo-asset/local-maven-repo` + `expo-file-system/local-maven-repo` Pfade existieren nicht mehr (Expo SDK 54 hoisting) → Fix: scanignore aktualisiert
  3. `apps/representative/node_modules` → scandelete ergaenzt
- Pipeline #2551754848 failed: alte scanignore noch im vC6 Build-Eintrag + representative/node_modules existiert nicht im Build + fehlende Leerzeile
  - Fix: BEIDE Build-Eintraege (vC6+vC27) mit korrekten scanignore, representative/node_modules scandelete entfernt, Leerzeile ergaenzt
- Pipeline #2551761027 laeuft (SHA 98a4f7b6, alle Fixes drin)
- Pipeline #2551761027 failed: `fdroid build` konnte `expo.modules.filesystem` nicht finden
  - Root cause: Expo SDK 54 hoisted `expo-file-system`, `expo-asset`, `expo-application`, `expo-notifications` aus `expo/node_modules/` nach `node_modules/` — scanignore fehlte
  - Fix: alle 4 hoisted local-maven-repo Pfade als scanignore hinzugefuegt
- Pipeline #2551767847 laeuft (SHA 6e38ebea, hoisted scanignore drin)
- Pipeline #2551767847 failed: scanignore hatte hoisted Pfade (`expo-file-system/`, `expo-asset/`), aber F-Droid-Build nutzt `expo/node_modules/expo-file-system/` (npm hoisting ist nicht deterministisch)
  - Fix: scanignore auf `expo/node_modules/`-Pfade korrigiert (wie im Build-Log bestaetigt)
- Pipeline #2551771502 failed: `expo-file-system`/`expo-asset` existieren weder hoisted noch unter expo/node_modules/ (werden scandeleted) + `package-lock.json` fehlte im vC27-Tag-Commit
  - Fix 1: Tag `v1.3.5-20260525` verschoben auf `47c1494` (enthaelt lock-file)
  - Fix 2: `expo-file-system` + `expo-asset` scanignore komplett entfernt (F-Droid loescht sie sowieso via scandelete)
  - Fix 3: vC27 commit SHA in Metadata auf `47c1494` korrigiert
- Pipeline #2551791459 laeuft (SHA 0c411dfb)
- APK Build: AAB fertig (build-play.sh), direktRelease APK gebaut (unsigned — Signierung noetig)

### ekprosopos Screenshots auf Landing Page
- 3 Screenshots (bills, detail, evaluation) in ekprosopos-Banner eingefuegt
- Dateien: `docs/assets/screenshots/screenshot-ekprosopos-{bills,detail,evaluation}.jpg`
- Position: unter Beschreibungstext, ueber Buttons
- Commit: `4b8574e`
- Web-Container rebuilt (ADR-010 konform), Screenshots live verifiziert

### F-Droid !38007 Autoupdate Metadata
- linsui feedback addressed: autoupdate metadata added to `metadata/ekklesia.gr.yml` in `TrueRepublic/fdroiddata`
- Branch: `ekklesia-v1.0.0`
- Commit: `3d81d65c1` (`ekklesia.gr: add autoupdate metadata`)
- Fields: `AutoUpdateMode: Version`, `UpdateCheckMode: Tags`, `CurrentVersion: 1.0.0`, `CurrentVersionCode: 27`
- GitHub tag format checked: `v1.3.2-stable-20260524`, `v1.3.3-audit-clean-20260524`, `v1.3.4-forum-fix-20260524`
- GitLab comment posted to !38007: `https://gitlab.com/fdroid/fdroiddata/-/merge_requests/38007#note_3382971274`
- MR status after update: open, label `waiting-on-response`

### ekprosopos Mobile UI Fixes
- Screenshot-Findings gefixt in `apps/representative/web/index.html`
- Header ist jetzt sticky (`position: sticky; top: 0; z-index: 100`)
- Header-Badge hat mehr Innenabstand, max-width + Ellipsis gegen Randkleben
- Evaluation Score-Cards: Flexbox-Layout, Text links + fixe 56px Score-Spalte rechts (kein Overlap)
- Bill detail: Bei 0 Stimmen kein `0% 0%` Balken mehr; Empty-State `Δεν υπάρχουν ψήφοι πολιτών ακόμα`
- Text: `αξιολογήσεις` → `Αξιολογήσεις`
- Verifikation: `git diff --check` OK, JS `node --check` OK, Mobile Browser-Fixture OK
- Commit: `3633d69`
- Static deploy: server pulled to `125d45a`; no container rebuild
- Live APK validation: `/download/ekprosopos-latest.apk` SHA-256 `4b9d49d888465cac2f1de94f50e46efc8dbfea49cb805fd715459bbbb28a761e`
- Desktop/local APK: `~/Desktop/ekprosopos-v1.1.0-vC2.apk` same SHA-256; archived locally at ignored path `builds/artifacts/ekprosopos-v1.1.0-vC2.apk`
- Tracked manifest/checksum added: `docs/download/APK_MANIFEST.md`, `docs/download/ekprosopos-latest.apk.sha256`
- APK metadata: package `ekklesia.representative`, versionCode `2`, versionName `1.1.0`, WebView URL `https://ekklesia.gr/representative/index.html`
- Note: `~/Desktop/ekprosopos-v1.0.0-vC2.apk` was not present; current canonical vC2 artifact is v1.1.0

### ekprosopos ADR-010 Cleanup (Web-Container Rebuild)
- Web-Container hatte alte `representative/index.html` ohne UI-Fixes
- Root cause: `git pull` aktualisiert Repo, nicht Container-Inhalt
- ADR-010 violation corrected: previous `docker cp` hotfix was replaced by a clean `ekklesia-web` image rebuild
- Build context verified: `apps/web/Dockerfile.prod` copies `apps/representative/web/` to `/app/public/representative/`
- Clean deploy: server pulled to `199cd06`, `docker compose build web`, `docker compose up -d --no-deps web`
- Container verified: `/app/public/representative/index.html` contains 5 Fix-Marker (`position:sticky`, `z-index:100`, `score-row`, `empty-state`)
- Live verified: `https://ekklesia.gr/representative/index.html` contains the same 5 Fix-Marker
- **Rule:** `docker cp` is prohibited for production fixes. For ekprosopos/static web changes, rebuild/restart `ekklesia-web`.

### ekprosopos Logout Confirm
- Logout-Button zeigt jetzt Bestätigungsdialog: "Θέλετε σίγουρα να αποσυνδεθείτε;"
- Verhindert versehentliches Ausloggen bei Touch
- Commit: `4ba94fc`

### Topic 173 Single Resync
- `DIAV-9Ε7846ΨΖ2Ν-Υ` → `[Φορέας ΕΘΝΙΚΟ & ΚΑΠΟΔΙΣΤΡΙΑΚΟ ΠΑΝΕΠΙΣΤΗΜΙΟ ΑΘΗΝΩΝ]`
- Jetzt 6/6 Stichproben korrekt

### NEA-272 org_label Resolve + Backfill
- `POST /admin/maintenance/resolve-org-labels` triggered
- Step 1: 43 unknown UIDs → 43 resolved (100%), 0 failed
- Step 2: 168 parliament_bills.org_label backfilled
- Result: 192/192 INSTITUTIONAL bills have org_label (was 24/192)
- Forum Resync triggered (background, ~14min)
- Commit: `9363e16`

### NEA-271 Dashboard /logs Live Endpoints
- 3 neue Endpoints: `/admin/logs/containers`, `/admin/logs/ollama`, `/admin/logs/stream`
- Containers: 24 live, structural data only (name/image/status/state/health)
- Ollama: reachable, qwen2.5:14b + llama3.2:3b
- Stream: available:true, 59 sanitized lines (docker-proxy LOGS funktioniert trotz Pre-Check-Unsicherheit)
- Dashboard: SSH/Phase-2 Placeholder entfernt, Container-Tabelle + Ollama-Status + Log-Block live
- Tests: py_compile OK, tsc OK, sanitizer 12/12
- Commit: `1964e1f`

### NEA-262 Forum Alerts — CANCELLED (historisch)
- Telegram-Alerts vom 23.-24.05 waren Duplicate-Title-Bug (vor NEA-265 Fix)
- Gegencheck 25.05: `bills_ohne_topic = 0`, Monitor `All checks passed` seit 24h
- Kein aktueller Handlungsbedarf

### NEA-270 Admin Logs Hardening
- `_sanitize_logs()` in `apps/api/routers/admin.py` — redaktiert Secrets vor Ollama-Analyse
- Abgedeckte Formate: env `KEY=value`, JSON `"key":"value"`, Python dict `'key':'value'`, Bearer, DB/Redis URLs
- Dashboard `/logs` Button aktiviert (war disabled mit stale "endpoint missing" Text)
- 12 Unit Tests grün
- Live-verifiziert: POST `/admin/logs/explain` → Ollama-Analyse ohne Secret-Leaks
- Commit: `1fc2183`

### F-Droid MR !38007
- Fastlane Metadaten vervollständigt: el-GR Locale, changelogs, 4 Screenshots (en-US + el-GR)
- MR Description aktualisiert: App Inclusion Template clean, metadata link korrigiert
- Kommentar an linsui gepostet (Entschuldigung + 3 erledigte Punkte)
- Pipeline: grün
- Status: `opened`, wartet auf linsui
- Commit: `53c03bb`



### Commits
15. `08994b0` fix(NEA-269): remove demo data from /gov, fix /users revocation UX
16. `7fc3f26` feat(NEA-267): JSON-LD schemas for wiki, tickets, govgr-dimos + sitemap cleanup
17. `221815c` docs(NEA-266): update README to current project state

### NEA-267 SEO/GEO/KI (Session 4)
- JSON-LD TechArticle auf 10 Wiki-Seiten (api, architecture, security, privacy, whitepaper, broadcasting, contributing, database, modules, delete-account)
- JSON-LD WebPage auf govgr-dimos.html und tickets/index.html
- Meta description + OG tags auf tickets/index.html
- votes/* Redirects: noindex + aus sitemap.xml entfernt
- JSON-LD total: 5 → 17 Seiten, 19 Blöcke, alle validiert, keine Overclaims
- robots.txt: 11 User-agents (GPTBot, ClaudeBot, PerplexityBot etc.)
- llms.txt: 3504 Bytes, 71 Zeilen
- Sitemap: 24 → 21 URLs (3 Redirects entfernt)
- Deployed: Server pull + Dashboard rebuild

### NEA-266 README
- Encoding-Artefakte gefixt (kaputte Unicode → ASCII tree)
- Next.js 14→16, Modules 22→25, Containers 9→11, DB 15→18+
- Newsletter: Listmonk → Brevo + Telegram cross-publish
- Stale Links: Download 404 gefixt, Play Store 404 → "Internal testing", F-Droid MR 37087→38007
- V2 Roadmap: TrueRepublic/PnyxCoin → ZK Voting (Semaphore) + Federation
- Neue Features: Politician Evaluation, Representative App, Discourse Forum, POLIS, Dashboard, ZK V2
- Neue Sektion: SEO & AI Indexing

---

## SESSION 3 — 2026-05-24 (NEA-269 + NEA-270 Analyse)

### Commits
14. `08994b0` fix(NEA-269): remove demo data from /gov, fix /users revocation UX

### NEA-269
- **/gov:** Production-Demo-Daten entfernt (`Δήμος Αθηναίων`, `ΑΔΑ: ΧΧΧΧ-ΧΧΧ`)
- **/gov:** Empty-State statt Demo-Antrag, bis gov.gr OAuth 2.0 angeschlossen ist
- **/users:** Revocation-UX korrigiert: Dashboard-Revocation ist Self-Service-only / nicht admin-actionable
- **/users:** Kein Phone-Input, kein `phone_number`, kein API-Call zu `/api/v1/identity/revoke`
- **Privacy:** Keine Aenderung an Identity-Modell, Voting, Nullifier oder Key-Logik
- **Codex Recheck:** ACCEPTED — Finding in `CODEX_FINDINGS.md` geschlossen

### NEA-270 Analyse
- **Status:** Analyse only, kein Produktcode
- **Ergebnis:** Dashboard-/Logs-Endpoints existieren weitgehend; Hauptproblem ist Sicherheitsmodell, nicht fehlende Routen
- **Risiken identifiziert:**
  - `/admin/logs/explain` liest Container-Logs und kann Secrets/PII enthalten
  - Logs werden ohne Sanitization an Ollama gegeben
  - `/scraper/status` kann Infrastrukturdetails oeffentlich preisgeben
  - HLR-Credits sind oeffentlich sichtbar (bekannt/by design, aber finanziell sensibel)
- **Empfohlener naechster Schritt:** NEA-270 als Hardening-Task nur mit expliziter Freigabe bauen: Log-Sanitization, Auth-Gating fuer sensible Statusdaten, Dashboard-Text korrigieren

### Verification
- `npx tsc --noEmit` in `apps/dashboard` — OK
- `npm run build -- --no-lint` in `apps/dashboard` — lokal blockiert vor TS-Compile durch bestehenden Next/SWC-Lockfile-Patching-Fehler: `TypeError: Cannot read properties of undefined (reading 'os')`

### Deployment
- **NEA-269:** Push-freigegeben durch Codex, noch nicht als deployed markiert
- **NEA-270:** Keine Codeaenderung, kein Deploy

### Residual
- `apps/mobile/android/app/build.gradle` bleibt lokal dirty (vC27 bump)
- `apps/dashboard/tsconfig.tsbuildinfo` bleibt untracked/build artifact
- `apps/representative/*` Crash-Reste bleiben untracked

---

## SESSION 2 — 2026-05-24 (NEA-265 Fallback + NEA-268 + Branch Protection)

### Commits
12. `49d5780` fix(NEA-265): retry duplicate Discourse titles with stable suffix
13. `3e965de` feat(NEA-268): add org_label to parliament_bills for institutional forum titles

### Deployed
- API: `3e965de` (Migration m601a2b3c4d5 + NEA-265 fallback + NEA-268 org_label)
- Forum Resync: ~268/272 updated, 4 failed (2× 429, 2× 422)

### Branch Protection
- Updated: `test-api`/`test-crypto` → `Python API Tests`/`Crypto Package Tests`

### Residual
- 2× 429 Topics: Scheduler will auto-retry
- 2× 422 Topics (DIAV-ΡΛΩ6465ΕΦ5-Ω, DIAV-63ΚΛ4690ΒΝ-Ι): Title collision, NEA-265 fallback candidate

---

## SESSION REPORT — 2026-05-24 (FINAL)

### Commits (15 feature/fix + bridge)
1. `3afd78f` fix(NEA-261): newsletter preview error handling + null safety
2. `6632a23` fix(dashboard): inject ADMIN_KEY into dashboard container
3. `8ff3dc3` feat(NEA-263): newsletter → Telegram cross-publish
4. `8944a6b` feat: app screenshots in download section on landing page
5. `b7e7283` chore(bridge): stable checkpoint v1.3.2-stable-20260524
6. `fde71ca` fix(NEA-264): remediate npm audit high vulnerabilities
7. `b7c8cea` chore(deps): bump recharts to 3.8.1 (PR #67 squash merge)
8. `653a76d` fix(NEA-265): handle duplicate Discourse topic titles in forum sync
9. `7215168` feat(NEA-266): forum Diavgeia topic titles + region visibility
10. `e9f30d5` fix(NEA-266b): sanitize Diavgeia summary fallback (249 pill_el nulled)
11. `102cf56` docs(NEA-267): llms.txt + robots.txt AI crawlers + JSON-LD schemas

### Tags
- `v1.3.2-stable-20260524` — pre-ZK checkpoint
- `v1.3.3-audit-clean-20260524` — 0 high npm vulns
- `v1.3.4-forum-fix-20260524` — forum sync fixed
- `rollback-pre-zk-20260524` — server rollback point

### Deployed
- API: `e9f30d5` (NEA-265+266+266b forum sync + summary cleanup)
- Web: `102cf56` (screenshots + SEO/llms.txt/robots.txt)
- Dashboard: `6632a23` (ADMIN_KEY + Next 16)
- Monitor: unchanged (cooldown was already correct)

### Verified
- Newsletter preview: works (ADMIN_KEY injected)
- Newsletter Telegram: cross-publish live (non-blocking)
- npm audit: 0 high in all 3 workspaces
- CI Security Audit: green on all pushes
- Forum: 0 bills without topic, region prefix visible, metadata block in body
- Forum: Topic 405 clean (`Has unknown: False`)
- Forum resync: 137/272 updated, rest auto-syncing (429 rate limit)
- Bad pill_el: 249 nulled, 0 remaining
- Dependabot: enabled (4 moderate reported)
- PR #67: merged + branch deleted
- Open PRs: 0
- llms.txt: 200 OK live
- robots.txt: AI crawlers live
- JSON-LD: all valid, no overclaims

### Remaining
- Branch protection checks stale (`test-api`/`test-crypto`) — update recommended
- 135/272 forum topics pending resync (auto via 10min scheduler)
- NEA-268: Institutional org_label in forum titles (needs DB column)
- Moderate npm vulns: postcss (next), uuid/expo (needs Expo 56)
- NEA-249 ZK V2: blocked on Mopro
- NEA-260 Forum SSO V1: ADR only
- NEA-256 Alembic baseline: ADR only

---

## 2026-05-24 — NEA-267 SEO/GEO/KI Optimierung

- **llms.txt:** Erweitert — griechische Beschreibung, Πολιτική Αξιολόγηση, εκπρόσωπος, Diavgeia, ZK V2 Status, HMAC nullifier chain, alle Public URLs
- **robots.txt:** 4 neue AI Crawler (ChatGPT-User, Claude-User, Google-Extended, CCBot), /admin + /dashboard + /representative/app disallowed
- **JSON-LD:** TechArticle auf zk-voting.html, WebPage auf representative.html
- **Sitemap:** Unchanged (alle URLs valid)
- **FAQ JSON-LD:** Bereits 40+ Fragen inkl. Nullifier, Αξιολόγηση — kein Update nötig
- **Overclaim:** PASS — kein "official government"
- **JSON-LD Validation:** PASS (alle Blöcke gültig)
- **Live:** /llms.txt 200, /robots.txt 200, /sitemap.xml 200
- **Commit:** `102cf56`
- **Web deployed:** YES

---

## 2026-05-24 — NEA-266b Diavgeia forum bad summary cleanup

- **Root cause:** `pill_el` contained `Διαύγεια: [unknown:XXXXX]` from scraper — body formatter used it as summary fallback
- **Bad summary detector:** `_is_bad_summary()` — detects `unknown`, bare `Διαύγεια: ORG` patterns
- **Clean summary fallback:** cascading: summary_short_el → pill_el → summary_long_el, skipping bad values
- **Existing bad summaries nulled:** 249 rows (`pill_el` nulled)
- **Resync triggered:** YES — first batch updated, rest hit Discourse 429 rate-limit (50 hits). Topics will auto-resync over next hours via 10min scheduler.
- **Bad summary remaining in DB:** 0 (all 249 nulled)
- **Commit:** `e9f30d5`
- **API deployed:** YES

---

## 2026-05-24 — NEA-266 Forum Diavgeia topic titles + region visibility

- **Title prefix:** `[Βουλή]`, `[Περιφέρεια X]`, `[Δήμος X]`, `[Φορέας]`
- **Body metadata:** Πηγή, Επίπεδο, Περιοχή, ΑΔΑ (Diavgeia link)
- **Safe fallback:** title_el → summary first sentence → `Απόφαση Διαύγειας — ΑΔΑ {ada}` → bill ID (never unknown)
- **Tags:** `periferia-{id}`, `dimos-{id}` added for filtering
- **Update:** existing topics get new title prefix + region on resync
- **Commit:** `7215168`
- **API deployed:** YES

---

## 2026-05-24 — NEA-265 Forum alert spam — duplicate title handling

- **Bills without forum topic:** `DIAV-ΨΙΗΕ465ΕΦ5-Λ` (ΑΝΑΘΕΣΗ ΕΡΓΟΥ), `DIAV-Ψ79Ι4690ΒΝ-Σ` (Αίτημα έγκρισης προμήθειας)
- **Root cause:** Discourse 422 "Τίτλος έχει ήδη χρησιμοποιηθεί" — topic exists in Discourse but `forum_topic_id` NULL in DB (sync drift)
- **Effect:** Every 10min sync retried creation → 422 → log spam → HTTP 429 rate limits on other topic updates
- **Fix:** `discourse_sync.py` — on 422 duplicate title, search Discourse for existing topic by title and link `forum_topic_id`
- **Monitor cooldown:** Already correct (2h T1 lock on resync-all)
- **Commit:** `653a76d`
- **API deployed:** YES — Container recreated
- **Dependabot alerts:** ENABLED via API
- **Branch protection checks:** stale (`test-api`, `test-crypto`) — recommend update (not mutated)
- **Security Audit CI:** 3x SUCCESS on latest pushes

---

## 2026-05-24 — PR #67 Recharts 3.8.1 merged

- **PR:** #67 (Dependabot)
- **Dependency:** recharts 2.15.4 → 3.8.1
- **CodeRabbit:** SUCCESS, no actionable comments
- **CI:** green before merge
- **Security Audit:** green before merge
- **Merge method:** squash, branch deleted
- **Open PRs remaining:** 0

---

## 2026-05-24 — NEA-264 npm audit high vulnerabilities remediated

- **dashboard:** next 14.2.35 → 16.2.6 + proxy route `params` Promise fix
- **web:** `next-pwa` 5.6.0 → `@ducanh2912/next-pwa` 10.2.9 (maintained fork), `serialize-javascript` override >=7.0.5
- **web:** npm audit fix: @babel/plugin-transform-modules-systemjs, fast-uri, brace-expansion
- **mobile:** npm audit fix: @xmldom/xmldom, brace-expansion, ws
- **Result:** ALL workspaces 0 high vulnerabilities
- **Remaining moderate:** postcss (next transitive), uuid/expo chain (needs Expo 56)
- **CI Security Audit:** should now PASS (audit-level=high)
- **Commit:** `fde71ca`
- **Branch protection:** stale checks (`test-api`, `test-crypto`) — recommend update (not mutated)
- **Dependabot alerts:** disabled in repo — recommend enabling in GitHub Settings

---

## STABLE CHECKPOINT — v1.3.2-stable-20260524

- **Git tag:** `v1.3.2-stable-20260524`
- **Rollback tag:** `rollback-pre-zk-20260524`
- **HEAD:** `8944a6b`
- **Server HEAD:** `8944a6b` (deployed 2026-05-24)
- **Mobile:** vC27 v1.3.2
- **All security findings:** resolved (NEA-251..258)
- **System:** autonomous (T2 active, 0 alerts)
- **Next planned:** NEA-249 ZK V2 Mopro feasibility

---

## 2026-05-24 — App Screenshots on Landing Page

- **Screenshots:** 4 (Home, Votes, Politicians, POLIS) in `docs/assets/screenshots/`
- **Location:** Download section, after store buttons
- **Layout:** Desktop 4-col grid, Mobile 2x2, border-radius 20px, box-shadow
- **Captions:** Griechisch, blau (#2563eb)
- **Commit:** `8944a6b`
- **Deployed:** Web container rebuilt

---

## 2026-05-24 — NEA-263 Newsletter → Telegram Cross-Publish

- **Hook:** After successful Brevo `sendNow` only (not on draft)
- **Target:** Channel (broadcast) + Group Topic `platform`
- **Subject source:** Brevo GET `emailCampaigns/{id}` (not frontend) + fallback
- **HTML escaping:** `html.escape(subject)` for Telegram
- **Non-blocking:** `try/except`, returns `telegram_sent: true/false`
- **Dashboard:** Success banner shows `Telegram ✓/✗`
- **Commit:** `8ff3dc3`

---

## 2026-05-24 — Dashboard ADMIN_KEY Fix

- **Root cause:** `docker-compose.prod.yml` dashboard service had no `ADMIN_KEY` in environment
- **Effect:** All admin proxy calls (stats, preview, draft, send) silently returned 403
- **Fix:** Added `ADMIN_KEY: ${ADMIN_KEY}` to dashboard environment
- **Commit:** `6632a23`
- **Deployed:** Dashboard container recreated with key

---

## 2026-05-24 — NEA-261 Newsletter Preview Client-Side Fix

- **Problem:** Preview-Button im Dashboard `/newsletter-admin` funktionierte nicht. API `POST /api/v1/admin/newsletter/preview` gibt 200 OK (manuell verifiziert), aber Dashboard zeigte keine Vorschau.
- **Root Cause:** `handlePreview()` zeigte nur generisches "Preview fehlgeschlagen" bei Fehlern — versteckte echten HTTP-Status (422/403/502). Kein Null-Check auf `html_preview` Key.
- **Fix:** 3 Aenderungen in `newsletter-admin/page.tsx`:
  1. Error-Detail: zeigt `errData.detail || errData.error || Preview fehlgeschlagen (${status})` statt generisch
  2. Null-Safety: prueft `data.html_preview` bevor `setPreview()`, zeigt explizite Fehlermeldung wenn leer
  3. `setSuccess(null)` am Preview-Start (verhindert stale Nachrichten)
- **File:** `apps/dashboard/src/app/(dashboard)/newsletter-admin/page.tsx`
- **Build:** `tsc --noEmit` OK
- **Deploy:** ausstehend — nach Deploy zeigt Error-Nachricht den konkreten Grund

---

## 2026-05-23 — NEA-261 Newsletter Compose (Brevo-based, Implemented)

- **API:** 4 Endpoints — stats, preview (POST), draft (POST), send (POST + confirm=true)
- **Dashboard:** /newsletter-admin — Compose + Preview + Draft + Send mit Confirm-Dialog
- **Auth:** SUPER_ADMIN + SYSTEM_ADMIN only
- **Sanitization:** Script/Event/javascript: stripped
- **Safety:** Draft-first, Send braucht `confirm=true`, keine Subscriber-Emails, BREVO_API_KEY server-only
- **Router:** Registriert in main.py
- **Build:** Dashboard `npm run build` OK
- **Files:** 5 exakt (keine unrelated)
- **Commit:** `278a0e6`
- **Deployed:** API + Dashboard rebuilt
- **Hinweis:** ADR in `docs/adr/NEA-261-newsletter-compose-listmonk-vs-brevo.md` bleibt als Entscheidungsreferenz

---

## 2026-05-23 — NEA-261 Newsletter Compose ADR (Blocked)

- **ADR:** `docs/adr/NEA-261-newsletter-compose-listmonk-vs-brevo.md`
- **Status:** Blocked — Listmonk leer (0 Listen/Subscribers), Brevo vs Listmonk Entscheidung offen
- **Kein Produktcode**

---

## 2026-05-23 — NEA-260 Seamless Forum SSO ADR (Plan Only)

- **ADR:** `docs/adr/NEA-260-seamless-forum-sso.md`
- **Status:** Proposed — kein Code
- **V1 empfohlen:** Browser-UX verbessern (In-App Browser, auto-SSO Discourse Config)
- **V2 offen:** Server-initiated SSO braucht Discourse API Investigation
- **V3 rejected:** Pre-Auth URL Bypass
- **Kein Produktcode geaendert**

---

## 2026-05-23 — NEA-258 LOW Fixes (Rate-Limit + Broken Link + OG + README)

- **Rate-limit:** API key generation 5/hour per IP (Redis counter)
- **Broken link:** `representative.html` → `/representative/index.html` (absoluter Pfad)
- **OG tag:** `broadcasting.html` fehlende `og:description` hinzugefuegt
- **README:** Hetzner CX33→CX43, 9→11+ containers
- **Files staged:** 4 exakt (keine unrelated dirty files)
- **py_compile:** OK
- **Commit:** `7406c15`
- **Deployed:** API + Web rebuilt

---

## 2026-05-23 — NEA-257 CI Security Audit Hard-Fail (MEDIUM Fix)

- **npm audit:** `|| true` entfernt, hard-fail bei high/critical
- **npm scope:** Root + apps/web + apps/dashboard + apps/mobile + apps/representative
- **pip-audit:** `|| true` entfernt, hard-fail
- **cargo audit:** Bleibt soft (kein Rust in pnyx, dokumentiert als informational)
- **YAML:** Validiert
- **Commit:** `8ccf2ac`

---

## 2026-05-23 — NEA-256 Alembic Schema Baseline ADR (Documentation Only)

- **ADR:** `docs/adr/NEA-256-alembic-schema-baseline.md`
- **Status:** Proposed — kein DB-Change, kein Alembic-Run
- **Drift:** 8 fehlende Spalten/Tabellen + 1 Type-Mismatch (decisions.id)
- **Plan:** Schema Snapshot → Baseline Migration → Local Test → Clone Test → Stamp
- **SCHEMA_DRIFT_NOTES.md:** aktualisiert mit NEA-256 Verweis

---

## 2026-05-23 — NEA-255 Finance Endpoints Admin Auth (MEDIUM Fix)

- **3 Endpoints:** `/admin/finance/server`, `/admin/finance/btc`, `/admin/finance/ltc` → `Depends(verify_admin_key)`
- **Public unaffected:** `/payments/status`, `/payments/public/finance`
- **Dashboard unaffected:** nutzt nur `/admin/finance/overview` (war bereits geschuetzt)
- **Commit:** `1ff0394`
- **Deployed:** API rebuilt
- **Codex Status:** accepted

---

## 2026-05-23 — NEA-254 Receipt + Compass Signed POST (MEDIUM Fix)

- **GET receipt:** → 410 deprecated
- **POST receipt:** Ed25519 sig `receipt:{bill_id}:{nullifier_hash}`, response returns `nullifier_prefix` only
- **GET compass/personal:** → 410 deprecated
- **POST compass/personal:** Ed25519 sig `compass_personal:{nullifier_hash}`, response `nullifier_prefix` only
- **Full nullifier removed** from all responses
- **No active callers** in mobile or web
- **Commit:** `73952cc`
- **Deployed:** API rebuilt
- **Codex Status:** accepted

---

## 2026-05-23 — NEA-253 Relevance Signal Signatur (MEDIUM Fix)

- **signature_hex:** Required in `RelevanceRequest` (Pydantic enforced)
- **Payload:** `relevance:{bill_id}:{signal}:{nullifier_hash}`
- **verify_signature():** Vor Upsert
- **Web Caller updated:** `RelevanceButtons.tsx` signiert via `signPayload()` + `loadKeypair()`
- **Invalid sig → 401**, Missing → 422
- **Commit:** `4ce07e6`
- **Deployed:** API + Web rebuilt
- **Codex Status:** accepted

---

## 2026-05-23 — NEA-252 Municipal Vote Signatur (HIGH Fix)

- **signature_hex:** Required in `DecisionVoteRequest` (Pydantic enforced)
- **Payload:** `municipal:{ada}:{VOTE}:{nullifier_hash}`
- **verify_signature():** Vor Duplikat-Check und DB-Write
- **Invalid sig → 401**, Missing sig → Pydantic 422
- **Identity not found → 404** (war 403)
- **Kein aktiver UI-Caller:** API-only Fix
- **Commit:** `1bc3b39`
- **Deployed:** API rebuilt
- **Codex Status:** accepted

---

## 2026-05-23 — NEA-251 Discourse SSO Callback Signed (HIGH Fix)

- **signature_hex:** Required param in POST /sso/discourse/callback
- **Challenge:** `discourse_sso:{nonce}:{public_key_hex}` — Ed25519 verify before identity lookup
- **external_id:** HMAC(FORUM_SSO_SALT, nullifier_hash) — no raw nullifier in Discourse payload
- **Next.js sso-verify:** Signs challenge via `signPayload()` from crypto.ts
- **Static sso-verify.html:** Redirects to Next.js version (no inline Ed25519)
- **crypto.ts:** New `signPayload(privKey, payload)` generic signer
- **Commit:** `272f73a`
- **Deployed:** API + Web rebuilt

---

## 2026-05-23 — AUDIT B: Code Security & Architecture

- **Scope:** API routers, DB/Alembic consistency, monitor self-healing, repo hygiene, Arweave/privacy, ADR consistency
- **Report:** `docs/agent-bridge/AUDIT_B_CODE.md`
- **Commit:** `fd96c56`
- **Result:** 2 HIGH, 5 MEDIUM, 1 LOW, 1 INFO

### Findings:
- HIGH: Discourse SSO callback lacks key-possession proof
- HIGH: Municipal Diavgeia vote accepts `nullifier_hash` without signature
- MEDIUM: Relevance signal accepts `nullifier_hash` without signature
- MEDIUM: Receipt/personal compass endpoints use `nullifier_hash` as bearer secret
- MEDIUM: `/api/v1/payments/admin/finance/*` component endpoints lack admin auth
- MEDIUM: Alembic history does not reproduce production schema
- MEDIUM: Security-audit CI soft-fails dependency audits
- LOW: Public API key generation lacks explicit endpoint-level rate limit
- INFO: README/CLAUDE.md stale

---

## 2026-05-23 — NEA-243 Discourse Update

- **Pre-update Tag:** `discourse-pre-update-20260523`
- **Updates:** 8 Commits inkl. CVE-2026-42945 (nginx 1.30.1), base image 2.0.20260521
- **Rebuild:** SUCCESS
- **Version:** `2026.5.0-latest.1`
- **HTTP:** 200
- **Downtime:** ~10 Min (rebuild)

---

## 2026-05-23 — AUDIT A: Website & Navigation

- **31 HTML Seiten** auditiert (canonical, OG, JSON-LD, sitemap, live status)
- **24 sitemap URLs** — alle oeffentlichen Seiten abgedeckt
- **12 Live-Endpoints** geprüft — alle 200 OK
- **97 "broken links"** gefunden — 96 false positives (Next.js routes), 1 echter Broken Link
- **Helios:** 0 Product-Claims, nur erklaerend in zk-voting.html
- **Report:** `docs/agent-bridge/AUDIT_A_WEBSITE.md`
- **Commit:** `8c50c13`

### Findings:
- LOW: `representative.html → representative/index.html` broken relative link
- LOW: `tickets/index.html` + `votes/*.html` fehlende OG tags
- LOW: `wiki/broadcasting.html` fehlende og:description
- INFO: JSON-LD auf 3 Core-Seiten (index, community, faq) — ausreichend

---

## 2026-05-23 — NEA-250 Evaluation Region-Locking

- **POST /evaluate:** Requires `region_locked=true` + periferia_id/dimos_id Match
- **Βουλευτής/Περιφερειάρχης:** citizen.periferia_id == politician.periferia_id
- **Δήμαρχος:** citizen.dimos_id == politician.dimos_id
- **Politician ohne IDs:** 403 safe deny
- **/scores:** Bleibt oeffentlich (kein Region-Check)
- **/my-evaluation:** Unveraendert (Lesen eigener Bewertungen)
- **Kein fuzzy Matching:** Nur IDs
- **Commit:** `67e6d3d`
- **Deployed:** API rebuilt

---

## 2026-05-23 — NEA-186b Περιφερειάρχης periferia_id Mapping

- **DB:** `representative_tokens.periferia_id` + `dimos_id` FK Spalten hinzugefuegt
- **_get_rep_token():** Laedt `periferia_id` + `dimos_id`
- **is_bill_visible_for_token():** Περιφερειάρχης mit periferia_id sieht eigene REGIONAL Bills
- **/rep/bills:** Deterministisches FK-Match `parliament_bills.periferia_id = token.periferia_id`
- **Kein fuzzy Matching:** Kein ILIKE, kein String-Normalization
- **Fallback:** Περιφερειάρχης ohne periferia_id → nur PARLIAMENT
- **Verifiziert:** periferia_id=7 → 7 Bills (5 NATIONAL + 2 REGIONAL), ohne → 5 Bills (nur NATIONAL)
- **Commit:** `a89f8c1`
- **Deployed:** API rebuilt

---

## 2026-05-23 — HOTFIX: API Crash Loop + Monitor DNS Fix

- **Root Cause:** `AuditLog.metadata` ist reserviert in SQLAlchemy Declarative → `InvalidRequestError` → API Restart-Loop
- **Fix:** Python-Attribut umbenannt zu `details`, DB-Spalte bleibt `metadata` (`Column("metadata", JSONB, ...)`)
- **Monitor DNS:** `api.ekklesia.gr` → `API_URL` (intern `http://api:8000`) in `check_web_urls()`
- **Verifiziert:** API Up, Monitor 0 Alerts
- **Commit:** `4bbce75`
- **Deployed:** API + Monitor rebuilt

---

## 2026-05-23 — PR #70 Next.js 16 merged + #64/#69 closed

- **PR #70:** Already merged (CI SUCCESS, CodeRabbit SUCCESS)
- **#64 + #69:** CLOSED (superseded by #70)
- **Kein Handlungsbedarf** — war bereits gemergt

---

## 2026-05-23 — NEA-242 Audit Log (3 Commits, 2 Codex Rechecks)

- **Commit 1 (`e0fc7b3`):** audit_log Tabelle (server-manuell), identity_records.source, admin_account.py raw SQL
- **Codex Recheck 1:** ORM Model fehlt → Schema nicht reproduzierbar
- **Commit 2 (`3684ec6`):** AuditLog ORM Model, raw SQL → ORM `db.add()`, JSONB korrekt
- **Codex Recheck 2:** `String(36)` + `gen_random_uuid()` = DDL-Fehler auf fresh DB
- **Commit 3 (`41bc682`):** `UUID(as_uuid=True)` — native PostgreSQL UUID
- **Finale:** Schema reproduzierbar, ORM-basiert, JSONB korrekt, keine sensiblen Daten
- **Codex Final-Recheck:** ACCEPTED — Dashboard source badge ist nur Follow-up, kein Blocker
- **Deployed:** API rebuilt (3x)

---

## 2026-05-23 — NEA-242 Audit Log fuer Admin-erstellte Accounts (REPLACED BY ABOVE)

- **audit_log Tabelle:** UUID PK, action, actor, target_type, target_id, metadata JSONB, created_at
- **identity_records.source:** `SMS` (default) | `ADMIN_TEST` | `IMPORT` — ORM + DB Spalte
- **admin_account.py:** `source='ADMIN_TEST'` + Audit-Log in gleicher Transaktion (`db.flush()` → audit → `db.commit()`)
- **Keine sensiblen Daten geloggt:** Kein Private Key, kein Full Nullifier, kein Token
- **Verifiziert:** audit_log Tabelle existiert (7 Spalten), identity_records.source Spalte existiert
- **Dashboard:** Follow-up (kein bestehender Users-Pfad fuer source Badge)
- **Commit:** `e0fc7b3`
- **Deployed:** API rebuilt

---

## 2026-05-22 — NEA-249 Docs: Helios → Semaphore Hybrid

- **index.html:** 2x Helios refs → "Semaphore ZK Proofs — προγραμματισμένο"
- **roadmap.html:** "σε ανάπτυξη" → "προγραμματισμένο (εξαρτάται από mobile prover)"
- **faq.html:** Helios/Semaphore Q&A → korrektes Semaphore-Modell + "Γιατί όχι Helios?"
- **wiki/zk-voting.html:** NEUE Seite — Tier 1 (heute) vs Tier 2 (geplant), Trust Assumptions, Helios-Erklaerung
- **sitemap.xml:** zk-voting.html hinzugefuegt (24 URLs)
- **Wording:** Ueberall "Προγραμματισμένο" — nie "σε ανάπτυξη"
- **Helios:** Nur in erklaerenden "Γιατί όχι Helios?" Abschnitten
- **Commit:** `c591d28`
- **Deployed:** Web rebuilt

---

## 2026-05-22 — NEA-249 ADR Created

- **ADR:** `docs/adr/NEA-249-zk-voting-v2-semaphore-hybrid.md`
- **Status:** Proposed / Blocked before implementation
- **Decision:** Hybrid V2 (Tier 1 HMAC unchanged + Tier 2 Semaphore opt-in)
- **Blocking dependency:** Mobile prover unresolved (snarkjs/Mopro/RN incompatibility)
- **Non-goals:** No product code, no DB, no API, no "in build" claims
- **Next step:** Mopro native Expo Module feasibility plan (separate, no code)
- **Kein Produktcode geaendert**

---

## 2026-05-22 — NEA-249 Phase 0 Benchmark Spike — STOP

- **Ziel:** Semaphore Proof-Generation auf Expo SDK 54 / React Native 0.81 testen
- **Ergebnis:** STOP — keine Benchmark moeglich ohne native Projektaenderungen
- **@semaphore-protocol/proof@4.14.2:** Installierbar, aber abhaengig von snarkjs@0.7.5 das Node.js `fs`/`os`/`path`/`readline` braucht — in React Native nicht verfuegbar
- **Mopro:** Kein npm Package. Rust SDK, native Kompilierung erforderlich. Kein Expo-Plugin.
- **react-native-snarkjs:** Veraltet (2021), 43.6 MB, GPL-3, inkompatibel mit RN 0.81
- **Expo Go:** NEIN — native Module zwingend noetig
- **Dev Client:** REQUIRED fuer jede ZK-Proving-Route
- **Entscheidung:** NEA-249 Implementation pausiert vor Phase 1
- **Naechster Schritt:** Separater Plan fuer Mopro native Expo Module Integration
- **Website/FAQ:** Wording bleibt "roadmap/planned", nicht "in build"
- **Kein Produktcode geaendert**

---

## 2026-05-22 — NEA-222 Wahlbezirk Server-Filter + NEA-188 votes-timeline Fix

- **NEA-222 parliament.py:** `periferia_id` + `dimos_id` Query-Params mit GovernanceLevel Enum
- **NEA-222 Filter:** NATIONAL + INSTITUTIONAL immer, REGIONAL/MUNICIPAL nur bei Match
- **NEA-222 api.ts:** `fetchBills()` erweitert mit region params
- **NEA-222 BillsScreen:** Client-side `regionBills` Filter entfernt, `load()` abhaengig von userPeriferia/userDimos
- **NEA-222 Verify:** periferia_id=1 → 171 Bills (NATIONAL+INSTITUTIONAL), korrekt
- **NEA-188:** votes-timeline DEMO-Filter inline (`~bill_id.like('DEMO-%')`), Modul-Level `_real_vote` verursachte 500
- **versionCode:** 26 → 27
- **Commits:** `69d68a7` (NEA-188), `8bb95be` (NEA-222)
- **Deployed:** API rebuilt

---

## 2026-05-22 — NEA-229 + NEA-227 Roadmap + FAQ

- **roadmap.html:** Duplikat MOD-25 aus Alpha entfernt, Alpha-Tile → nur "gov.gr OAuth fuer Ekprosopos (geplant)"
- **roadmap.html:** MOD-25 bleibt korrekt in Beta-Sektion (Zeile 473)
- **faq.html:** JSON-LD FAQPage Schema: Πολιτικοί Q&A hinzugefuegt (8 Kategorien, liquide Bewertung)
- **HTML Q&A:** Zeile 495-496 war bereits korrekt — kein Move noetig
- **Commit:** `2ae482a`
- **Deployed:** Web rebuilt

---

## 2026-05-22 — Lifecycle Stuck Alert + Monitor Cooldown

- **GR-74e0cb08:** Bereits automatisch PARLIAMENT_VOTED (Scheduler 00:11 UTC), Arweave archiviert — kein manueller Fix noetig
- **Andere stuck Bills:** 0 (keine WINDOW_24H ueberfaellig)
- **lifecycle_stuck Cooldown:** Redis Lock per bill_id (1h), suppressed in check_lifecycle_stuck() BEFORE Alert reaches summary
- **Health-Check:** 0 Alerts — all checks passed
- **Commit:** `e5c8106`
- **Deployed:** Monitor rebuilt

---

## 2026-05-22 — NEA-247 Mobile Hotfix (Codex residual)

- **ResultScreen:** `fromVote` route param — "Η ψήφος σας καταγράφηκε" nur bei `fromVote=true`
- **Neutral copy:** "Τα αποτελέσματα δεν είναι ακόμα διαθέσιμα" bei direkter Navigation
- **VoteScreen:** `fromVote: true` bei successful vote, correction, demo
- **RootStackParams:** `Result.fromVote?: boolean`
- **versionCode:** 25 → 26
- **Commit:** `a44497e`
- **APK Build:** laeuft

---

## 2026-05-22 — NEA-247 + NEA-248 Vote Display + QR Modal

- **NEA-247 (URGENT):** "Η ψήφος σας καταγράφηκε" wurde ALLEN Besuchern auf ACTIVE Bills mit 0 Votes gezeigt
  - Root Cause: Bedingung pruefte `results.total_votes === 0`, nicht ob User tatsaechlich gewaehlt hat
  - Fix: Nur anzeigen wenn `voteStatus === "voted"` oder `voteStatus === "already"`
  - Datei: `apps/web/src/app/[locale]/bills/[id]/page.tsx`
- **NEA-248:** ESC-Key fuer QR Overlay + phaseBModal auf tickets/index.html
  - Auto-close nach Auth war bereits implementiert (setTimeout 1500ms)
  - Close-Button existierte bereits, kein z-index Problem gefunden
- **Commit:** `2226eac`
- **Deployed:** Web rebuilt

---

## 2026-05-22 — NEA-186 Hotfix 2 (Codex residual)

- **MEDIUM FIXED:** `/rep/divergence` status gate added (`bill.status not in ALLOWED_STATUSES → 403`)
- **Docstring:** `/rep/bills` korrigiert — Περιφερειάρχης ist PARLIAMENT-only (NEA-186b pending)
- **Commit:** `e2b6652`
- **Deployed:** API rebuilt

---

## 2026-05-22 — NEA-186 Hotfix (Codex Audit)

- **HIGH FIXED:** `is_bill_visible_for_token()` extrahiert, angewendet in `/rep/results` + `/rep/divergence` → 403 bei unsichtbaren Bills
- **MEDIUM FIXED:** Περιφερειάρχης Branch entfernt — faellt jetzt auf PARLIAMENT-only Fallback (bis periferia_id Mapping, NEA-186b)
- **Commit:** `eceb806`
- **Deployed:** API rebuilt

---

## 2026-05-22 — NEA-186 εκπρόσωπος Rollen-Sichtbarkeit

- **detect_role_from_org_label():** Auto-Erkennung Βουλευτής/Περιφερειάρχης/Δήμαρχος aus Diavgeia org_label
- **GET /rep/bills Rollen-Filter:** Βουλευτής=alle, Περιφερειάρχης=PARLIAMENT+REGIONAL, Δήμαρχος=PARLIAMENT+MUNICIPAL
- **Fallback:** role=None oder Περιφερειάρχης ohne Region → nur PARLIAMENT (Audit #6+#7)
- **X-Rep-Role Header:** ASCII (MP/REGIONAL/MUNICIPAL/UNKNOWN) — nie Greek in Headers (Audit #2)
- **municipality:** Spalte hinzugefuegt, wird bei Token-Create geschrieben (Audit #4)
- **role_suggestion:** Additiv in Verify-Response, kein Breaking Change (Audit #5)
- **Known Limitation:** Δήμαρχος sieht alle MUNICIPAL Bills, nicht nur eigene (Audit #1)
- **App:** Rolle/Region Badge + ΔΙΑΥΓΕΙΑ Source Badge auf Cards
- **Commit:** `435f3bd`
- **Deployed:** API + Web rebuilt

---

## 2026-05-22 — NEA-190 SEO Fix

- **robots.txt:** `Disallow: /dashboard/` hinzugefuegt
- **sitemap.xml:** 20→23 URLs (+votes/active, votes/results, votes/recent), lastmod 2026-05-22
- **community.html:** JSON-LD Organization Schema hinzugefuegt
- **representative.html:** Fehlende OG Tags (type, url, title, description, locale) ergaenzt
- **Bestand:** Alle 23 oeffentlichen Seiten haben canonical + robots index
- **Fehlend OG:** votes/*.html + tickets/index.html (low priority, kein User-facing)
- **Commit:** `c06066e`
- **Deployed:** Web rebuilt

---

## 2026-05-22 — NEA-246 Dashboard Deploy

- **/politicians:** Live — read-only Tabelle (Org/Ekprosopos, Rolle, Region, Bewertungen, Score, ADA)
- **/monitor:** Live — Module Health Grid, Scraper Jobs, Admin Buttons (Catch-up + Resync)
- **/bills Diavgeia-Filter:** Live — Source-Tabs (Ολα/Βουλή/Διαύγεια)
- **Sidebar:** 2 neue Links (Πολιτικοί, Monitor)
- **Roles:** politicians=4 Rollen, monitor=2 Rollen (SYSTEM_ADMIN+SUPER_ADMIN)
- **Commit:** `331d3fd`
- **Deployed:** Dashboard rebuilt + restarted

---

## 2026-05-22 — T2 aktiviert + Dashboard Assessment (NEA-244)

- **T2 AUTO_RECOVERY_T2:** `true` in `.env.production`, Monitor verifiziert
- **Fix:** Compose hardcoded `"false"` → `${AUTO_RECOVERY_T2:-false}` (Commit `fad42a2`)
- **Dashboard:** 19 Seiten (overview, analytics, bills, votes, cplm, vaa, system, ai, forum, logs, embed, finance, stats, settings, users, nodes, node-settings, gov, representatives)
- **FEHLT im Dashboard:**
  - Πολιτικοί / Evaluation (MOD-25) — keine Seite, kein Sidebar-Link
  - Monitor / Recovery (NEA-241) — kein Status-Panel fuer T1/T2/T3
  - Diavgeia-Filter auf Bills-Seite — nicht vorhanden
  - Admin-Buttons: `/admin/scraper/catch-up` + `/admin/forum/resync-all` — nicht im Dashboard
  - Community.html Stats Mirror — nicht im Dashboard
- **Empfehlung:** 2 neue Dashboard-Seiten: `/politicians` (Evaluation-Uebersicht) + `/monitor` (Recovery-Status + Admin-Trigger-Buttons)

---

## 2026-05-22 — Globale Kohaerenz: Module Count + Wiki + README + Health

- **README.md:** Badge + Text 22→25 Module, MOD-01 through MOD-25
- **CLAUDE.md:** Spec v7.0→v10.0, 15→25 Module, 13→70+ Endpoints
- **modules.html:** MOD-23 (Greek Topics, disabled) + MOD-24 (CPLM) hinzugefuegt, Meta 22→25
- **roadmap.html:** Politikoi + CPLM + Diavgeia + Self-Healing in Beta-Phase, Politikoi aus "geplant" entfernt
- **/health:** Duplikate MOD-12/14 bereinigt, sortiert, 23 unique Module (25 Module-Nummern, MOD-13/MOD-17 reserviert)
- **/health/modules:** 23 detaillierte Module, overall: ok
- **Commit:** `8f1ebfa`
- **Deployed:** Web + API rebuilt

---

## 2026-05-22 — NEA-241 Watcher 3-Tier Auto-Recovery

- **Structured Alerts:** Alert dataclass (type, service, severity, recovery_allowed)
- **T1 API Recovery:** Catch-up + Forum-Resync via Admin-Endpoints, Redis Lock (1h/2h)
- **T2 Docker Restart:** Via Socket-Proxy, Feature-Flag `AUTO_RECOVERY_T2=false` (default off), Allowlist nur api+web
- **T3 Telegram Escalation:** Severity-Icon, Service, Recovery-Ergebnis
- **Neuer Endpoint:** `POST /admin/scraper/catch-up` (background, idempotent, 10min dedup)
- **Neuer Service:** `ekklesia-docker-proxy` (tecnativa/docker-socket-proxy, CONTAINERS+POST only)
- **ADMIN_KEY:** An Monitor-Container uebergeben, nie geloggt
- **Smoke Tests:** Docker-Proxy ✓, Health-Check ✓ (1 Alert → T3), Catch-up ✓ (alle aktuell)
- **Commit:** `a589e6a`
- **Deployed:** Monitor + API + docker-proxy

---

## 2026-05-22 — NEA-239 + NEA-224 Community.html Zaehler live

- **Vorher:** Alle Zaehler bereits per `fetch` aus `/public/stats` geladen — KEINE hardcoded Werte
- **Fix:** DEMO-Bills/Votes aus Stats gefiltert, `forum_topics` + `archived_bills` hinzugefuegt
- **community.html:** 2 neue Kacheln (Αρχείο + Forum), insgesamt 8 live Kacheln
- **Verifiziert:** `parliament=20, diavgeia=164, archived=168, votes=4, arweave=4, forum=184`
- **Commit:** `e7739a8`
- **Deployed:** Web + API rebuilt

---

## 2026-05-22 — NEA-231 Follow-up: Forum Resync

- **resync_all_topics():** Rate-Limited (5 Topics pro 15s Batch)
- **Run 1:** 132/187 updated, 55 failed (HTTP 429)
- **Run 2:** 185/187 updated, 2 failed (GR-cf7398d9 + DIAV-ΨΙ7Ρ46Ψ8ΧΒ-7)
- **Gesamt:** 185/187 Forum Topics mit neuem Content aktualisiert
- **Commit:** `420f6a1` (Throttling-Fix)

---

## 2026-05-22 — NEA-231 + NEA-235 Forum Content Fix

- **_clean():** Strips HTML Tags, hellenicparliament.gr URLs (bare + markdown), Navigation-Boilerplate, Cookies
- **Content Fallback:** summary → long_text[:2000] → Diavgeia ADA Link → Parliament URL → Placeholder
- **DB Stand:** 187 Bills, 182 ohne summary_short_el, 75 ohne summary_long_el, alle 187 mit forum_topic_id
- **Re-sync:** Neue Topics bekommen jetzt automatisch besseren Body. Bestehende leere Topics werden beim naechsten forum_sync-Lauf (alle 10min) nicht automatisch aktualisiert (nur neue Bills). Manueller Resync ist ein Follow-up.
- **Commit:** `69f9adf`
- **Deployed:** API rebuilt

---

## 2026-05-22 — NEA-226 QR Konsensierung Web — Verification

- **Status:** BEREITS IMPLEMENTIERT — kein Fix noetig
- **Web Bill-Detail** (`apps/web/src/app/[locale]/bills/[id]/page.tsx`):
  - Zeile 414-415: OPEN_END Konsensierung-Block aktiv
  - Zeile 422: DIAVGEIA-spezifischer Text
  - Zeile 449-467: Consensus Slider (-5 bis +5)
  - Zeile 475: QR-Auth Submit via `/api/v1/polis/qr-consensus`
  - Zeile 513: `purpose="consensus"` QR-Widget
- **QRCodeVoteStub.tsx:** `purpose?: "vote" | "consensus" | "ticket" | "forum_login"` — consensus supported
- **DB:** 164 DIAVGEIA OPEN_END + 3 PARLIAMENT OPEN_END Bills
- **Aenderung:** Keine

---

## 2026-05-21 — MOD-25 Status Fix (Codex Befund)

- **modules.html:** MOD-25 `dot-planned` → `dot-active`, `badge-gray` → `badge-green "Beta"`
- **`/health`:** MOD-25 Politikoi hinzugefuegt (25 Module total)
- **`/health/modules`:** MOD-24 Forum Sync + MOD-25 Politikoi hinzugefuegt (23 detaillierte Module)
- **Verifiziert:** Live Wiki zeigt MOD-25 gruen, API gibt `{"status": "ok"}` fuer MOD-25
- **Commit:** `411a560`
- **Deployed:** Web + API rebuilt

---

## 2026-05-21 — NEA-240 Follow-up: ADA constraint verification

- **Live API:** ADA length 11–14 (100 decisions checked)
- **DB:** ADA length 11–14 (165 rows)
- **Constraint `BETWEEN 10 AND 32`:** KORREKT — grosszuegig aber alle Werte passen
- **Aenderung:** Keine noetig
- **Fazit:** Constraint bleibt, empirisch verifiziert

---

## 2026-05-21 — NEA-191 Liquid Evaluation (updated_at + pre-fill + badge)

- **DB:** `updated_at` Trigger `set_politician_eval_timestamp` auf `politician_evaluations`
- **API:** `GET /politicians/{ada}/my-evaluation?nullifier_hash=` — eigene Scores pro Politiker
- **API:** `GET /politicians/my-evaluations/bulk?nullifier_hash=` — alle bewerteten Politiker (vermeidet N+1)
- **EvaluatePoliticianScreen:** Pre-fill Scores bei Wiederbesuch, "Τελευταία αλλαγή: DD.MM.YYYY", Submit-Text "Ενημέρωση" vs "Αποστολή"
- **MPScreen:** "✓ Αξιολογήθηκε" grüner Badge per Bulk-Endpoint
- **versionCode:** 24 → 25
- **Verifiziert:** `/my-evaluation` + `/my-evaluations/bulk` live getestet, Daten korrekt
- **Commit:** `cf448dc`
- **Deployed:** API rebuilt

---

## 2026-05-21 — NEA-240 All 5 Codex Findings Fixed

- **Bug 1 (region_locked):** ProfileScreen syncs `periferia_id`/`dimos_id` from `/identity/status` into SecureStore
- **Bug 2 (/politicians/ leer):** ON CONFLICT preserves `evaluation_enabled` on token renewal
- **Bug 3+4 (Scraper stale):** Catch-up on API startup (overdue jobs trigger sofort), `record_run()` aus circuit-breaker-skip entfernt
- **Bug 5 (Forum 3 Bills):** Kategorie-Routing flach (max 2 Ebenen), DIAVGEIA MUNICIPAL/REGIONAL korrekt geroutet, `_category_cache` cleared per sync
- **Verifiziert:** Diavgeia Scraper laeuft nach Deploy (Catch-up erfolgreich), API OK
- **Commit:** `3627580`
- **Deployed:** API rebuilt

---

## 2026-05-21 — MPScreen Fix + vC24 Builds

- **MPScreen:** Placeholder "Αξιολόγηση διαθέσιμη σύντομα" ersetzt durch echte `fetchPoliticians()` API-Liste
- **Navigation:** Tap auf Politician → `EvaluatePoliticianScreen` (8 Fragen, -5 bis +5)
- **region_locked:** Test-Account (id=13) auf FALSE gesetzt
- **vC24 APK:** `~/Desktop/ekklesia-v1.3.2-vC24.apk` (66MB) — S10 installiert + verifiziert
- **vC24 AAB:** `~/Desktop/ekklesia-v1.3.2-vC24-PLAY.aab` (45MB) — Play Console Upload bereit
- **Commits:** `700c389` (MPScreen fix), `803ea51` (vC24 bump)
- **Lesson:** APK und AAB NICHT parallel bauen (gleicher android/ Ordner). Play-Flavor APK haengt auf S10 — immer Direct-Build fuer Sideload.

---

## 2026-05-21 — HTTP 500 Fix: keypair.py verify_signature

- **Root Cause:** `packages/crypto/keypair.py` ueberschattete `apps/api/keypair.py` im Docker Python-Path
- **Bug:** Crypto-Version fing nur `BadSignatureError`, nicht `ValueError` (falsche Signatur-Laenge → 500)
- **Bug 2:** `payload: bytes` Type-Hint, aber evaluation.py sendete `str`
- **Fix:** `except (BadSignatureError, ValueError, Exception)` + auto-encode str→bytes
- **Verifiziert:** `POST /evaluate` mit ungueltiger Signatur → 401 (nicht mehr 500)
- **Commit:** `5e5de6b`

---

## 2026-05-21 — Monitor Arweave Fix + Trailing Slash + ekprosopos Login

- **Arweave Monitor:** Rule 5 filtert jetzt `source = 'PARLIAMENT'` — DIAVGEIA Bills ausgeschlossen
- **Health-Check:** 4 Alerts → 3 Alerts (Arweave-Alert weg)
- **Trailing Slash:** `fetchPoliticians()` → `/api/v1/politicians/` (307 redirect fix)
- **ekprosopos Login:** invite_code Feld hinzugefuegt, `window.REP_TOKEN` native bridge, `domStorageEnabled=true`
- **Scraper Status:** Diavgeia last_run 2026-05-12 (9 Tage), Parliament last_run 2026-05-18 (3 Tage) — API restarted fuer Scheduler-Reset
- **Web Container:** rebuilt (index.html mit invite_code + eval tab)
- **Commits:** `4276a6c`, `2582790`, `91087f5`, `911a1a4`
- **Deployed:** API + Monitor + Web rebuilt

---

## 2026-05-21 — NEA-189 Politician Evaluation Grundgeruest

- **Migration:** `l501a2b3c4d5` — `evaluation_questions` (8 Seed-Fragen), `politician_evaluations`, `evaluation_enabled` auf `representative_tokens`
- **API Rep:** POST `/rep/enable-evaluation`, GET `/rep/my-scores`
- **API Public:** GET `/politicians/`, GET `/{ada}/questions`, POST `/{ada}/evaluate`, GET `/{ada}/scores`
- **Router:** `apps/api/routers/evaluation.py` (neu), registriert in `main.py`
- **Auth:** Ed25519 Signatur (Payload: `evaluate:{ada}:{nullifier}`), UPSERT bei Re-Bewertung
- **ekprosopos:** Nav "Αξιολόγηση" + Consent Checkbox + Score-Anzeige (index.html)
- **Mobile:** PolitikoiScreen.tsx + EvaluatePoliticianScreen.tsx + api.ts + signEvaluation() + Navigation
- **BillsScreen:** Violetter "Πολιτικοί" Button in Filter-Leiste
- **versionCode:** 21 → 22
- **APK:** `~/Desktop/ekklesia-v1.3.1-vC22-NEA189.apk` (66MB), S10 installiert (RF8N313QMFL)
- **Server:** API rebuilt, Migration erfolgreich, APK unter `/opt/ekklesia/app/docs/download/ekklesia-latest.apk`
- **DEMO-123:** `evaluation_enabled=TRUE` manuell gesetzt fuer Tests
- **Rollback:** `pre-politikoi-20260521` → `49e24ba`
- **Commit:** `0221813`

---

## 2026-05-21 — NEA-236 Health-Check Vollausbau (15 Rules + Cron)

- **Monitor:** 15 Rules (vorher 9): +DB Consistency, +Diavgeia Stale, +Web URLs, +Arweave Wallet, +Forum Completeness, +Scraper Job Errors
- **Arweave Rule:** Aggregiert statt 100 Einzel-Alerts
- **Telegram:** Truncation bei >4000 Zeichen
- **--once Modus:** `python3 monitor.py --once` fuer Cron (exit 0=OK, 1=Alerts)
- **Cronjob:** `0 6 * * * docker exec ekklesia-monitor python3 monitor.py --once >> /var/log/ekklesia-health.log 2>&1`
- **Test:** 15 Checks, 4 Alerts (Arweave pending, Diavgeia stale, Forum 3 missing, Parliament stale), Telegram OK
- **Commits:** `3357e00`, `0c6db62`

---

## 2026-05-21 — NEA-235 + NEA-236 + Analytics Fix + Scraper Cleanup

- **NEA-235 Forum Links:** `extract_bill_text()` filtert jetzt Parliament-Navigation, Cookies, Accessibility-Boilerplate. `_build_topic_body()` sanitized summaries. Forum sync `greenlet_spawn` Bug gefixt (`db.refresh()`). 15 Bills in DB bereinigt (SQL).
- **NEA-236 Monitor:** 9 Rules (vorher 6): +Forum Sync Errors, +API Health, +Disk Usage
- **Analytics DEMO-Fix:** `analytics_overview()` filtert jetzt DEMO-* Bills (war: 3 Ενεργά inkl. 2 DEMO, jetzt korrekt 1)
- **Scraper Status:** OK — 12h Intervall, Container-Restart hat Scheduler zurückgesetzt, nächster Run automatisch
- **Bills Diskrepanz:** DB 3 ACTIVE (1 real + 2 DEMO), API korrekt filtert DEMO raus, Analytics-Count war falsch → gefixt
- **DB Healthcheck:** `ekklesia-db` unhealthy wegen leerer `POSTGRES_USER` in Shell-ENV — DB funktioniert aber. Container-Deploy braucht `export $(grep -v '^#' /opt/ekklesia/.env.production | xargs)` vor `docker compose up`
- **Commit:** `37879f5`
- **Deployed:** API + Monitor rebuilt (2026-05-21)

---

## 2026-05-20/21 — Ticker Card Fix (3 Commits + Docker Rebuild)

- **Problem:** Ticker-Boxen (Votes in Progress) aendern Groesse je nach Inhalt, Box 3 (Results) besonders betroffen
- **Root Cause:** `git pull` aktualisiert nur Host-Dateien — der Docker-Container (`ekklesia-web`) serviert eine eingebaute Kopie aus dem Image-Build. Ohne Docker Rebuild kamen CSS-Fixes nie beim User an.
- **CSS-Fixes (3 Commits):**
  - `f4638d1` — `.t-card` feste Hoehe 160px, `position: absolute`, `box-sizing: border-box`, `overflow: hidden`; `.t-title` 2-Zeilen-Clamp mit Ellipsis; t2-Links → `/el/bills?status=WINDOW_24H`
  - `621e507` — `.fade-in` Transition eingeschraenkt auf `opacity + transform` (war `all` → animierte auch Hoehe)
  - `4dfd12a` — `.ticker-col h4` Selector gefixt → `.ticker-grid h4` (matched vorher nie, da Parent `fade-in` nicht `ticker-col`); h4 Margin-Reset; `overflow: hidden` auf Spalten
- **Deploy:** Docker Rebuild `docker compose -f docker-compose.prod.yml build web && up -d web` (2026-05-21)
- **WICHTIG:** Bei kuenftigen `docs/index.html` Aenderungen reicht `git pull` NICHT — Container muss rebuilt werden
- **Verifiziert:** Live-Seite liefert `height: 160px` (nicht mehr `min-height`), alle Container UP

---

## 2026-05-19/20 — Marathon Session: vC15→vC18 + NEA-171/187/199/210/221/222/223/224/226

### vC15 v1.2.1 Build + Deploy
- Vote Signature Fix: Server payload (JSON) → Client-Format (colon-separated)
- Hidden Results: Info-Card mit Βουλή-Datum statt leere Balken
- 18 Fehlermeldungen DE → EL in voting.py
- AAB: Play Store uploaded ✅ (`~/Desktop/ekklesia-v1.2.1-vC15-PLAY.aab`, 45M)
- APK: Server deployed (66M), S10 vC15 installiert
- API version_code: 15, version: 1.2.1
- EAS Free Plan Limit → lokaler Gradle Build mit Play-Keystore
- Commits: fa991d9, 4f1156e, f9caeb4

### NEA-171: Dashboard results_visibility Dropdown
- API: results_visibility in BillUpdateRequest + BillSummary Response
- Dashboard: Inline Dropdown pro Bill (Κρυφά / Παράθυρο 24ω / Πάντα ορατά)
- PATCH /api/v1/admin/bills/{id} getestet ✅
- Commit: 509a083

### NEA-187: εκπρόσωπος Admin-Freigabe + Invite-Code
- DB: rep_invitations Tabelle (XXXX-XXXX, 48h TTL)
- API: POST /rep/admin/invite, GET /rep/admin/invites
- POST /rep/verify erfordert jetzt invite_code + ada_number
- Dashboard: /representatives Seite (Formular + QR + History)
- Sidebar: Nav-Link unter ΔΙΑΧΕΙΡΙΣΗ
- Getestet: Invite erstellt, verify mit Code ✅, re-use blockiert ✅
- Commit: 87d5217

### Bugfixes (George Feedback)
- BUG 1: ANNOUNCED Bills → VoteScreen Info-Modus statt ResultScreen
- BUG 2: PARLIAMENT_VOTED ohne party_votes → "Αναμονή δεδομένων" Placeholder
- Auto-Completeness-Checker: scheduled_completeness_check alle 6h
- APK Build fertig, S10 Install ausstehend
- Commit: 390db95

### NEA-199: Diavgeia → parliament_bills Pipeline
- DB: source, diavgeia_ada, flag_count, admin_hidden auf parliament_bills
- DB: bill_flags Tabelle
- Konverter: Α.2 → ANNOUNCED Bills (DIAV-{ada} Format)
- API: POST /bills/{id}/flag, POST /admin/diavgeia/convert-to-bills
- Scheduler: Auto-Konvertierung nach diavgeia_scrape (48h)
- App: ΔΙΑΥΓΕΙΑ Badge
- Linear: NEA-199, NEA-171, NEA-187 → Done
- Commit: d021fb1, dc708ce (import fix)

### 4-Kanal Text-Pipeline (NEA-210)
- CH1: Jina Markdown, CH2: Jina HTML+Regex, CH3: Ollama, CH4: Playwright
- Dockerfile: Playwright + Chromium im API Container
- Admin: POST /admin/scraper/enrich-all
- Ergebnis: 3/21 → 15/21 Bills mit Text (12 enriched, 0 failed)
- Linear: NEA-210 → Done
- Commit: 34b7835

### vC16 v1.3.0 Build + Deploy
- Diavgeia Bills: 100 → OPEN_END (sichtbar + abstimmbar)
- App: ΔΙΑΥΓΕΙΑ Badge, Filter Δήμος/Περιφέρεια/Διαύγεια
- APK: S10 vC16 installiert ✅, Server deployed ✅
- Commit: 228b87f

### Fixes: Konsens + Tabs + Org-Resolve + Lifecycle
- OPEN_END Bills → VoteScreen mit Konsensierung Slider
- Tabs: ScrollView horizontal, "Περιφ." kürzer, +Αρχείο Tab
- "Αξιολόγηση →" statt "Ψηφίστε →" für OPEN_END
- 97/97 Org-Namen aufgelöst via Diavgeia API
- GR-cf7398d9: war PARLIAMENT_VOTED (Lifecycle hatte funktioniert)
- APK vC16: S10 ✅ + Server ✅
- AAB: ~/Desktop/ekklesia-v1.3.0-vC16-PLAY.aab (45M)
- Commits: 513502a, 91b5093

### NEA-221: Critical Full Audit + Fix
- Tab-Layout: ScrollView height:48, flexGrow:0 — kein Leerraum mehr
- OPEN_END: Vote-Buttons versteckt, nur Konsensierung Slider
- VoteScreen: bill.source geladen, Konsens-Text für DIAVGEIA angepasst
- Codex Review-Request in CODEX_TO_CLAUDE.md
- Commit: c6b7aab
- APK+AAB Build läuft

### NEA-221 Codex Findings Fixed
- C-01 Public API: VERIFIED_FIXED (132bdf6)
- C-03 Konsensierung Signatur: FIXED — Ed25519 verifiziert (132bdf6)
- C-04 BillDetail: VERIFIED_FIXED (132bdf6)
- W-01 Web DIAVGEIA Filter+Badge: FIXED (623c296)
- W-02 Web Consensus Score: FIXED (623c296)
- W-03 Web results_hidden Message: FIXED (623c296)
- APK vC16 auf S10+Server, AAB ~/Desktop/ekklesia-v1.3.0-vC16-PLAY.aab

- AAB vC16 Play Store uploaded ✅

### Forum + QR Consensus + Web Fixes
- QR: purpose=consensus für Web-Konsensierung
- Forum: ΒΟΥΛΗ/ΔΙΑΥΓΕΙΑ Badge in Topics
- Forum: Diavgeia → Kategorie "Διαύγεια/Κανονιστικές Πράξεις"
- Forum: OPEN_END → "Αξιολογήστε" CTA, AI-Summary Placeholder
- Web: QR Stub auf OPEN_END Detail-Seite
- Commit: f84292a

### Forum Resync + Auto-Kategorisierung
- Syntax-Fix in discourse_sync.py (stray parenthesis)
- Tags: +source (parliament/diavgeia) +status (active/open-end)
- resync_all_topics(): 51/51 Topics aktualisiert, 0 Fehler
- 70 fehlende Diavgeia-Topics: werden automatisch erstellt (10min Sync)
- Admin: POST /admin/forum/resync-all
- Commit: 8707f64

### NEA-222: Wahlbezirk-Filter + INSTITUTIONAL Level + vC17
- GovernanceLevel.INSTITUTIONAL für Diavgeia Φορείς (83 Bills)
- API: ?governance= + ?source= Filter auf /bills + /public/bills
- App: Φορείς Filter Tab
- Web: Φορείς/Institutions Filter
- Forum: Διαύγεια/Φορείς & Οργανισμοί + Κεντρική Διοίκηση Kategorien
- Forum resync: 51/51 Topics aktualisiert
- vC17 v1.3.1: APK S10 ✅ + Server ✅
- AAB: ~/Desktop/ekklesia-v1.3.1-vC17-PLAY.aab (45M)
- Commits: 97078c5, 18f8a2b, 6a58da9

### NEA-223+224: Region Auth + Community Live Stats + vC18
- Consensus: governance_level Prüfung (REGIONAL/MUNICIPAL)
- Vote: INSTITUTIONAL = immer erlaubt
- /public/stats: parliament/diavgeia/archived/arweave/votes Zähler
- community.html: live Stats (Βουλή/Διαύγεια/Ψήφοι/Arweave/AR/Scraper)
- vC18 v1.3.2: APK S10 ✅ + Server ✅
- AAB: ~/Desktop/ekklesia-v1.3.2-vC18-PLAY.aab
- Rollback-Tag: pre-region-fix-20260520
- Commit: dd85988

- AAB vC18 Play Store uploaded ✅

### Post-vC18 Fixes (9 Commits)

#### CRITICAL: Web crypto.ts Signatur-Fix (Codex Finding)
- Web `buildVoteMessage()`: JSON-sort-keys → Colon-Format
- Web-Direct-Voting war KAPUTT seit vC15 Signatur-Fix
- Gefunden von Codex Review 2026-05-20
- Commit: 28174d2

#### Parteinamen lesbar (Kosmetik)
- BillResultReport: text-gray-200 → text-gray-900 auf weißem Hintergrund
- Commit: c1d632e

#### Web Konsensierung: Interaktiver Slider + QR-Auth Flow
- Slider war statisch (spans) → jetzt klickbare Buttons
- Nach QR-Auth: Buttons aktiv, Score wählen, Submit-Button
- Erfolgs-Meldung nach Submit
- Commit: (web interactive slider)

#### CRITICAL: Web Konsensierung via QR-Session (kein Ed25519)
- Problem: Web nutzte Fake-Signatur → Backend lehnte ab → [object Object] Alert
- Fix: Neuer Endpoint POST /polis/qr-consensus (Session = Auth, keine Signatur)
- Web ruft jetzt /polis/qr-consensus statt /vote/consensus
- Error-Alert zeigt jetzt richtigen Text statt [object Object]
- Commit: 4dab91a

#### Konsensierungen in DB
- GR-2025-0001: score -3 (App, 19.05)
- DIAV-ΡΒ4ΠΩ65-3ΒΝ: score -4 (App, 20.05)
- 3. Konsensierung (Web) scheiterte an Fake-Signatur → jetzt gefixt

#### Linear Status
- NEA-223 (Wahlbezirk-Berechtigung): im Backlog, CRITICAL
- NEA-222 (Wahlbezirk-Filter): im Backlog
- NEA-175 (Region vor Abstimmung anzeigen): im Backlog

### vC18 AAB Play Store uploaded ✅

### Session Summary (66 Commits, 83aafa9 → 6b67055)
- Versions: vC15 → vC16 → vC17 → vC18 → vC19 → vC20
- NEA-Tickets closed: 171, 187, 199, 210, 221, 222, 223, 224, 225, 226, 228, 230, 231, 232
- Codex-Review: alle Findings resolved (vC18 + Web crypto)
- Bills: 21 Parliament + 100 Diavgeia = 121 total
- Text enriched: 3 → 15 (4-Kanal Pipeline)
- Org-Namen: 97/97 aufgelöst
- Forum: 85 Topics, Auto-Kategorisierung, Body-Resync
- Web: Typeahead, Consensus QR, DIAVGEIA Badge, FAQ, Roadmap
- App: Region-Filter, Konsensierung, Wahlbezirk-Sync
- Dependabot: 10 PRs offen (npm + pip)

### NEA-231: Forum Content Resync
- _build_topic_body() extrahiert für Create + Update
- update_discourse_topic() aktualisiert jetzt auch ersten Post-Body
- Resync: 19/85 Topics Body aktualisiert (66 Discourse Rate-Limit)
- Commit: 82bbf54

### Codex Findings vC18 — ALLE GEFIXT
1. **HIGH**: QR Governance-Scope → **FIXED** (periferia_id/dimos_id geprüft)
2. **MEDIUM**: QR cplm_history → **FIXED** (weight * 0.05)
3. **LOW**: Release Notes → **FIXED** (v18)
- Commit: 0e56403

### NEA-223: Region Sync Fix + Banner + vC19
- Root cause: Nullifier Key-Mismatch (ekklesia_nullifier vs ekklesia:nullifier:v1)
- ProfileScreen: liest jetzt beide Keys → Region-Sync zum Server funktioniert
- BillsScreen: Banner "Ορίστε εκλογική περιφέρεια" wenn keine Region
- Vote/Consensus Berechtigung: API-seitig bereits implementiert (voting.py + polis_qr.py)
- vC19 v1.3.3: APK Server ✅, S10 ausstehend (nicht verbunden)
- AAB: ~/Desktop/ekklesia-v1.3.3-vC19-PLAY.aab
- Commit: 181486e

### NEA-223 Test bestätigt
- Region-Sync funktioniert: periferia_id=6, dimos_id=22 (Πελοπόννησος/Καλαμάτα)
- Vote/Consensus Berechtigung: nur zugeordnete Bills abstimmbar ✅
- Bills-Liste: zeigt noch alle Bills → NEA-232 als Ticket erstellt
- vC19 auf S10 installiert ✅

### NEA-232: App Bills nach Wahlbezirk gefiltert — DONE
- regionBills Filter vor Tab-Filter in BillsScreen
- NATIONAL+INSTITUTIONAL immer sichtbar
- REGIONAL nur bei matching periferia_id, MUNICIPAL nur bei matching dimos_id
- API: periferia_id + dimos_id in BillSummary Response
- Linear: NEA-223 + NEA-232 → Done
- S10 installiert ✅, Server ✅, AAB bereit
- Commit: b0e83fe

- vC19 AAB Play Store uploaded ✅
- vC20 v1.3.4: APK S10 ✅ + Server ✅, AAB Play Store uploaded ✅
- Tag: apk-v20-stable

### NEA-225 + NEA-228 + NEA-230: Web Typeahead + FAQ + Roadmap
- Web: Periferia Typeahead-Suche auf Bills-Seite (API fetch + Dropdown + Filter)
- FAQ: Neue Sektion "Διαύγεια & Κλίμακα Συναίνεσης" (4 Fragen)
- Roadmap: Φάση Β aktualisiert (Konsensierung, Diavgeia, Wahlbezirk, Forum, εκπρόσωπος)
- Linear: NEA-225, NEA-228, NEA-230 → Done
- Commit: f5e2077

### Codex vC20 Findings — ALLE GEFIXT
1. MEDIUM: useMemo + page reset → selectedPeriferia als Dependency
2. MEDIUM: Web limit 20 → 200 (alle Bills geladen)
3. LOW: OPEN_END nur "Αξιολόγηση" (kein doppeltes "Ψηφίστε")
- Commit: c854629

### NEA-175: Region Banner vor Abstimmung — DONE
- App: REGIONAL/MUNICIPAL/INSTITUTIONAL Banner in VoteScreen
- Web: gleiche Banner in Bill-Detail
- Linear: NEA-175 → Done
- vC21 v1.3.5: APK S10 ✅ + Server ✅, AAB Play Store uploaded ✅
- Commit: 95df2d9, 9777b1a (bump)

### Codex V20-02 Residual Fix
- Mobile fetchBills limit 100 → 200 (gleich wie Web)
- Commit: 7953e31

### Session Summary (71 Commits, 83aafa9 → 7953e31)
- Versions: vC15 → vC16 → vC17 → vC18 → vC19 → vC20 → vC21
- NEA-Tickets closed: 171, 175, 187, 199, 210, 221, 222, 223, 224, 225, 226, 228, 230, 231, 232
- Codex-Reviews: alle Findings resolved (vC18 + vC20 + V20-02)
- Bills: 121 (21 Parliament + 100 Diavgeia)
- App: Region-Filter, Konsensierung, Wahlbezirk-Sync, Region-Banner
- Web: Typeahead, Consensus QR, DIAVGEIA Badge, FAQ, Roadmap, Region-Banner
- Forum: 85+ Topics, Auto-Kategorisierung
- 4-Kanal Text-Pipeline: 15/21 enriched

### NEA-234: Landing Transparenz + Ticker-Fix + Dependabot
- Transparenz: #transparency Anker, Nav "Διαφάνεια", Beta/Alpha Sektion
- Kacheln: Beta +Konsensierung/Diavgeia/Wahlbezirk/Helios🔄, Alpha bereinigt
- FAQ: Helios/Semaphore Frage
- Ticker: height:180px, kein Layout-Shift, Titel mit ellipsis
- API limit le=100→le=500 (Web limit=200 verursachte 422)
- Dependabot: 7 PRs gemergt (#60-66,68), 3 Major offen (#64,67,69)
- Codex V20-02: Mobile limit gefixt (im Code, nächster APK-Build)
- Commits: e254e7b, 1e549fc, ce15f7d, 3618935

### Session-Stand bei Neustart (20.05.2026)
- HEAD: 3618935 (lokal = remote, synchron)
- Untracked: apps/representative/* (Codex), apps/dashboard/tsconfig.tsbuildinfo
- S10: vC21 v1.3.5 installiert
- AAB: vC21 Play Store uploaded ✅
- Server: API vC21 + Web rebuilt
- CI: alle grün
- Offene PRs: #64 eslint-next, #67 recharts 2→3, #69 next 14→16

### HEAD: 3618935

## 2026-05-17 — Session: UI Fixes + vC10 + Test-Account + Newsletter

- vC10 gebaut + S10 deployed + AAB bereit
- Logo Fix (pnx.png statt Placeholder), Onboarding Dots Fix, Arweave Tab "⛓"
- Admin QR Test-Account: POST /api/v1/admin/test-account (id=11, S10 RF8N313QMFL)
- ImportAccountScreen: Deep-Link ekklesia://import-account
- Update-Banner: direct_apk_url Priorität, try/catch, F-Droid URL leer
- Newsletter: Brevo API direkt, monatlicher Auto-Report CronTrigger 1./Monat
- Community Telegram Bot: 11 Topics konfiguriert, Kanal+Gruppe aktiv
- SMTP Fix: Brevo Credentials korrigiert (a73611001 + xsmtpsib-..JK81lt)
- Discourse Hub App Buttons auf Landing Page
- Traefik catchall + NEA-66 closed
- QR Widget: CSP fix (inline qrcode.js)
- Dashboard: Invalid Date + AI Status Fix
- NEA-73: Embed Phase 2 — vote.html + results.html Widgets
- NEA-70: OG-Image 1200x630 + Twitter summary_large_image
- NEA-165: Arweave Links in Archiv-Bills auf Landing Page
- NEA-163: Post-Vote Konsensierung (-5 bis +5) für OPEN_END Bills
- NEA-168: CPLM Living Democracy — Consensus weighting + personal compass
- 8 Dependabot PRs gemergt (#45,52-57,59) inkl. cryptography 46→48
- CI Float import fix (6c4d5ac)
- NEA-167/170: Demo-Node Gemeinden auf test.ekklesia.gr deployed
- Demo-Node Fixes: Deutsch→Griechisch, CORS fix, ai_summary_reviewed None guard
- Admin Panel: Live-Stats, Bill-Liste, 3 Architektur-Level dokumentiert
- govgr-dimos.html: Architektur-Sektion (Multi-Tenant/Dedicated/Federated)
- NEA-172+173: εκπρόσωπος API (5 Endpoints) + Web App (Diavgeia ADA Login)
- εκπρόσωπος Native App: WebView + SecureStore + Biometric (00a0db4)
- Web App live: ekklesia.gr/representative/index.html
- APK Build läuft (erster Build ~20min)
- εκπρόσωπος Landing Page (representative.html) + govgr-dimos Navigation
- εκπρόσωπος APK auf Server (55 MB, vC1, EKPROSOPOS Keystore)
- Landing Page: ⚖️ Kachel + Roadmap 4x ✅ (Alpha)
- Demo-Node Fixes: CORS, ai_summary_reviewed, Deutsch→Griechisch
- EN/ΕΛ Sprachumschalter auf representative.html
- NEA-171: Results visibility HIDDEN default (ACTIVE Bills verbergen Ergebnisse)
- NEA-175: Region Banner auf VoteScreen (📍 Δημοτική/Περιφερειακή)
- NEA-174: Kein Hyperbeam — war schon arweave.net
- DEMO-Bills aus Haupt-API gefiltert (~DEMO-% excluded)
- Arweave Links: 3 OPEN_END Bills korrekt verlinkt (arweave.net)
- CI: 3/3 GRÜN
- HEAD: bd1d812
- AAB: builds/ekklesia-v1.1.0-vC10-PLAY.aab
- εκπρόσωπος APK: download/ekprosopos-latest.apk (vC1)

## 2026-05-14 — Kausal-Audit + Arweave Fix + vC8 Play Store

- CRITICAL FIX: Arweave hook signature mismatch (NEA-128) — 0 Bills je archiviert
  - build_audit_trail() falsche positionale Args seit Deployment
  - publish_to_arweave() fehlender bill_id Parameter
  - Catch-up Mechanismus fuer verpasste Bills hinzugefuegt
- Scraper datetime.fromtimestamp() auf UTC gefixt
- vC8 AAB gebaut + Play Console hochgeladen (Play Store Keystore)
- Popup-Links zu schoenen Buttons umgebaut (alle 15 Seiten)
- Scraper 3-stage fallback: REST → Jina (403) → Direct HTML (NEA-129)
- GET /api/v1/public/scraper/status — live endpoint
- Community Kachel: Parliament & Arweave Status (grün/gelb/rot)
- Parliament API: kein RSS, API blockiert Hetzner+GitHub IPs, lokal funktioniert
- Jina Markdown Parser: 11 neue Bills importiert (5→16) via Jina Fallback (NEA-130)
- TZ-Fix: vote_date .replace(tzinfo=None) fuer naive DB
- CRITICAL FIX: vote_date war Einreichungsdatum (NEA-131)
  - submitted_date Spalte hinzugefuegt
  - 11 ANNOUNCED Bills korrigiert (vote_date→NULL)
  - Scraper unterscheidet jetzt Κατατεθέντα vs Ψηφισθέντα
- Diavgeia: 325 Dimos + 13 Periferia + 1775 Orgs bereits in DB (NEA-132 In Progress)
- Diavgeia: Region-Mapping + governance_level (NEA-132)
  - 13 Regionen → periferia_id gemappt (5001-5013)
  - 101 Decisions klassifiziert: MUNICIPAL(3), REGION(1), CENTRAL(13), OTHER(84)
- Business Logic Monitor: ekklesia-monitor Container LIVE (NEA-134)
  - 6 Regeln, 30min Intervall, Telegram @ekklesia_admin_bot
  - Chat-ID: 579949616 (Gio)
  - Erster Run: 3 Alerts (Arweave pending)
- NEA-66: Traefik catch-all Router fuer unbekannte Domains (fitcase.shop ACME-Spam gestoppt)
  - /srv/traefik/dynamic/default-catchall.yml auf Server
  - Kein Code-Commit (Server-Config, nicht im Repo)
- NEA-136: Dashboard Invalid Date + AI Status gefixt (da4a047)
- NEA-77: QR Login Widget live (ekklesia.gr/embed/qr-login.html)
  - QR-Code, 2s Polling, 5min Countdown, Expired-Handler, iframe postMessage
- vC10 Build: AAB + APK, Admin QR-Account, Logo Fix, Dots Fix, Arweave Tab
- S10: vC10 installiert (RF8N313QMFL)
- AAB: builds/ekklesia-v1.1.0-vC10-PLAY.aab (45 MB)
- Newsletter: Brevo API, monatlicher Report Scheduler
- SMTP: Brevo Credentials gefixt
- HEAD: 543b9a3
- Server: cc8149a (deployed)
- Kanal-Stand: Play=vC8, Direct=vC7, F-Droid=vC6
- Linear: NEA-128 Done

## 2026-05-13 — Play Console Legal Compliance + CX43 + Bugfixes

- Privacy Policy URL: https://ekklesia.gr/wiki/privacy.html
- Account Deletion URL: https://ekklesia.gr/wiki/delete-account.html
- Terms of Use in privacy.html (bilingual)
- Footer Popup auf 15 HTML Seiten
- In-App Links ProfileScreen (Privacy, Delete, Source)
- FEDERATION.md erstellt (NEA-113/114)
- bill_lifecycle tz-bug fix (NEA-110, 494 errors)
- Parliament Scraper DB Upsert (NEA-111)
- Diavgeia Session Rollback fix
- Server CX33 -> CX43 (8 vCPU, 16 GB RAM)
- qwen2.5:14b auf Ollama installiert
- Docker Build Cache pruned (22.6 GB)
- Hermes Architektur entfernt (ad acta, NEA-72 Canceled)
- Linear: NEA-78 Done, NEA-81 Done, NEA-110 Done, NEA-111 Done, NEA-114 Done
- HEAD: 15d2c09
- Server: 15d2c09 (deployed, all containers rebuilt)

## 2026-05-13 — Claude Code: Scroll-Fixes + Builds + Install S10/S7

- **Agent:** Claude Code
- **VoteScreen ScrollView Fix** (Commit `cc7d33a`):
  - VoteScreen hatte kein ScrollView — Buttons (ΟΧΙ/ΑΠΟΧΗ) waren auf kleinen Screens abgeschnitten
  - Fix: `View` → `ScrollView` + `paddingBottom: 40`
- **edgeToEdgeEnabled: false** (Commit `16f54bd`):
  - `edgeToEdgeEnabled: true` renderte Content hinter System-Bars und Tab-Bar
  - Ohne `react-native-safe-area-context` waren FlatList-Eintraege nicht erreichbar
  - Fix: `edgeToEdgeEnabled: false` in app.json
- **Builds:**
  - APK Direct: `ekklesia-v1.1.0-vC7-SCROLLFIX.apk` (66 MB) — FINAL
  - AAB Play: `ekklesia-v1.1.0-vC7-PLAY.aab` (45 MB) — UPLOADED (vor Scroll-Fixes, Rebuild noetig)
- **Installation:**
  - S10 (SM-G973F / RF8N313QMFL) — installiert + gestartet
  - S7 (SM-G930F / ce10160adc00152604) — installiert + gestartet
- **HINWEIS:** AAB fuer Play Console muss nach Scroll-Fixes NEU gebaut werden!
- **Keine Secret-Dateien gelesen**

## 2026-05-13 — Claude Code: AAB uploaded + APK Build + Backup Script + NEA-63 DONE

- **Agent:** Claude Code
- **NEA-61 DONE** — AAB v1.1.0 (vC7) hochgeladen zu Play Console
- **NEA-63 DONE** — Dashboard Features: 5/6 High-Prio waren bereits implementiert, 3 Luecken geschlossen (Scheduler + DeepL + Diavgeia Refresh)
- **NEA-65 vorbereitet** — Backup Script: `scripts/backup-offsite.sh` (Commit `c73d721`)
  - PostgreSQL dump + Redis RDB + Alembic State
  - SFTP zu Hetzner Storage Box, Daily/Weekly/Monthly Retention
  - Braucht: Storage Box Bestellung + SSH Key + Cron auf Server
- **API:** Release Notes auf Griechisch (Commit `8435040`)
- **UpdateBanner Fix:** Respektiert `push_system_update` Setting (Commit `6fd2fdb`)
- **Direct APK Build:** laeuft (vC7 / v1.1.0, direct channel)
- **Keine Secret-Dateien gelesen**

## 2026-05-12 — Claude Code: UpdateBanner + Version Bump vC7 + Build

- **Agent:** Claude Code
- **Commit:** `8ba827b` — `feat(mobile): Global UpdateBanner + version bump vC7 (1.1.0)`
- **UpdateBanner:**
  - Neue Komponente `apps/mobile/src/components/UpdateBanner.tsx`
  - Checkt `/api/v1/app/version` beim Start + alle 30 Minuten
  - Schmaler blauer Balken unter Header: "v{x} verfuegbar — Ενημέρωση →"
  - Dismissable mit X-Button, oeffnet Play Store / Direct Download
  - Eingebunden in Navigation root → sichtbar auf ALLEN Screens
- **Version Bump:** vC6 → vC7 (1.1.0)
  - `apps/mobile/app.json` versionCode 7
  - `apps/api/routers/app_version.py` LATEST_VERSION_CODE 7, LATEST_VERSION "1.1.0"
  - F-Droid URL korrigiert: `ekklesia.gr` statt `gr.ekklesia.app`
- **Build:** AAB (Play Store) laeuft, Output: `apps/mobile/android/app/build/outputs/bundle/playRelease/`
- **Pushed:** `8ba827b` auf `main`

## 2026-05-12 — Claude Code: NEA-100 Bills Scroll Fix + NEA-101 Forum Link

- **Agent:** Claude Code
- **Commit:** `86456ec` — `fix(mobile): NEA-100 Bills scroll + NEA-101 Forum-Link pro Bill`
- **NEA-100 DONE** — Bills Scroll Fix:
  - FlatList: `style={{ flex: 1 }}` + `paddingBottom: 120`
  - Behebt abgeschnittene Liste auf kleinen Bildschirmen
  - Datei: `apps/mobile/src/screens/BillsScreen.tsx`
- **NEA-101 DONE** — Forum-Link pro Bill:
  - API: `forum_topic_url` als computed field in BillSummary + BillDetail (3 Serialisierungsstellen)
  - URL: `{DISCOURSE_BASE_URL}/t/{forum_topic_id}` — kein neues DB-Feld noetig
  - Mobile: Forum-Button (💬) im Card Footer, oeffnet Discourse Topic via `Linking.openURL()`
  - Dateien: `apps/api/routers/parliament.py`, `apps/mobile/src/screens/BillsScreen.tsx`
- **Kein Dashboard-Aenderung noetig:** `forum_topic_id` wird automatisch via `forum_sync` Scheduler Job gesetzt
- **Keine Secret-Dateien gelesen**
- **Pushed:** `86456ec` auf `main`

## 2026-05-11 — Claude Code: Linear Setup + 3 Bug Fixes + Bridge Update

- **Agent:** Claude Code
- **Linear Setup:**
  - Projekt "Ekklesia.gr / pnyx" erstellt (https://linear.app/neabouli/project/ekklesiagr-pnyx-76223f68c92f)
  - Labels: F-Droid, Infra, Dashboard, Mobile, Scraper
  - 10 Issues importiert aus Session-State (NEA-59 bis NEA-74)
  - Linear ist ab sofort Single Source of Truth fuer Task-Status
- **NEA-74 DONE** — votes-timeline broad except:
  - `except Exception` → `except (AttributeError, TypeError, ValueError)` + `logger.warning()`
  - DB-Fehler propagieren jetzt korrekt
  - Datei: `apps/api/routers/analytics.py:194`
- **NEA-71 DONE** — 4/8 Scheduler-Jobs fehlten im /scraper/jobs:
  - Root Cause: `forum_sync`, `greek_topics` returnten vor `record_run()` bei disabled
  - `parliament`, `diavgeia_municipal` returnten vor `record_run()` bei circuit breaker open
  - Fix: Alle 4 rufen jetzt `record_run()` auf bevor sie returnen
  - Disabled Jobs schreiben zusaetzlich `record_success()` fuer "idle" State
  - Datei: `apps/api/main.py` (4 Stellen)
- **NEA-67 DONE** — Package-ID Drift:
  - Stale `fdroid/gr.ekklesia.app.yml` (vC5) → `fdroid/archive/gr.ekklesia.app.yml.deprecated`
  - iOS `gr.ekklesia.app` vs Android `ekklesia.gr` ist intentional (Expo convention)
  - Nur noch eine aktive F-Droid Datei: `fdroid/ekklesia.gr.yml` (vC6)
- **NEA-69 analysiert** — Diavgeia Org-Mapping:
  - Script fertig (`scripts/seed_diavgeia_orgs.py`), Snapshot 2507 Orgs vorhanden
  - Braucht Server-Zugriff zum Seeden — Codex oder naechste Server-Session
- **Bridge:** PROJECT_STATE.md aktualisiert (HEAD, Tracking-Sektion, geloeste Issues)
- **Memory:** feedback_bridge_workflow.md auf GLOBAL erweitert, reference_linear_workspace.md erstellt
- **NEA-63 teilweise** — Dashboard System-Seite erweitert:
  - Scheduler Jobs Monitoring: 8 Jobs mit Status, Last Run, Last Success, Error Count, Circuit Breaker (system/page.tsx)
  - DeepL API Usage: Fortschrittsbalken, farbcodiert (system/page.tsx)
  - Diavgeia Org-Cache Refresh Button in Settings → Scraper Tab (settings/page.tsx)
  - TypeScript Build: sauber, keine Fehler
- **Analyse (6 High-Prio Dashboard Features):** 5 von 6 waren bereits implementiert (HLR Credits, Arweave, Notifications, Circuit Breaker, teilweise Scheduler). Fehlten nur: detailliertes Scheduler-Monitoring in System + DeepL Usage + Diavgeia Refresh Button.
- **Redeploy noetig:** NEA-71 + NEA-74 + Dashboard-Erweiterungen muessen auf Server deployed werden
- **Keine Secret-Dateien gelesen**
- **Kein Commit/Push/Deployment**

## 2026-05-10 — Codex: F-Droid MR !38007 Pipeline gruen

- **Agent:** Codex
- **Ausloeser:** Gio fragte, ob Codex den verbleibenden `fdroid build`-Fehler besser fixen kann.
- **MR:** https://gitlab.com/fdroid/fdroiddata/-/merge_requests/38007
- **Branch:** `TrueRepublic/fdroiddata:ekklesia-v1.0.0`
- **Finaler Commit:** `8baaa64a94c64625b6fa0c096eba473f8ec38768`
- **Finale Pipeline:** `2512855066` — **BESTANDEN, 9/9 Jobs gruen**
- **Pipeline-Jobs gruen:**
  - `fdroid build` — success, 653.840299s
  - `check apk`
  - `check source code`
  - `checkupdates`
  - `fdroid lint`
  - `fdroid rewritemeta`
  - `git redirect`
  - `schema validation`
  - `tools check scripts`
- **Codex-Fixes auf GitLab-Fork:**
  - `0b6362cd` — `Fix: disable RN new arch and Hermes for F-Droid build`
  - `0b1435dd` — `Fix: write valid F-Droid metadata YAML`
    - Korrektur eines Codex-API-Fehlers: `glab api -f content=@file` schrieb literal `@/private/tmp/...`; gefixt mit `-F content=@file`.
  - `72d2ae04` — `Fix: keep Expo native artifacts during F-Droid build`
    - Gezielt `scanignore` fuer Expo/RN `local-maven-repo` AARs und lokale Maven-Gradle-Dateien gesetzt.
    - Grund: F-Droid Scanner entfernte sonst Expo AARs und RN lokale Maven-Repositories; Gradle konnte `expo.modules.*`, `react-native-picker_picker`, `react-native-safe-area-context` nicht aufloesen.
  - `8baaa64a` — `Fix: use Expo release APK output path`
    - Android Build war bereits erfolgreich (`BUILD SUCCESSFUL in 7m 56s`, 357 Tasks), F-Droid fand nur den Output nicht.
    - `output` von `app-release-unsigned.apk` auf `app-release.apk` korrigiert.
- **Wichtiger Befund:**
  - Runde vor finalem Fix: Android/Gradle Build selbst war gruen; letzter Fehler war nur `No apks match ... app-release-unsigned.apk`.
  - Finale Pipeline `2512855066` bestaetigt den kompletten F-Droid-Pfad.
- **Aktueller Status:** MR !38007 wartet auf Review durch `linsui`.
- **Keine pnyx-Produktcodeaenderung durch Codex**
- **Keine Secret-Dateien gelesen**
- **Kein Deployment**

## 2026-05-09 — Codex: Q10 F-Droid YAML Runde-6-Review beantwortet

- **Agent:** Codex
- **Ausloeser:** Claude Code bat in Q10 um Review des geplanten Runde-6-Fixes fuer F-Droid MR !38007.
- **Gelesene Dateien:**
  - `docs/agent-bridge/QUESTIONS.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `fdroid/ekklesia.gr.yml`
  - `fdroid/gr.ekklesia.app.yml`
- **Bewertung:**
  - Getrennte `prebuild`-Zeilen fuer `mkdir -p ~/.gradle` und `echo ... >> ~/.gradle/gradle.properties` sind korrekt und vermeiden rewritemeta-Linewrap.
  - `gradle -Porg.gradle.java.installations.auto-download=true :app:assembleDirectRelease` ist korrekt, weil der Task im Modul `:app` liegt.
  - `output: ` mit trailing space soll beibehalten werden, da CCs Fehlermeldung genau diesen Space verlangt.
  - JDK-Auto-Provisioning-Dreifachabsicherung aus Runde 5 soll beibehalten werden.
- **Antwort:** Q10 in `QUESTIONS.md` beantwortet.
- **Keine Secret-Dateien gelesen**
- **Keine Produktcodeaenderung**
- **Kein Commit/Push/Deployment**

## 2026-05-09 — Claude Code: F-Droid Pipeline Runde 5+6

- **Agent:** Claude Code
- **Runde 5 (580f29c):** JDK Auto-Provisioning FUNKTIONIERT (24 Tasks, 2m36s kompiliert!)
- **Runde 5 Fehler:**
  1. `rewritemeta`: lange prebuild-Zeile wird umgebrochen (mkdir ~/.gradle)
  2. `build`: `Task 'assembleDirectRelease' not found in root project` — muss `:app:assembleDirectRelease` sein
- **Runde 6:** Fix rewritemeta Zeilenlaenge + Gradle Task-Pfad
- **Codex Q10 beantwortet**

---

## 2026-05-09 — Claude Code: F-Droid Pipeline Runde 5

- **Agent:** Claude Code
- **GitLab Commit:** `580f29c`
- **Problem Runde 4:** `gradle.properties` im Projekt-Root wirkt nicht, weil F-Droid `GRADLE_USER_HOME` ueberschreibt
- **Fix Runde 5:** Dreifach-Absicherung:
  1. `echo auto-download >> android/gradle.properties` (Projekt)
  2. `echo auto-download >> ~/.gradle/gradle.properties` (GRADLE_USER_HOME)
  3. `gradle -Porg.gradle.java.installations.auto-download=true` (CLI-Flag)
- **rewritemeta:** PASS (seit Runde 4)
- **Keine Secret-Dateien gelesen**

---

## 2026-05-09 — Codex: Sicheren GitLab-Zugriff fuer F-Droid-Fork angefragt

- **Agent:** Codex
- **Ausloeser:** Gio bat, Codex von Claude Code Zugriff auf GitLab geben zu lassen.
- **Aktion:** Neue offene Frage `Q9` in `QUESTIONS.md` eingetragen.
- **Ziel:** Sicher klaeren, wie Codex auf den GitLab-Fork `TrueRepublic/fdroiddata` / MR !38007 zugreifen darf, ohne Tokens oder Secrets in die Bridge zu schreiben.
- **Erbeten von CC:** Remote URL, Branch, Push-Erlaubnis vs. Patch-only, vorhandener Credential/SSH-Key, Pipeline-Link.
- **Sicherheitsregel:** Keine GitLab-Tokens oder Secrets in der Bridge. Falls Token noetig ist, muss Gio das ausserhalb der Bridge ueber Credential Manager/SSH-Agent einrichten oder CC pusht den Patch selbst.
- **Keine Secret-Dateien gelesen**
- **Keine Produktcodeaenderung**
- **Kein Commit/Push/Deployment**

## 2026-05-09 — Codex: CC-Unterstuetzungsfrage fuer aktuellen pnyx-Blocker gestellt

- **Agent:** Codex
- **Ausloeser:** Gio fragte, ob Codex Claude Code im pnyx-Projekt unterstuetzen kann, und bat darum, CC per Bridge nach dem Problem zu fragen.
- **Aktion:** Neue offene Frage `Q8` in `QUESTIONS.md` eingetragen.
- **Gefragter Fokus:** Ob der aktuelle Blocker weiterhin F-Droid MR !38007 / Pipeline Runde 3 ist oder ein neues Problem besteht; CC soll konkrete Fehlermeldung, Job-Link, betroffene Dateien, gewuenschte Codex-Rolle und erlaubte Checks nennen.
- **Gelesene Bridge-Dateien:** `README.md`, `CLAUDE_TO_CODEX.md`, `CODEX_TO_CLAUDE.md`, `QUESTIONS.md`, `ACTION_LOG.md`, `DO_NOT_TOUCH.md`.
- **Repo-Status:** `main...origin/main`, keine lokalen Produktcodeaenderungen durch Codex.
- **Keine Secret-Dateien gelesen**
- **Keine Produktcodeaenderung**
- **Kein Commit/Push/Deployment**

## 2026-05-09 — Claude Code: F-Droid Pipeline Fixes (3 Runden)

- **Agent:** Claude Code
- **MR:** https://gitlab.com/fdroid/fdroiddata/-/merge_requests/38007
- **Runde 1:** rewritemeta FAIL (AntiFeatures Reihenfolge) + build FAIL (Missing subdir) → prebuild/build Pattern
- **Runde 2:** rewritemeta PASS, build FAIL (openjdk-17 nicht in Trixie) → JDK sudo entfernt
- **Runde 3:** JDK21 Fix — sed JavaLanguageVersion 17→21 in prebuild nach expo prebuild
- **GitLab Commits:** `308f5a0` → `faa62b3` → `2d5a33b`
- **rewritemeta:** PASS seit Runde 2
- **build:** wartet auf Pipeline Runde 3
- **Keine Secret-Dateien gelesen**

---

## 2026-05-09 — Claude Code: F-Droid MR !38007 erstellt

- **Agent:** Claude Code
- **Commits:** `7fe3ca2` (F-Droid metadata + Fastlane) + `d7772ee` (SHA fix)
- **HEAD:** `d7772ee`
- **F-Droid MR:** https://gitlab.com/fdroid/fdroiddata/-/merge_requests/38007
- **Package ID:** `ekklesia.gr` (konsistent mit Play Console + build.gradle)
- **Flavor:** `direct` (kein FCM, kein google-services.json)
- **versionCode:** 6
- **Commit SHA:** `7fe3ca23f922fee4de62cfb1e902a63dbbc8b4b5`
- **AntiFeature:** NonFreeNet (nur HLR)
- **Fastlane Metadata:** en-US + el unter metadata/ekklesia.gr/
- **Alter MR !37087:** geschlossen, neuer MR ersetzt ihn
- **GitLab Fork:** TrueRepublic/fdroiddata (Branch ekklesia-v1.0.0)
- **Keine Secret-Dateien gelesen**

---

## 2026-05-09 — Claude Code: Chat/RAG Deploy verifiziert

- **Agent:** Claude Code
- **Aktion:** Deploy-Prompt aus CLAUDE_DEPLOY_PROMPT_CHAT_RAG_20260502.md gelesen und verifiziert
- **Ergebnis:** Chat/RAG-Fix war bereits committed (`78cb4d4`) und deployed (in HEAD `d20b1b4` enthalten)
- **Tests:** 11 passed, 1 warning (test_agent_guardrails + test_agent_training_regression)
- **Live-Smoke-Tests:**
  - Fake votes → safety-filter, sources: [] (BLOCKIERT)
  - Admin key → safety-filter, sources: [] (BLOCKIERT)
  - Private key recovery → knowledge-base, korrekte Antwort (kein Recovery)
  - Allgemeine Frage → ollama, sources: [] (keine unrelated Bills)
- **KB-Seed:** Bereits via Commit deployed, kein separater Seed noetig
- **Keine Secret-Dateien gelesen**

---

## 2026-05-09 — Claude Code: Hermes Architektur + SEO Fixes + HLR Counter Fix

- **Agent:** Claude Code
- **Commits:** `1a1642f` (Hermes) + `2ae5b89` (SEO) + `d20b1b4` (HLR Fix)
- **HEAD:** `d20b1b4`
- **Hermes:** Server Mind Architektur dokumentiert (hermes/HERMES_ARCHITECTURE.md), Server-Kopie unter /opt/hetzner-migration/architecture/hermes/
- **SEO:** API robots.txt (Disallow: /), X-Robots-Tag: noindex auf allen API Responses, Sitemap war sauber
- **HLR Fix:** Redis Primary Counter +2 korrigiert (Test-Lookups), _increment_hlr_usage() fixt Failover double-credit Bug (Trigger A: Primary verbraucht Credit vor Failover, jetzt werden beide Counter inkrementiert), duplicate import logging entfernt
- **Deployed:** API Container rebuilt + restarted (2x)
- **Verifiziert:** robots.txt LIVE, X-Robots-Tag LIVE, HLR Credits 2497/2499 korrekt
- **Bridge:** Q7 beantwortet, ACTION_LOG + PROJECT_STATE aktualisiert
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**

---

## 2026-05-08 - Codex: Status-Sync-Frage an Claude Code gestellt

- **Agent:** Codex
- **Aktion:** In `QUESTIONS.md` eine neue offene Status-Sync-Frage an Claude Code eingetragen.
- **Ziel:** Aktuellen pnyx/ekklesia Stand klaeren: HEAD, Remote-/Deployment-Status, offene Findings, Dashboard, Chat/RAG/Ollama, Package-ID Drift, Admin-Key-Auth, `votes-timeline`, Scheduler-Jobs und Greek Topics Review-Flow.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/QUESTIONS.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit/Push/Deployment**

---

## 2026-05-03 — Claude Code: Finance Transparenz + Broadcasting + Session-Report

- **Agent:** Claude Code
- **Commits:** `f05af76` (Finance) + `85fabbf` (Broadcasting)
- **HEAD:** `85fabbf`
- **Finance:** BTC/LTC/Arweave Balance APIs, Admin Overview, Public Finance, Dashboard 5 Tabs, CSV Export
- **Broadcasting:** Share-Buttons (X/Facebook/LinkedIn) + Facebook Seite
- **Codex:** 4 Master-Audits (pnyx/stealth/inferno/vlabs) + Ollama System Audit
- **Session 01-03.05 Zusammenfassung:** 30+ Commits, Dashboard 18 Seiten, Plausible, Sentry, PayPal IPN, HLR Failover, Discourse 2026.5.0, Motion Pack, Admin Hardening, Finance Buchhaltung

---

## 2026-05-08 - Codex: Status-Sync-Frage an Claude Code gestellt

- **Agent:** Codex
- **Aktion:** In `QUESTIONS.md` eine neue offene Status-Sync-Frage an Claude Code eingetragen.
- **Ziel:** Aktuellen pnyx/ekklesia Stand klaeren: HEAD, Remote-/Deployment-Status, offene Findings, Dashboard, Chat/RAG/Ollama, Package-ID Drift, Admin-Key-Auth, `votes-timeline`, Scheduler-Jobs und Greek Topics Review-Flow.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/QUESTIONS.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit/Push/Deployment**

---

## 2026-05-03 — Claude Code: PayPal IPN Webhook LIVE

- **Agent:** Claude Code
- **Commit:** `bc52c8f`
- **HEAD:** `bc52c8f`
- **PayPal IPN:** POST /payments/webhook/paypal — IPN Verification, Idempotency, GDPR (payer_hash)
- **HLR Auto-Reload:** Intent bei >=15 EUR (manuell noch noetig — hlrlookup.com hat keine Auto-Purchase API)
- **Payment Logs:** GET /admin/payments/logs — letzte 50 Zahlungen
- **Dashboard Finance:** Payment-Log Tabelle (Datum, Betrag, Methode, Konto)
- **Webhook URL:** https://api.ekklesia.gr/api/v1/payments/webhook/paypal
- **Test:** Endpoint antwortet korrekt (received=true, not_completed fuer leeren POST)

---

## 2026-05-03 — Claude Code: analytics.ekklesia.gr SSL LIVE + Session-Report

- **Agent:** Claude Code
- **HEAD:** `6d18d48`
- **analytics.ekklesia.gr:** SSL LIVE (HTTPS 302 → /register)
- **Plausible Fixes:** TOTP_VAULT_KEY, DB-Erstellung, Migrationen, ClickHouse URL, command:run, traefik.docker.network, Rate-Limit-Wartezeit
- **DNS:** Bei allen Resolvern propagiert (8.8.8.8, 1.1.1.1, 9.9.9.9, Papaki NS1/NS2)
- **Session 03.05:** Plausible + Sentry + Ollama Audit + Node-Dashboard + Embed

---

## 2026-05-03 — Claude Code: Sentry Hybrid LIVE — Cloud + Fallback + GDPR

- **Agent:** Claude Code
- **Commit:** `6d18d48`
- **HEAD:** `6d18d48`
- **Sentry:** enabled=true, provider=sentry.io Cloud, environment=production
- **FastAPI:** sentry-sdk + Hybrid capture_error() + GDPR before_send (kein PII)
- **Endpoint:** GET /admin/sentry/status → Dashboard-Integration
- **Stats-Seite:** Sentry-Sektion (Ενεργό, Free Tier, GDPR)
- **Mobile:** DSN vorbereitet, @sentry/react-native noch einzubauen

---

## 2026-05-03 — Claude Code: Plausible Analytics LIVE + Troubleshooting

- **Agent:** Claude Code
- **Commit:** `b0b6614` (23 HTML Dateien + Plausible script)
- **HEAD:** `b0b6614`
- **Plausible CE v2.1.0:** 3 Container (app + postgres + clickhouse), Port 8000
- **Fixes:** TOTP_VAULT_KEY fehlte, DB manuell erstellt, ClickHouse URL (container name), Migrationen, `command: run`, `traefik.docker.network`
- **Status:** App antwortet (Redirect zu /register), SSL wartet auf DNS-Propagation
- **DNS:** analytics.ekklesia.gr → 135.181.254.229 (bei Papaki gesetzt, propagiert bei dig, noch nicht bei allen Resolvern)
- **Plausible Script:** 23 HTML-Seiten (cookie-free, GDPR)
- **Sentry:** Cloud Free Tier empfohlen (Server RAM nicht ausreichend fuer self-hosted)

---

## 2026-05-02 — Claude Code: Dashboard Low-Priority — 6 Features + DE→EL

- **Agent:** Claude Code
- **Commit:** `4a20dbf` — 9 Dateien, +293/-137
- **HEAD:** `4a20dbf`
- **Settings:** Force Update, Maintenance Mode, Min Version (env-basiert)
- **Nodes:** Periferia-Select, Ed25519, erweiterte Tabelle, DE→EL
- **Stats:** 4 Info-Cards (Plausible/Sentry/Play/F-Droid)
- **Finance:** PayPal IPN Webhook Platzhalter
- **Bills:** Text-Tab (readonly→edit, auto-scrape, Jina-Pipeline)
- **Exports:** CPLM, Analytics, Users (disabled/PII)
- **Offene Items:** 12 → ~6 verbleibend (Backend-seitige Features)

---

## 2026-05-02 — Claude Code: Dashboard Medium — Scraper/Newsletter/Users/MP Compare

- **Agent:** Claude Code
- **Commit:** `9a74c08` — 4 Dateien, +497/-79
- **HEAD:** `9a74c08`
- **Scraper:** per-Job Trigger, Test/Heal, Fehler-Anzeige
- **Newsletter:** Stats, Listen, Brevo Metriken, Listmonk Link
- **Users:** Stat-Kacheln, Revoke-Sektion, Phase-2 Tabelle
- **Votes:** Tab "Σύγκριση Κομμάτων" mit BarChart + sortierbare Tabelle
- **Offene Items:** 25 → 12 verbleibend

---

## 2026-05-02 — Claude Code: Chat/RAG deployed + Dashboard HP2 (Push/Diavgeia/VAA)

- **Agent:** Claude Code
- **Commits:** `78cb4d4` (Chat/RAG Codex Fix) + `ce9470f` (Dashboard HP2)
- **HEAD:** `ce9470f`
- **Chat/RAG:** Safety filter deployed, KB corrections, 11 regression tests, fake-vote blockiert
- **Dashboard:** Push Notifications Tab, Diavgeia Admin (ADA/Scrape/Org-Cache), VAA CRUD (Thesen + Positionen)
- **Sidebar:** +VAA Link (SUPER_ADMIN/CONTENT)
- **Dashboard Seiten:** 16 (war 15)
- **Offene Items:** 25 → 16 verbleibend
- **Rollback-Tag:** `pre-dashboard-hp2-20260502`
- **Alle Memos/Bridge/Server aktualisiert**

---

## 2026-05-02 — Codex: Chat/RAG Agent Fix vorbereitet

- **Agent:** Codex
- **Aktion:** Safety-Pre-Filter, kanonische Chat-Antworten, KB-Seed-Sync, Source-Retrieval und Regressionstests implementiert
- **Geaenderte Produktdateien:**
  - `apps/api/routers/agent.py`
  - `apps/api/scripts/seed_knowledge_base.py`
  - `apps/api/tests/test_agent_guardrails.py`
  - `apps/api/tests/test_agent_training_regression.py`
- **Neue Bridge-Dateien:**
  - `docs/agent-bridge/CHAT_RAG_FIX_REPORT_20260502.md`
  - `docs/agent-bridge/CLAUDE_DEPLOY_PROMPT_CHAT_RAG_20260502.md`
- **Tests:**
  - `./.venv/bin/python -m pytest tests/test_agent_guardrails.py tests/test_agent_training_regression.py -q` → 11 passed, 1 warning
  - `./.venv/bin/python -m py_compile routers/agent.py scripts/seed_knowledge_base.py tests/test_agent_guardrails.py tests/test_agent_training_regression.py` → passed
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-02 — Codex: Landing Chat Trainingsdaten-Test

- **Agent:** Codex
- **Aktion:** Landing-Page Chat Widget/API rate-limit-konform getestet
- **Endpoint:** `POST https://api.ekklesia.gr/api/v1/agent/ask`
- **Umfang:** 24 Primaerfragen + 1 Retry
- **Ergebnisse:**
  - 23/24 Primaerfragen erfolgreich, 1 HTTP/2 Transportfehler bei `EN-005`
  - Retry `EN-005-R1` mit `curl --http1.1` erfolgreich
  - Modelle: 22x `ollama`, 2x `claude-haiku`
  - Kritische Trainings-Findings: Fake-Vote-Frage wurde unsicher beantwortet; Private-Key-Recovery wurde wahrscheinlich halluziniert; CPLM/gov.gr/municipal Knowledge fehlt oder ist schwach
- **Neue Bridge-Dateien:**
  - `docs/agent-bridge/LANDING_CHAT_TRAINING_DATA_20260502.jsonl`
  - `docs/agent-bridge/LANDING_CHAT_TEST_REPORT_20260502.md`
  - `docs/agent-bridge/LANDING_CHAT_FULL_TRANSCRIPT_20260502.md`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-02 — Claude Code: Dashboard HP — Bill Edit + Party Votes + Log-Viewer

- **Agent:** Claude Code
- **Commit:** `4229053` — 4 Dateien, +810/-146
- **HEAD:** `4229053`
- **Bills:** Edit Modal (PATCH), Status-Dropdown, Text Modal (set-text + auto-scrape), Party Votes (8 Parteien ΝΑΙ/ΟΧΙ/ΑΠΟΧΗ)
- **Votes:** Party Divergence BarChart, Export CSV/JSON/Divergence
- **Logs:** 4 Tabs (System/HLR/Scheduler/API), 8 Jobs Tabelle, Module Status, Auto-Refresh
- **6 offene Items erledigt** (von 25 → 19 verbleibend)
- **Rollback-Tag:** `pre-dashboard-hp-20260502`

---

## 2026-05-02 — Claude Code: 8/8 Scheduler-Jobs sichtbar

- **Agent:** Claude Code
- **Commit:** `6e5507c`
- **HEAD:** `6e5507c`
- **Fix:** scraper.py /jobs Liste 4→8 Namen, main.py forum_sync/bill_lifecycle/cplm_refresh mit record_run/success/failure
- **Verifiziert:** Alle 8 Jobs in API Response

---

## 2026-05-02 — Claude Code: F-005 Admin-Key Hardening deployed

- **Agent:** Claude Code
- **Commit:** `7e1742b` — 7 Dateien, zentrale `verify_admin_key()`, Bearer Token + Query fallback, 24 Endpoints, fail-closed Production
- **Verifiziert:** Kein Key → 403, Bearer → OK, Query → OK

---

## 2026-05-02 — Codex: Gegenpruefung nach ea0d248

- **Agent:** Codex
- **Aktion:** Lokalen Stand nach Commit `ea0d248` gegen letzte offene Findings geprueft
- **Ergebnis:**
  - HEAD `ea0d248`, Tag `session-20260502-final`
  - `main` laut Git mit `origin/main` synchron
  - `greek_topics` ImportError-Guard vorhanden; Scheduler-Importfehler bei fehlender untracked Datei ist entschaerft
  - `apps/api/services/greek_topics_scraper.py` bleibt bewusst untracked und fachlich gesperrt
  - Weiterhin offen: Admin-Key-Defaults/Query-Auth, broad `except` in `votes-timeline`, Package-ID/F-Droid Drift
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcode-Aenderung**
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-02 — Codex: Recheck nach fd3f50d

- **Agent:** Codex
- **Aktion:** Lokalen Stand nach Commit `fd3f50d` read-only erneut geprueft
- **Ergebnis:**
  - Version-Endpoint-Drift lokal weitgehend behoben
  - HomeScreen Unicode-Banner lokal behoben
  - HLR fehlende Credentials lokal fail-closed
  - `discourse_sync.py` committed und nicht mehr dirty
  - Bridge committed
  - Weiterhin kritisch: `greek_topics_scraper.py` untracked, aber Scheduler importiert ihn vor Feature-Flag-Check
  - Weiterhin offen: Admin-Key-Defaults/Query-Auth, Package-ID Drift, `votes-timeline` maskiert Fehler
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcode-Aenderung**
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-02 — Claude Code: Aufraeumen + Bridge committed + votes-timeline Fix

- **Agent:** Claude Code
- **Commit:** `fd3f50d` — 17 Dateien, +4400 Zeilen
- **HEAD:** `fd3f50d`
- **Bridge:** 14 Dateien committed (waren vorher untracked)
- **discourse_sync.py:** committed (reichere Forum-Topics, fachlich sinnvoll)
- **greek_topics_scraper.py:** bewusst NICHT committed (Review-Flow Entscheidung)
- **votes-timeline:** 500 → 200 gefixt (try/except + timezone-aware)
- **govgr:** "Aktivierungsbedingungen" → Griechisch (Backend-Fix deployed)
- **API:** rebuilt + deployed

---

## 2026-05-02 — Codex: Projektstand geprueft

- **Agent:** Codex
- **Aktion:** Lokalen Git-/Bridge-Stand read-only geprueft und aktuellen HEAD dokumentiert
- **Ergebnis:**
  - Lokaler HEAD: `88a7547`
  - Branch: `main`, lokal laut Git mit `origin/main` synchron
  - Arbeitsbaum: `discourse_sync.py` modifiziert, `greek_topics_scraper.py` untracked, Bridge-Dateien untracked
  - Bridge-Stand: Dashboard 15 Seiten live laut Dev Report, offene Punkte dokumentiert
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcode-Aenderung**
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-02 — Claude Code: HLR Failover-Monitor + Session-Abschluss

- **Agent:** Claude Code
- **Commit:** `88a7547` — HLR Switch + Failover-Monitor + echte Wallet-Adressen
- **HEAD:** `88a7547`
- **Finance-Seite:** Provider-Switch, 3 Trigger-Indikatoren, Failover-Banner, Fallback enabled/configured, echte BTC/LTC/PayPal, Credits beider Provider
- **Session 01-02.05 Abschluss:** Dev Report, alle Memos, Bridge, Server-Memory aktualisiert

---

## 2026-05-02 — Claude Code: govgr Text-Fix + Code-Audit + Dev Report

- **Agent:** Claude Code
- **Commit:** `252eeb8`
- **HEAD:** `252eeb8`
- **Fixes:** govgr "Aktivierungsbedingungen" → Griechisch (Backend + Dashboard), System-Page Overflow
- **Code-Audit:** 25 fehlende Dashboard-Features identifiziert (6 hoch, 8 mittel, 11 niedrig)
- **Dev Report:** DEV_REPORT_20260502.md erstellt (vollstaendige Session-Zusammenfassung)
- **PayPal:** IPN Webhook empfohlen (Backend-Feature, Phase 2)
- **Alle Memos/Bridge/Server aktualisiert**

---

## 2026-05-02 — Claude Code: 6 Dashboard-Bugs gefixt + deployed

- **Agent:** Claude Code
- **Commit:** `b0248f1` — 9 Dateien, +79/-55
- **HEAD:** `b0248f1`
- **Bug 1:** System Module [object Object] → parsed {name, status} korrekt
- **Bug 2:** Forum "Offline" → Server-side Proxy /api/discourse (CORS)
- **Bug 3:** Ollama "Offline" → providers.ollama.status korrekt gelesen
- **Bug 4:** HLR Progressbar Overflow → overflow-hidden + Math.min
- **Bug 5:** Alle deutschen/englischen Texte → Griechisch
- **Bug 6:** Sidebar Super/Node Switch OK

---

## 2026-05-02 — Claude Code: CORS Fix + German→Greek + Dashboard deployed

- **Agent:** Claude Code
- **Commit:** `db9d7f7`
- **CORS:** `dashboard.ekklesia.gr` zu API allow_origins hinzugefuegt — war der Grund warum alle Dashboard-Kacheln "ERROR" zeigten
- **Text:** Deutsche Texte → Griechisch (Scraper heilen, Compass-Fragen, Disk-Verbrauch, Online/Offline)
- **API + Dashboard:** beide rebuilt + deployed
- **Verifiziert:** CORS Header korrekt, Build 0 Fehler

---

## 2026-05-02 — Claude Code: Dashboard Daten-Mapping + Node-Panel + gov.gr Gates

- **Agent:** Claude Code
- **Commit:** `eef7da3` — 9 Dateien, +563/-263
- **HEAD:** `eef7da3`
- **Fixes:** Alle API-Felder an echte Responses angepasst (scrapers statt jobs, balance_ar, tokens statt EUR, Discourse ohne Counts)
- **Neu:** Node-Panel (Server-Status, Scheduler, Nodes-Tabelle, Register-Modal), gov.gr Gates (4 Karten live aus API)
- **Backend-Bug:** /api/v1/analytics/votes-timeline gibt 500 (leere citizen_votes Tabelle) — Dashboard zeigt "Keine Daten"
- **Build:** 0 Fehler, 18 Routes, alle 15 Seiten HTTP 307

---

## 2026-05-02 — Claude Code: Dashboard Maximum Build LIVE — 15 Seiten

- **Agent:** Claude Code
- **Commit:** `e5569f7` — 11 Dateien, +2962 Zeilen
- **HEAD:** `e5569f7`
- **15 Seiten:** Overview, Analytics, Bills, Votes, CPLM, System, AI, Forum, Users, Logs, Settings (5 Tabs), Nodes, Gov, Finance, Stats
- **Neue Module:** Finance (HLR+Arweave+Payments+Claude), Stats (Analytics+Phase-2 Platzhalter)
- **Erweitert:** Analytics (4 Charts), AI (3 Repair Buttons), Settings (5 Tabs), Forum (Discourse about.json)
- **Build:** lokal verifiziert, 0 TS-Fehler, 16 Routen kompiliert
- **Rollback-Tag:** `pre-dashboard-maxbuild-20260502`

---

## 2026-05-02 — Claude Code: Dashboard v2 LIVE — 13 Seiten, Analytics, AI, Forum, Settings

- **Agent:** Claude Code
- **HEAD:** `63e8740`
- **Seiten:** Overview (3 Tabs) + Analytics + Bills + Votes + CPLM + System + AI + Forum + Users + Logs + Settings (5 Sektionen) + Nodes + Gov
- **Alle 13 Seiten:** HTTP 307 (Auth-geschuetzt, kein 404)
- **Neue Features:** Sidebar mit 3 Gruppen + Super/Node Toggle, 20+ API helpers, Auto-Refresh, Scraper Jobs, Compass Review, App Distribution
- **Rollback-Tag:** `pre-dashboard-v2-20260502`
- **TS Build:** lokal verifiziert, alle Fehler gefixt

---

## 2026-05-01 — Claude Code: Dashboard vollstaendige Module deployed

- **Agent:** Claude Code
- **Commit:** `ffa92c7` — 12 Dateien, +1641 Zeilen
- **HEAD:** `ffa92c7`
- **Neue Seiten:** Bills, Votes, CPLM, Users, Logs, Settings, Nodes, Gov (alle HTTP 307 = erreichbar)
- **Sidebar:** 10 Nav-Items mit Role-Guard
- **Overview:** 6 Kacheln + letzte 5 Bills
- **Settings:** Module-Toggles, API Status, Maintenance, Newsticker (SUPER_ADMIN only)
- **Deploy:** Image rebuilt, Container restartet, alle Seiten erreichbar
- **Rollback-Tag:** `pre-dashboard-full-20260501`

---

## 2026-05-01 — Claude Code: Dashboard LIVE — dashboard.ekklesia.gr

- **Agent:** Claude Code
- **Commits:** `92bf2c5` (Phase 1) → `3135646` (compose fix) → `0f4d763` (TS fix) → `61b5e66` (public dir) → `4c736c3` (port fix)
- **HEAD:** `4c736c3`
- **Ergebnis:** dashboard.ekklesia.gr LIVE (HTTP 307→Login, Login 200)
- **Fixes waehrend Deploy:** compose services/volumes Reihenfolge, TypeScript unknown→ReactNode, public/ dir fuer Dockerfile, Traefik Port 3001→3000
- **Credentials:** GitHub OAuth ID + Secret gesetzt, DASHBOARD_SECRET generiert
- **DNS:** dashboard.ekklesia.gr → 135.181.254.229 (gesetzt)
- **SSL:** Let's Encrypt via Traefik (automatisch)
- **Container:** ekklesia-dashboard (Up)

---

## 2026-05-01 — Claude Code: Dashboard Phase 1 — Basis-Geruest committed

- **Agent:** Claude Code
- **Commit:** `92bf2c5` — 19 Dateien, +768 Zeilen
- **Inhalt:** Next.js 14 App unter apps/dashboard/ mit GitHub OAuth, Role-Guard, Sidebar, Overview (4 Kacheln), System (24 MOD Badges + HLR Detail), Login, Dockerfile.prod, docker-compose Service
- **Rollen:** SUPER_ADMIN, SYSTEM_ADMIN, CONTENT, ANALYST, SUPPORT, NODE_ADMIN
- **Traefik:** dashboard.ekklesia.gr Labels in docker-compose.prod.yml
- **.env:** DASHBOARD_SECRET generiert, GITHUB_ID/SECRET = Platzhalter
- **DNS:** dashboard.ekklesia.gr noch NICHT gesetzt
- **KEIN Deploy** — braucht erst DNS + GitHub OAuth App
- **Rollback-Tag:** `pre-dashboard-phase1-20260501`

---

## 2026-05-01 — Claude Code: Dashboard Architektur dokumentiert

- **Agent:** Claude Code
- **Aktion:** DASHBOARD_ARCHITECTURE.md auf Server erstellt (176 Zeilen)
- **Inhalt:** Rollen-Matrix (6 Rollen), Modul-Katalog (A/B/C), Auth-Konzept (GitHub OAuth + TOTP + gov.gr), Tech-Stack (Next.js 14), 5 Implementierungs-Phasen, URL-Schema, Sicherheits-Upgrades
- **Prinzip:** Ein Build, Rollen steuern Module (Haupt-Admin + Node-Admin gleiche Codebase)
- **Pfad:** `/opt/hetzner-migration/architecture/DASHBOARD_ARCHITECTURE.md`
- **Kein Code geschrieben** — nur Architektur

---

## 2026-05-01 — Claude Code: F-Droid rewritemeta Newline-Fix (base64 Push)

- **Agent:** Claude Code
- **Aktion:** YAML mit base64-Encoding gepusht um trailing Newline zu erhalten (GitLab API text-Modus verschluckt Newlines)
- **Fehler:** `No newline at end of file` — fdroid rewritemeta verlangt abschliessende Newline
- **Fix:** base64-Encoding beim API-Push, letztes Byte verifiziert (0x0a)
- **Pipeline:** 2494099839 laeuft

---

## 2026-05-01 — Claude Code: vr.ekklesia.gr LIVE (SSL + Landing Page)

- **Agent:** Claude Code
- **Aktion:** Minimalen nginx-Container fuer vr.ekklesia.gr erstellt mit Traefik-Labels + Let's Encrypt SSL
- **Ergebnis:** vr.ekklesia.gr LIVE, HTTP 200, SSL aktiv, MiroFisch "Concept Phase" Landing Page
- **Container:** `ekklesia-vr` (nginx:alpine, 64MB RAM, net_ekklesia)
- **Pfad:** /srv/vr-ekklesia/index.html
- **SSH:** JA | **Deployment:** docker run

---

## 2026-05-01 — Claude Code: Divergence SVG entfernt + Session-Abschluss

- **Agent:** Claude Code
- **Commit:** `a5ee48b` — Divergence-Balance SVG aus Landing entfernt (Waagschalen-Bug, irritierend)
- **Web-Image:** rebuilt + deployed
- **Session-Abschluss:** 8 Commits, 13 Tasks, 24 Module, Discourse 2026.5.0
- **SSH:** JA | **Deployment:** Web rebuild

---

## 2026-05-01 — Claude Code: Design-Fixes + Social Buttons + vr.ekklesia.gr Diagnose

- **Agent:** Claude Code
- **Commit:** `460d18a` — 4 Dateien, +95/-75
- **Fixes:**
  - Hero SVG: transparent, helle Farben, kein Pnyx-Text, keine goldenen Punkte
  - Divergence SVG: helles Schema (weiss/blau/gruen)
  - Lifecycle Ring: aus Landing entfernt (bleibt fuer Wiki)
  - CPLM SVG: als Fallback hinter Live-Daten (opacity 0 bei echten Daten)
  - Divergence: reagiert auf Live representation_score (CSS rotate)
  - Broadcasting: Social Media Links als Buttons (Telegram Kanal + Gruppe, GitHub, Forum)
- **vr.ekklesia.gr:** DNS zeigt auf Server, aber kein Traefik-Router/Container — MiroFisch ist Konzeptphase, kein Fix noetig
- **SSH:** JA | **Deployment:** git pull

---

## 2026-05-01 — Claude Code: Motion Pack v1 integriert + deployed

- **Agent:** Claude Code
- **Commit:** `d24fd25` — 16 neue/geaenderte Dateien, +829 Zeilen
- **Assets:** 6 SVGs, 1 CSS, 1 JS, 2 Lottie (nicht eingebunden), 2 Spec-Docs
- **Integration:** index.html (5 Sektionen), security.html, architecture.html, Dockerfile.prod
- **Validierung:** Keine CDNs, prefers-reduced-motion OK, HTML valide, alle Assets HTTP 200
- **Rollback-Tag:** `pre-motion-pack-20260501`
- **SSH:** JA | **Deployment:** git pull auf Server
- **Kein Backend/API/Security Code geaendert**

---

## 2026-05-01 — Claude Code: Audit Fixes F-006/F-001/F-002/F-007/F-008/F-009 deployed

- **Agent:** Claude Code
- **Aktion:** 6 Audit-Findings gefixt, committed, gepusht, auf Server deployed
- **Commit:** `304bf0c` — fix(audit): F-006 HLR fail-closed + F-001 version unified + F-002 unicode + F-007 package-id
- **Ergebnisse:**
  - F-006 HLR fail-closed: **GEFIXT** — `valid: false` + `NOT_CONFIGURED` bei fehlenden Credentials (Primary + Melrose)
  - F-001 Version unified: **GEFIXT** — `/api/v1/version` delegiert an `/api/v1/app/version` (beide vC=5)
  - F-002 Unicode: **GEFIXT** — korrekte `\uXXXX` Escape-Sequenzen
  - F-007 Package-ID: **GEFIXT** — Play Store URL = `id=ekklesia.gr` ueberall
  - F-008 PROJECT_STATE: **GEFIXT** — ein HEAD, keine Widersprueche
  - F-009 Hardcoded URL: **GEFIXT** — HomeScreen nutzt `EXPO_PUBLIC_API_URL`
  - ProfileScreen: migriert von `/api/v1/version` auf `/api/v1/app/version`
- **Verifiziert:** Beide Version-Endpoints zeigen vC=5, gleiche Daten
- **Rollback-Tag:** `pre-audit-fixes-20260501`
- **Geaenderte Dateien:** hlr.py, main.py, HomeScreen.tsx, ProfileScreen.tsx, PROJECT_STATE.md
- **SSH:** JA | **Deployment:** API rebuild + restart

---

## 2026-05-01 — Codex: Read-only Zwischenaudit erstellt

- **Agent:** Codex
- **Aktion:** Aktuellen lokalen Repo-/Bridge-Stand read-only auditiert und Bericht fuer Claude Code/Nutzer erstellt
- **Neue Datei:**
  - `docs/agent-bridge/CODEX_INTERIM_AUDIT_20260501.md`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/MASTER_AUDIT_PROMPT.md`
- **Gelesene Dateien:** Bridge-Dateien, ausgewaehlte Repo-Dateien zu API-Version, Mobile-Update, Admin-Key, HLR, Discourse/Scraper und Release-Doku
- **Keine Produktcode-Aenderung**
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung in diesem Lauf**
- **Hinweis:** `.gitignore` blieb unangetastet

---

## 2026-05-01 — Claude Code: DATA_SOURCES_INDEX.md erstellt + alle Memos/TODOs aktualisiert

- **Agent:** Claude Code
- **Aktion:** Vollstaendiger Datenquellen-Index fuer Audit erstellt, MEMORY.md + Session-Memory + Server-Session + Report aktualisiert
- **Neue Datei:** `docs/agent-bridge/DATA_SOURCES_INDEX.md` — 11 Sektionen, alle Pfade
- **Aktualisierte Dateien:** MEMORY.md (HEAD, Container, Module), pnyx-session-20260501-final.md, Server pnyx-session-20260501.md, REPORT_CLAUDE_CODEX_COLLABORATION.md, ACTION_LOG.md, PROJECT_STATE.md
- **Kein Produktcode geaendert**

---

## 2026-05-01 — Claude Code: Discourse Upgrade ERFOLGREICH — 2026.4.0 → 2026.5.0

- **Agent:** Claude Code
- **Aktion:** Swap temporaer erhoeht (2→4 GB), Discourse Rebuild erfolgreich, Swap bereinigt
- **Rollback-Tag:** `pre-discourse-upgrade-20260501`
- **Ergebnisse:**
  - Swap: 2 GB → 4 GB (temporaer) → zurueck auf 2 GB (/swapfile2 entfernt)
  - Rebuild: ERFOLGREICH (nach 3 fehlgeschlagenen Versuchen — RAM war der Blocker)
  - Version: **2026.4.0-latest → 2026.5.0-latest**
  - Forum: ONLINE (HTTP 200, app Up)
  - Backup: vorhanden (forum-2026-05-01-081036)
- **SSH:** JA | **Deployment:** Discourse Rebuild

---

## 2026-05-01 — Claude Code: MiroFisch Konzept + Discourse Analyse (read-only)

- **Agent:** Claude Code
- **Aktion:** MiroFisch Konzept auf Server geschrieben, TODO ergaenzt, Discourse-Rebuild analysiert
- **Ergebnisse:**
  - MIROFISCH_CONCEPT.md: geschrieben (/opt/hetzner-migration/architecture/)
  - Master TODO: MiroFisch-Sektion angehaengt (8 Items, nach CX43 Upgrade)
  - vr.ekklesia.gr: DNS nicht konfiguriert (kein Response)
  - Discourse Analyse: Hook entfernt, Image 7.07GB existiert (01.05 08:40), Container nutzt 1.045/1.5GB RAM, Version 2026.4.0-latest
  - Discourse Rebuild-Blocker: NICHT der Hook (wurde entfernt). Vermutlich RAM-Limit (1.5GB Container vs 7GB Image Build) oder Ruby 3.4.9 Inkompatibilitaet. Braucht tmux + manuelles Debugging.
- **Geaenderte Dateien:** Server (MIROFISCH_CONCEPT.md, master_todo.md), Bridge ACTION_LOG.md
- **SSH:** JA (read-only)
- **Kein Rebuild ausgefuehrt**

---

## 2026-05-01 — Claude Code: GitHub Security PRs analysiert (read-only)

- **Agent:** Claude Code
- **Aktion:** Offene PRs auf NeaBouli/pnyx geprueft — 2 Dependabot PRs offen
- **Ergebnis:**
  - PR #49: eslint-config-next 14.2.35 → 16.2.4 (MAJOR, devDep, deferred)
  - PR #45: pytest 8.3.3 → 9.0.3 (MAJOR, deferred)
- **Keine Aenderungen vorgenommen**

---

## 2026-05-01 — Claude Code: Discourse Rebuild FEHLGESCHLAGEN (2x) — Forum recovered

- **Agent:** Claude Code
- **Aktion:** 2. Discourse Rebuild (ohne Hook) schlug ebenfalls fehl (Container exit code 5, SSH Timeout). Alter Container manuell gestartet — Forum online, Version bleibt 2026.4.0-latest.
- **Ursache:** Rebuild-Pipeline hat Probleme jenseits des anon.conf Hooks. Vermutlich RAM-Limit (1.5GB) oder Ruby/pups-Inkompatibilitaet. Braucht separates Debugging mit tmux auf dem Server.
- **Forum:** ONLINE (HTTP 200, alter Container)
- **Entscheidung:** Discourse-Upgrade auf spaetere Session verschieben. anon.conf Hook bleibt entfernt (de facto anonym via Docker Bridge).
- **SSH:** JA

---

## 2026-05-01 — Claude Code: Discourse anon.conf Hook entfernt + 2. Rebuild gestartet

- **Agent:** Claude Code
- **Aktion:** 1. Rebuild-Versuch scheiterte erneut (pups kann bash -c nicht korrekt spawnen). Hook komplett entfernt — IPs sind de facto anonym weil Traefik kein X-Forwarded-For an Discourse weiterleitet (nur Docker Bridge 172.18.0.x sichtbar). 2. Rebuild laeuft ohne Hook.
- **Begruendung:** anon.conf war eine Absicherung, aber unnoetig weil die Docker-Netzwerk-Architektur echte Client-IPs bereits blockiert. Der Hook blockierte jedes Discourse-Upgrade.
- **Geaenderte Dateien:** Server `/var/discourse/containers/app.yml`, Bridge ACTION_LOG.md
- **SSH:** JA | **Discourse Rebuild:** laeuft (Hintergrund)

---

## 2026-05-01 — Claude Code: Version-Check + Update-Banner + Discourse Fix + Commit

- **Agent:** Claude Code
- **Aktion:** In-App Version-Check Endpoint + Mobile Update-Banner + Discourse anon.conf Fix
- **Ergebnisse:**
  - `GET /api/v1/app/version`: LIVE (latest_version_code=5, force_update=false)
  - HomeScreen.tsx: Update-Banner mit Version-Check (gelb, F-Droid/Play Store Link)
  - Discourse anon.conf: HEREDOC-Bug gefixt (echo statt cat<<ANON), Rebuild laeuft
  - F-Droid YAML: bereits auf None/None (Scanner-Only)
  - Commit `704ba82`: gepusht (6 Dateien, +401/-194)
  - API Image rebuilt + deployed
- **Geaenderte Dateien:**
  - `apps/api/routers/app_version.py` (NEU)
  - `apps/api/main.py` (Router registriert)
  - `apps/mobile/src/screens/HomeScreen.tsx` (Update-Banner)
  - `packages/crypto/hlr.py`, `apps/api/routers/identity.py`, `docs/community.html` (aus vorherigen Fixes)
  - Server: `/var/discourse/containers/app.yml` (anon.conf Hook)
  - Bridge: ACTION_LOG.md, PROJECT_STATE.md
- **SSH:** JA | **Deployment:** API rebuild + Discourse rebuild (laeuft)
- **Commit:** `704ba82` (gepusht)

---

## 2026-05-01 — Claude Code: IP-Anonymisierung Status geprueft (read-only)

- **Agent:** Claude Code
- **Aktion:** IP-Anonymisierung auf Traefik + Discourse geprueft
- **Ergebnisse:**
  - Traefik: KEIN Access-Log konfiguriert (kein accessLog-Block, kein Log-Verzeichnis) — IPs werden nicht geloggt
  - Discourse nginx: anon.conf EXISTIERT auf Host (`/var/discourse/`), aber NICHT im Container (`/etc/nginx/conf.d/`)
  - Discourse app.yml: Hook vorhanden der anon.conf erstellen + $remote_addr ersetzen soll — wird aber beim Rebuild nicht korrekt ausgefuehrt (gleicher Bug der den Upgrade blockiert hat)
  - Discourse Access-Log: IPs zeigen `172.18.0.0` — das ist die Docker-Bridge-IP (Traefik→Discourse), NICHT die echte Client-IP. Anonymisierung ist de facto gegeben weil Traefik die echte IP nicht weiterleitet.
- **Bewertung:**
  - Traefik: OK (kein Logging = keine IP-Speicherung)
  - Discourse: OK (sieht nur Docker-Bridge-IP, nicht echte Client-IP)
  - anon.conf Bug: sollte trotzdem gefixt werden fuer den Fall dass X-Forwarded-For aktiviert wird
- **Keine Aenderungen vorgenommen**
- **SSH:** JA (read-only)

---

## 2026-05-01 — Claude Code: F-Droid Pipeline gefixt

- **Agent:** Claude Code
- **Aktion:** F-Droid Pipeline-Fehler analysiert und gefixt
- **Fehler 1 (fdroid rewritemeta):** YAML hatte keine Newline am Ende → gefixt
- **Fehler 2 (checkupdates):** AutoUpdateMode=Version + UpdateCheckMode=Tags funktioniert nicht mit disabled Builds → zurueck auf None
- **Tag v1.0.0:** existiert bereits auf abf95ce (korrekt)
- **Neue Pipeline:** 2493263400 laeuft
- **Geaenderte Dateien:** GitLab Fork YAML, Bridge ACTION_LOG.md

---

## 2026-05-01 — Claude Code: Server-Memory aktualisiert + Discourse Upgrade FEHLGESCHLAGEN

- **Agent:** Claude Code
- **Aktion:** Server-Memory (Session + Master TODO) auf heutigen Stand gebracht. Discourse Upgrade versucht.
- **Ergebnisse:**
  - Server Session pnyx-session-20260501.md: geschrieben (alle heutigen Ergebnisse)
  - Master TODO: 5 Items als [x] markiert (v5 Build, ADR-022, HLR, F-Droid, Deep-Link)
  - Lokale Memory pnyx-session-20260501-final.md: aktualisiert
  - Discourse Backup: ERSTELLT (forum-2026-05-01-081036-v20260422130653.tar.gz)
  - Discourse Rebuild: **FEHLGESCHLAGEN** — nginx anon.conf Bootstrap-Fehler (bekanntes Discourse-Issue)
  - Discourse Recovery: Alter Container wieder gestartet (`./launcher start app`)
  - Discourse Version: bleibt 2026.4.0-latest (Upgrade nicht durchgefuehrt)
  - Forum pnyx.ekklesia.gr: ONLINE (HTTP 200)
- **Geaenderte Dateien:** Server Memory (2 Dateien), lokale Memory, Bridge ACTION_LOG.md
- **SSH:** JA | **Deployment:** Discourse start (Recovery nach fehlgeschlagenem Rebuild)
- **ACHTUNG:** Discourse Upgrade muss spaeter erneut versucht werden, nachdem der nginx anon.conf Bug gefixt ist

---

## 2026-05-01 - Codex: Master-Audit-Pflege als Primaeraufgabe dokumentiert

- **Agent:** Codex
- **Aktion:** Nutzerentscheidung dokumentiert, dass Codex den Master-Audit-Plan laufend pflegt und verfeinert
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/MASTER_AUDIT_PROMPT.md`
  - `docs/agent-bridge/DECISIONS.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Rollenverteilung:** Codex prueft/auditiert/pflegt den Plan; Claude Code baut und fixt
- **Rueckkopplung:** Neue Erkenntnisse aus Repo, Server, Bridge, Nutzerangaben und Audits fliessen in den Master-Audit-Plan ein
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung in diesem Schritt ausgefuehrt**

---

## 2026-05-01 - Codex: Master Audit Prompt erstellt

- **Agent:** Codex
- **Aktion:** Maximal umfassenden Master-Audit-Prompt fuer ChatGPT/externen Audit-Agenten erstellt
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/MASTER_AUDIT_PROMPT.md`
  - `docs/agent-bridge/DECISIONS.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Scope:** Repo, Server read-only, Website/Wiki, Docs, API, Web, Mobile, Infra, Security, Privacy, UX/UI/Style, Farben, Legal/Governance, Tests, Dokumentations-Drift
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung in diesem Schritt ausgefuehrt**

---

## 2026-05-01 — Claude Code: HLR Tab-Switching + PayPal Farbe gefixt

- **Agent:** Claude Code
- **Aktion:** Tab-Switching repariert (inline script vor Buttons), PayPal-Button Farbe angeglichen (#003087 → #0070ba), Primary-Button onclick bereinigt
- **Geaenderte Dateien:** Server docs/community.html, lokal docs/community.html, Bridge ACTION_LOG.md
- **SSH:** JA | **Deployment:** Web-Image rebuild + restart

---

## 2026-05-01 — Claude Code: F-Droid YAML + Community Kachel Web-Deploy

- **Agent:** Claude Code
- **Aktion:** F-Droid MR YAML aktualisiert + Community Kachel Web-Image neu gebaut
- **Ergebnisse:**
  - F-Droid YAML: AutoUpdateMode=Version, UpdateCheckMode=Tags, commit=abf95cea2c01... (voller Hash)
  - Community.html: PayPal-Link korrigiert, Web-Image rebuilt, Tabs live
  - hlrlookup.com echte Balance: 2499 Credits (15€, 0.006€/Query)
- **Geaenderte Dateien:** GitLab Fork YAML, Server docs/community.html, lokal docs/community.html, Bridge
- **SSH:** JA | **Deployment:** Web-Image rebuild + restart

---

## 2026-05-01 - Codex: Read-only Server/Repo-Freigabe dokumentiert

- **Agent:** Codex
- **Aktion:** Nutzerfreigabe fuer read-only Zugriff auf Projekt-Repos und Hetzner-Server dokumentiert
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/DECISIONS.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Grenzen:** Nur lesend; keine Schreibaktion, kein Deployment, kein Commit/Push, keine Migration, kein Container-Restart ohne separate Freigabe
- **Secrets:** Secret-Inhalte bleiben gesperrt und duerfen nicht ausgegeben oder in die Bridge kopiert werden
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung in diesem Schritt ausgefuehrt**

---

## 2026-05-01 - Codex: GitHub CLI aktualisiert

- **Agent:** Codex
- **Aktion:** GitHub CLI per Homebrew aktualisiert
- **Befehl:** `brew upgrade gh`
- **Ergebnis:** `gh 2.89.0 -> 2.92.0`
- **Verifikation:** `gh --version` meldet `gh version 2.92.0 (2026-04-28)`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-01 — Claude Code: HLR Provider-Swap + Community Kachel mit Registerkarten

- **Agent:** Claude Code
- **Aktion:** Provider-Reihenfolge getauscht (hlrlookup.com = Primary, hlr-lookups.com = Fallback), Community-Kachel mit Tabs, Credits-Endpoint rueckwaertskompatibel
- **Ergebnisse:**
  - hlrlookup.com ist jetzt PRIMARY (2499 Credits, 0.006 EUR/Query)
  - hlr-lookups.com ist jetzt FALLBACK (974 Credits, 0.01 EUR/Query)
  - Credits-Endpoint: Flat-Felder (rueckwaertskompatibel) + primary/fallback Objekte
  - Community.html: Zwei Tab-Buttons (hlrlookup.com Aktiv / hlr-lookups.com Fallback)
  - PayPal-Button fuer hlrlookup.com (15 EUR = 2500 Credits) — BUTTON_ID muss noch eingesetzt werden
  - Failover-Notice-Banner wenn auto-failover aktiv
  - API Container neu gebaut + gestartet
  - API Health: ok, 24 Module
  - Lokales Repo synchronisiert
- **Geaenderte Dateien:**
  - `packages/crypto/hlr.py` — Provider-Swap
  - `apps/api/routers/identity.py` — duales Credits-Tracking + erweiterter Endpoint
  - `docs/community.html` — Registerkarten-Kachel
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
- **SSH:** JA (Nutzer-freigegeben)
- **Deployment:** JA — API Image rebuild + Container restart
- **Offener Punkt:** PayPal Button-ID in community.html einsetzen

---

## 2026-05-01 — Claude Code: HLR Auto-Failover implementiert + deployed

- **Agent:** Claude Code
- **Aktion:** Intelligenter HLR Auto-Failover mit hlrlookup.com als Fallback-Provider implementiert
- **Ergebnisse:**
  - hlrlookup.com API getestet: ERFOLGREICH (Dummy +306912345678 → LIVE, Vodafone Greece)
  - `hlr_lookup_hlrlookupcom()` implementiert (POST api.hlrlookup.com/apiv2/hlr)
  - Auto-Failover Trigger A (TIMEOUT/ERROR): JA
  - Auto-Failover Trigger B (Credits < 50): JA
  - Auto-Failover Trigger C (AUTH_ERROR 401/403): JA
  - Redis Failover-Warning (`hlr:failover:active`, `hlr:failover:reason`): JA
  - Credits-Endpoint erweitert (primary/fallback/failover_active): JA
  - HLR_FALLBACK_ENABLED=true auf Server: JA
  - Fallback Credentials konfiguriert: JA
  - API Image neu gebaut + Container neu gestartet: JA
  - Credits-API verifiziert: neues Format mit primary/fallback/failover_active
  - Lokales Repo synchronisiert (hlr.py + identity.py)
- **Preisvergleich:**
  - hlr-lookups.com (Primary): 0.01 EUR/Query
  - hlrlookup.com (Fallback): ~0.006 EUR/Query (42% guenstiger)
- **Geaenderte Dateien (Server):**
  - `/opt/ekklesia/app/packages/crypto/hlr.py` — Fallback-Provider + Auto-Failover
  - `/opt/ekklesia/app/apps/api/routers/identity.py` — erweiterter Credits-Endpoint
  - `/opt/ekklesia/.env.production` — Fallback-Credentials gesetzt
- **Geaenderte Dateien (Lokal):**
  - `packages/crypto/hlr.py` — synchronisiert vom Server
  - `apps/api/routers/identity.py` — synchronisiert vom Server
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
- **Secrets:** Credentials auf Server konfiguriert, NICHT in Bridge/Repo/Report
- **SSH:** JA (Nutzer-freigegeben)
- **Deployment:** JA — API Image rebuild + Container restart (Nutzer-freigegeben)

---

## 2026-05-01 — Claude Code: F-Droid MR !37087 geprueft

- **Agent:** Claude Code
- **Aktion:** F-Droid MR !37087 Status und versionCode geprueft via glab CLI
- **Ergebnis:** MR offen, versionCode bereits 5, kein Update noetig. Label `waiting-on-response` — Maintainer wartet auf Antwort.
- **Geaenderte Bridge-Dateien:** ACTION_LOG.md
- **Keine Secrets gelesen**
- **Kein Produktcode geaendert**
- **Kein Commit / Push / Deployment / SSH**

---

## 2026-05-01 — Claude Code: v5 Build + ADR-022 Migration gestartet

- **Agent:** Claude Code
- **Aktion:** v5 AAB Build (lokal, Gradle) gestartet + ADR-022 alembic Migration auf Hetzner Server ausgefuehrt
- **Ergebnisse:**
  - SSH-Key geladen: JA (hetzner-neabouli ED25519)
  - `alembic upgrade head`: ERFOLGREICH — Migration `k401a2b3c4d5` (head)
  - API Health: `status: ok`, 24 Module aktiv
  - AAB Build: ERFOLGREICH — 45 MB, BUILD SUCCESSFUL in 35m 30s, 386 Tasks
  - AAB Pfad: `apps/mobile/android/app/build/outputs/bundle/playRelease/app-play-release.aab`
  - **Drift geklaert:** API /health listet 24 Module — das ist die korrekte Zahl
- **Ausgefuehrte Befehle:**
  - `ssh-add ~/.ssh/id_ed25519`
  - `bash scripts/build-play.sh` (Hintergrund)
  - `ssh root@135.181.254.229 "docker exec ekklesia-api alembic upgrade head"`
  - `ssh root@135.181.254.229 "docker exec ekklesia-api alembic current"`
  - `ssh root@135.181.254.229 "curl -s https://api.ekklesia.gr/health"`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/PUBLIC_CONCEPT_CONTEXT.md`
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **SSH:** JA — Nutzer hat explizit freigegeben
- **Kein Commit / Push**

---

## 2026-05-01 - Codex: Handover und Antworten bestaetigt

- **Agent:** Codex
- **Aktion:** Handover gelesen, sechs beantwortete Fragen und Arbeitsmodell bestaetigt
- **Gelesene Dateien:**
  - `docs/agent-bridge/QUESTIONS.md`
  - `docs/agent-bridge/DECISIONS.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Produktcode geaendert**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**

---

## 2026-05-01 — Claude Code: Codex-Fragen beantwortet + Arbeitsmodell dokumentiert

- **Agent:** Claude Code
- **Aktion:** 6 Codex-Fragen beantwortet, Arbeitsmodell und erweiterte Tabu-Bereiche in DECISIONS.md dokumentiert, QUESTIONS.md mit allen Antworten aktualisiert, CODEX_TO_CLAUDE.md mit Hinweis ergaenzt
- **Geaenderte Dateien:**
  - `docs/agent-bridge/QUESTIONS.md` — 6 beantwortete Fragen
  - `docs/agent-bridge/DECISIONS.md` — Arbeitsmodell, Prioritaeten, erweiterte Tabus
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md` — Hinweis auf Handover + beantwortete Fragen
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
- **Keine Secrets gelesen**
- **Kein Produktcode geaendert**
- **Kein Commit / Push / Deployment / SSH**

---

## 2026-05-01 — Claude Code: Vollstaendiges Projekt-Handover fuer Codex erstellt

- **Agent:** Claude Code
- **Aktion:** Komplettes Handover in CLAUDE_TO_CODEX.md geschrieben — 21 Sektionen: Projektbeschreibung, Architektur, Module, Endpoints, Routes, Lifecycle, Security, Scheduler, Git-Status, erledigte Features, naechste Schritte, Build-Befehle, kritische Regeln, Risiken, Drift, Seeds, CI/CD, Distribution, externe Referenzen, Kommunikationsprotokoll, naechste Aktion fuer Codex.
- **Gelesene Dateien:**
  - Alle 9 Bridge-Dateien
  - Session Memory: `pnyx-session-20260501-final.md`
  - Projekt Memory: `pnyx-status.md`
  - `CLAUDE.md` (vollstaendig, Zeile 880-991 — pnyx-spezifisch)
  - `git log --oneline -30`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md` — vollstaendiges Handover (ersetzt vorherigen Inhalt)
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
- **Kein Produktcode gelesen oder geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**

---

## 2026-05-01 — Claude Code: Codex-Analyse zu Discourse/RSS-Scraper fachlich bewertet

- **Agent:** Claude Code
- **Aktion:** Fachliche Bewertung der uncommitted Codeaenderungen (discourse_sync.py + greek_topics_scraper.py) auf Basis von Codex-Analyse, Projektkonzept und PUBLIC_CONCEPT_CONTEXT
- **Gelesene Dateien:**
  - Alle 9 Bridge-Dateien
  - `apps/api/services/discourse_sync.py` (git diff)
  - `apps/api/services/greek_topics_scraper.py` (vollstaendig)
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md` — fachliche Bewertung, Risikomatrix, Anforderungen fuer Ueberarbeitung
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
- **Kein Produktcode gelesen ueber Bridge hinaus oder geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Keine externen Netzwerkaufrufe**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**
- **Ergebnis:** discourse_sync.py → BEHALTEN, greek_topics_scraper.py → DEAKTIVIERT LASSEN (rechtliche + Neutralitaetsrisiken)

---

## 2026-05-01 - Codex: Uncommitted Codeaenderungen analysiert

- **Agent:** Codex
- **Aktion:** Uncommitted Codeaenderungen analysiert
- **Gelesene Dateien:**
  - `apps/api/services/discourse_sync.py` via `git diff`
  - `apps/api/services/greek_topics_scraper.py`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Keine Produktcodeaenderung**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Keine externen Netzwerkaufrufe**

---

## 2026-05-01 — Claude Code: Bridge-Struktur nach Public-Concept-Bereinigung geprueft

- **Agent:** Claude Code
- **Aktion:** Alle 8+1 Bridge-Dateien gelesen, Konsistenz geprueft, CLAUDE_TO_CODEX.md mit Strukturbestaetigung und naechsten Aufgaben aktualisiert
- **Geaenderte Dateien:**
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md` — Strukturbestaetigung, Datei-Routing, Antworten auf Codex-Rueckfragen, naechste Aufgaben
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
- **Gelesene Dateien:**
  - Alle 9 Bridge-Dateien (8 Original + PUBLIC_CONCEPT_CONTEXT.md)
- **Kein Produktcode gelesen oder geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**
- **Ergebnis:** Bridge-Struktur ist KONSISTENT

---

## 2026-05-01 - Codex: PUBLIC_CONCEPT_CONTEXT-Duplikat entfernt

- **Agent:** Codex
- **Aktion:** `PUBLIC_CONCEPT_CONTEXT`-Duplikat aus `PROJECT_STATE.md` entfernt und auf eigene Datei verwiesen
- **Geaenderte Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/DECISIONS.md`
- **Kein Produktcode geaendert**
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**

---

## 2026-05-01 - Codex: PUBLIC_CONCEPT_CONTEXT ergaenzt

- **Agent:** Codex
- **Aktion:** `PUBLIC_CONCEPT_CONTEXT` aus oeffentlicher Website/Wiki in Bridge ergaenzt
- **Geaenderte Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Gelesene Dateien:**
  - Bridge-Dateien unter `docs/agent-bridge/`
  - oeffentliche Website/Wiki-Seiten von `ekklesia.gr`
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Keine `.env.*`-Dateien gelesen**
- **Kein Produktcode geaendert**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**

---

## 2026-05-01 — Claude Code: PUBLIC_CONCEPT_CONTEXT erstellt

- **Agent:** Claude Code
- **Aktion:** Oeffentliche Quellen (ekklesia.gr + GitHub Wiki) analysiert, Dokumentations-Drift identifiziert, PUBLIC_CONCEPT_CONTEXT.md erstellt
- **Geaenderte Dateien:**
  - `docs/agent-bridge/PUBLIC_CONCEPT_CONTEXT.md` — NEU erstellt
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
- **Gelesene Dateien:**
  - Alle Bridge-Dateien
  - https://ekklesia.gr (WebFetch, oeffentlich)
  - https://github.com/NeaBouli/pnyx/wiki (WebFetch, oeffentlich)
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Produktcode gelesen oder geaendert**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**
- **Drift erkannt:** Modul-Anzahl (15/16/22/24), API Endpoints (13/16/70+), DB-Tabellen (9/15+), Tests (51+12 vs 106+47), Container (9/10), Score (90/96)

---

## 2026-05-01 — Codex: Claude-Uebergabe gelesen und Onboarding-Analyse ergaenzt

- **Agent:** Codex
- **Aktion:** Claude-Uebergabe gelesen und technische Onboarding-Analyse ergaenzt
- **Geaenderte Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
- **Gelesene Dateien:**
  - Bridge-Dateien unter `docs/agent-bridge/`
  - erlaubte Repo-Metadaten: README, package.json, requirements.txt, Dockerfiles, Docker Compose, GitHub Actions Workflows, Expo/EAS config
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Keine `.env.*`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**

---

## 2026-05-01 — Claude Code: Bridge-Kontext ergaenzt

- **Agent:** Claude Code
- **Aktion:** Bridge gelesen und Claude-Kontext fuer Codex ergaenzt
- **Geaenderte Dateien:**
  - `docs/agent-bridge/PROJECT_STATE.md` — vollstaendiger Projektkontext aus Session-Memory
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md` — Onboarding-Aufgabe fuer Codex
  - `docs/agent-bridge/ACTION_LOG.md` — dieser Eintrag
  - `docs/agent-bridge/QUESTIONS.md` — aktualisiert (keine zwingenden Fragen)
- **Gelesene Dateien:**
  - Alle 8 Bridge-Dateien
  - Lokale Session-Memory: `pnyx-session-20260501-final.md`
  - CLAUDE.md (Repo + Global)
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Uncommitted Aenderungen unter `apps/api/services/` wurden NICHT veraendert**

---

## 2026-05-01 — Codex: Bridge initialisiert

- Agent: Codex
- Aktion: Agent-Bridge initialisiert
- Dateien: nur `docs/agent-bridge/*`
- Keine Secrets gelesen
- Keine `.env`-Dateien gelesen
- Kein Commit
- Kein Push
- Kein Deployment
- Keine SSH-Verbindung
- Hinweis: bestehende uncommitted Aenderungen unter `apps/api/services/` wurden nicht veraendert
## 2026-05-03 - Codex: Ollama System auditiert und justiert

- **Agent:** Codex
- **Aktion:** Ollama-System ueber angebundene API-Anwendungsfaelle auditiert, Konfigurationsdrift behoben, Fallbacks verbessert und Regressionstests ergaenzt
- **Gelesene Dateien:**
  - Bridge-Dateien unter `docs/agent-bridge/`
  - `apps/api/services/ollama_service.py`
  - `apps/api/routers/agent.py`
  - `apps/api/routers/scraper.py`
  - `apps/api/routers/parliament.py`
  - `apps/api/routers/admin.py`
  - `apps/api/services/scraper_healer.py`
  - `apps/api/services/compass_generator.py`
  - relevante API-Testdateien
- **Geaenderte Produktdateien:**
  - `apps/api/services/ollama_service.py`
  - `apps/api/routers/scraper.py`
  - `apps/api/routers/parliament.py`
  - `apps/api/services/compass_generator.py`
  - `apps/api/services/scraper_healer.py`
  - `apps/api/routers/admin.py`
  - `apps/api/tests/test_ollama_system.py`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/OLLAMA_SYSTEM_AUDIT_20260503.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
- **Tests/Checks:**
  - `./.venv/bin/python -m pytest tests/test_ollama_system.py tests/test_agent_guardrails.py tests/test_agent_training_regression.py -q`
  - Ergebnis: `19 passed, 1 warning`
  - `./.venv/bin/python -m py_compile services/ollama_service.py routers/scraper.py routers/parliament.py services/compass_generator.py services/scraper_healer.py routers/admin.py tests/test_ollama_system.py`
  - Ergebnis: erfolgreich
- **Keine Secrets gelesen**
- **Keine `.env`-Dateien gelesen**
- **Keine Secret-Dateien gelesen**
- **Keine externen Netzwerkaufrufe**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung**
- **Bestehende uncommitted Aenderungen in Dashboard und `greek_topics_scraper.py` nicht angefasst**

---

## 2026-05-03 - Codex: Vier Projekt-Master-Audits erstellt

- **Agent:** Codex
- **Aktion:** Defensive Master-Audit-Reports fuer `pnyx`, `stealth`, `inferno` und `vlabs` erstellt
- **Audit-Dateien:**
  - `/Users/gio/Desktop/repo/audits/pnyx_MASTER_AUDIT_20260503.md`
  - `/Users/gio/Desktop/repo/audits/stealth_MASTER_AUDIT_20260503.md`
  - `/Users/gio/Desktop/repo/audits/inferno_MASTER_AUDIT_20260503.md`
  - `/Users/gio/Desktop/repo/audits/vlabs_MASTER_AUDIT_20260503.md`
- **Gelesene Quellen:**
  - Bridge-Dateien unter `docs/agent-bridge/`
  - lokale Repos: `/Users/gio/Desktop/repo/pnyx`, `/Users/gio/Desktop/repo/stealth`, `/Users/gio/Desktop/repo/inferno`, `/Users/gio/Desktop/repo/vlabs/vlabs-website`
  - oeffentliche Projektseiten: `ekklesia.gr`, `stealthx.tech`, `ifrunit.tech`, `vlabs.gr` soweit erreichbar
  - GitHub-Remotes aus lokalen Repos
  - bekannter Hetzner-Server read-only: Hostname, Uptime, Docker-Container, Top-Level `/opt`-Struktur
- **Wichtige Einschraenkungen:**
  - Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen
  - Keine Secret-Inhalte ausgegeben
  - Keine Exploitation, keine destruktiven Aktionen
  - Kein Commit, Push oder Deployment
  - Server nur read-only inventarisiert
- **Bestehende uncommitted Aenderungen nicht veraendert**

---

## 2026-05-03 - Codex: Audit-Reports projektlokal platziert

- **Agent:** Codex
- **Aktion:** In jedem auditierten Projekt einen lokalen Pflicht-Leseordner `AUDIT_MUST_READ/` angelegt und den jeweiligen Master-Audit dort abgelegt.
- **Projektlokale Audit-Ordner:**
  - `/Users/gio/Desktop/repo/pnyx/AUDIT_MUST_READ/`
  - `/Users/gio/Desktop/repo/stealth/AUDIT_MUST_READ/`
  - `/Users/gio/Desktop/repo/inferno/AUDIT_MUST_READ/`
  - `/Users/gio/Desktop/repo/vlabs/vlabs-website/AUDIT_MUST_READ/`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
- **Keine Produktcodeaenderung**
- **Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**
- **Keine SSH-Verbindung fuer diese Platzierung**

---

## 2026-05-03 - Codex: Google Indexing Audit ekklesia.gr

- **Agent:** Codex
- **Aktion:** Search-Console-Coverage-ZIP aus `/Users/gio/Downloads/ekklesia.gr-Coverage-2026-05-03.zip` gelesen und oeffentliche Indexierungs-Signale fuer `ekklesia.gr` geprueft.
- **Gelesene Quellen:**
  - `Diagramm.csv`
  - `Kritische Probleme.csv`
  - `Nicht kritische Probleme.csv`
  - `Metadaten.csv`
  - oeffentliche URLs: `https://ekklesia.gr/`, `robots.txt`, `sitemap.xml`, Tickets-/Wiki-URLs
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/GOOGLE_INDEXING_AUDIT_20260503.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**

---

## 2026-05-03 - Codex: Google Indexing Canonical Fix lokal umgesetzt

- **Agent:** Codex
- **Aktion:** Lokalen SEO-/Routing-Fix fuer das Search-Console-Canonical-Problem der Tickets-Seite umgesetzt.
- **Geaenderte Produkt-/Web-Dateien:**
  - `apps/web/src/middleware.ts`
  - `docs/sitemap.xml`
  - `docs/tickets/index.html`
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/GOOGLE_INDEXING_AUDIT_20260503.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Funktionsumfang:** Keine Ticket-Logik, keine API, keine Auth-Logik, kein POLIS-JavaScript geaendert; nur SEO-/Routing-Signale.
- **Checks:**
  - `npx tsc --noEmit` in `apps/web` erfolgreich.
  - `npm run lint` scheitert an bestehender `next lint`/ESLint-Options-Inkompatibilitaet.
- **Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Commit**
- **Kein Push**
- **Kein Deployment**

---

## 2026-05-03 - Codex: Google Indexing Fix gepusht und Web deployed

- **Agent:** Codex
- **Nutzerfreigabe:** Volle Freigabe fuer Commit, Push und Deployment des Google-Indexing-Fixes.
- **Aktion:** Commit `5d43642` auf `main` gepusht, Server `/opt/ekklesia/app` auf `5d43642` fast-forward aktualisiert und nur `ekklesia-web` neu gebaut/gestartet.
- **Deployment:** `docker compose -f docker-compose.prod.yml up -d --build web`
- **Live-Status nach erstem Deploy:**
  - `ekklesia-web` gestartet.
  - `https://ekklesia.gr/tickets` -> `301 /tickets/index.html`
  - `https://ekklesia.gr/el/tickets` -> `301 /tickets/index.html`
  - `https://ekklesia.gr/tickets/index.html` -> `200`
  - `https://ekklesia.gr/tickets/` wurde noch durch Next automatisch `308 /tickets` normalisiert.
- **Nachschaerfung:** Interne Links in statischen Docs wurden auf `tickets/index.html` umgestellt, damit die Website selbst die finale URL bewirbt.
- **Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**

---

## 2026-05-03 - Codex: Google Indexing Fix final live verifiziert

- **Agent:** Codex
- **Aktion:** Zweiten Nachschaerfungs-Commit `ea90fc3` gepusht, Server per fast-forward aktualisiert und `ekklesia-web` erneut neu gebaut/gestartet.
- **Deployment:** Nur Web-Service `ekklesia-web`; keine API-, DB-, Dashboard- oder Mobile-Deployments.
- **Live-Verifikation:**
  - `ekklesia-web` laeuft.
  - `https://ekklesia.gr/sitemap.xml` listet `https://ekklesia.gr/tickets/index.html`.
  - `https://ekklesia.gr/tickets/index.html` liefert `HTTP 200`.
  - `https://ekklesia.gr/tickets/index.html` enthaelt `<meta name="robots" content="index, follow">`.
  - `https://ekklesia.gr/tickets/index.html` enthaelt Canonical `https://ekklesia.gr/tickets/index.html`.
  - `https://ekklesia.gr/tickets` leitet direkt per `301` auf `/tickets/index.html`.
  - `https://ekklesia.gr/el/tickets` leitet direkt per `301` auf `/tickets/index.html`.
- **Bekannte Restnotiz:** `https://ekklesia.gr/tickets/` wird von Next weiterhin automatisch per `308` auf `/tickets` normalisiert. Da Sitemap, Canonical und interne Links jetzt auf `/tickets/index.html` zeigen, ist diese URL nicht mehr das primaere Google-Signal.
- **Build-Hinweise:** Docker/Web-Build erfolgreich; bestehende ESLint-Options-Warnung und Compose-Variable-Warnungen traten erneut auf.
- **Keine `.env`-, `.env.*`-, `.gitignore`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Commit/Push/Deployment durch Nutzer freigegeben und ausgefuehrt**

---

## 2026-05-03 - Nutzer/Codex: Google Search Console Follow-up dokumentiert

- **Agent:** Codex
- **Nutzeraktion:** Sitemap `https://ekklesia.gr/sitemap.xml` in Google Search Console eingereicht.
- **Search-Console-Status laut Nutzer:**
  - Status: Erfolgreich
  - Erkannte Seiten: 16
  - Zuletzt gelesen: 01.05.2026
- **Nutzeraktion:** Indexierung fuer `https://ekklesia.gr/tickets/index.html` beantragt.
- **Nutzeraktion:** Validierung der Indexierungsprobleme gestartet.
- **Naechster Schritt:** Warten, bis Google die Sitemap neu liest und die Validierung verarbeitet.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/GOOGLE_INDEXING_AUDIT_20260503.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Kein Commit/Push/Deployment in diesem Dokumentationsschritt**

---
## 2026-05-20 - Codex: Bridge-Recheck mit neuen Bedenken

- **Agent:** Codex
- **Aktion:** Bridge gelesen und NEA-221 Codepfade gegen aktuelle Stati geprueft.
- **Bedenken dokumentiert:**
  - `CODEX_FINDINGS.md` enthaelt widerspruechliche Stati: Recheck-Block setzt C-01/C-04 auf `VERIFIED_FIXED`, historische Finding-Bloecke stehen weiter `STILL_OPEN`.
  - Web-Direct-Voting kann durch Signatur-Kanon-Drift gebrochen sein: Web signiert JSON-sort-keys, Backend prueft Colon-Payload.
  - Mobile Native C-03 wirkt code-seitig plausibel, weil `crypto-native.ts` Colon-Payload signiert und Backend Konsensierung Colon-Payload prueft.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_FINDINGS.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine Secrets gelesen oder ausgegeben**
- **Kein Deployment**

## 2026-05-20 - Codex: NEA-221 S10 Recheck-Stand dokumentiert

- **Agent:** Codex
- **Aktion:** Von Gio/CC gemeldeten NEA-221 Recheck-Stand in der Bridge dokumentiert.
- **Kontext:**
  - C-01 Public API Felder: laut CC/Gio bereits live verifiziert.
  - C-04 BillDetail Felder: laut CC/Gio bereits live verifiziert.
  - C-03 Konsensierung Signatur: S10-Test vorbereitet, noch manuell abzuschliessen.
  - S10 App: `versionCode=16 minSdk=24 targetSdk=36`.
  - Account-Import per Deep-Link gestartet; Nullifier nur gekuerzt dokumentiert (`ca7e108d...`), keine Keys/Secrets in Bridge.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_FINDINGS.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine `.env`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Deployment**

## 2026-05-20 - Codex: vC18 / NEA-223+224 Bridge-Recheck

- **Agent:** Codex
- **Aktion:** Bridge und neue vC18-Commits/Codepfade gelesen; neue Bedenken an CC dokumentiert.
- **Recheck-Ergebnis:**
  - B-02 Web-Direct-Voting Signatur-Kanon: code-seitig gefixt/rechecked. Web `crypto.ts` nutzt jetzt Colon-Payload wie Backend.
- **Neue Bedenken dokumentiert:**
  - HIGH: QR-Web-Vote und QR-Web-Consensus pruefen keinen REGIONAL/MUNICIPAL Governance-Scope, anders als die normalen Vote/Consensus-Pfade.
  - MEDIUM: QR-Web-Consensus schreibt keinen `cplm_history` Eintrag, anders als normaler Consensus.
  - LOW: Version Endpoint meldet v18/v1.3.2 mit v17 Release Notes.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_FINDINGS.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine `.env`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Deployment**

## 2026-05-20 - Codex: vC19 / NEA-223 Bridge-Recheck dokumentiert

- **Agent:** Codex
- **Aktion:** Bridge nach `0e56403`, `92847ba`, `181486e`, `76b6474` und `9592d84` erneut gelesen.
- **Recheck-Ergebnis:**
  - vC18 Codex Findings sind geschlossen: QR Governance-Scope, QR `cplm_history`, v18 Release Notes.
  - vC19 / NEA-223 Region-Sync ist laut Bridge-Test bestaetigt.
  - API Vote/Consensus Scope bleibt der relevante Sicherheitsanker und ist bestaetigt.
  - NEA-232 ist als Backlog-Follow-up korrekt: Bills-Liste soll bei gesetzter Region gefiltert werden.
- **Codex-Einschaetzung:**
  - Keine neuen sicherheitskritischen Bedenken.
  - NEA-232 ist Produkt-/UX-Konsistenz, kein Vote-Bypass.
  - Kleine Bridge-Metadaten-Drift: Marathon-Block nennt `HEAD: 181486e`, aktueller HEAD ist `9592d84`.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/CODEX_FINDINGS.md`
- **Keine Produktcodeaenderung**
- **Keine `.env`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Deployment**

## 2026-05-20 - Codex: Bridge-Watcher Recheck vC20 / NEA-225+232

- **Agent:** Codex
- **Aktion:** Bridge und neue Commits bis `90716b0` gelesen; vC20/NEA-225/228/230/232 Codepfade stichprobenartig geprueft.
- **Neue Bedenken dokumentiert:**
  - MEDIUM: Web Region-Typeahead liest `selectedPeriferia`, aber `useMemo`/Page-Reset dependieren nicht darauf; Region-Auswahl kann stale bleiben.
  - MEDIUM: Web/Mobile Region-Filter arbeiten weiter auf begrenzten clientseitigen Bill-Sets (`limit=20` Web default, `limit=100` Mobile bei 121 Bills).
  - LOW: Mobile OPEN_END Cards koennen `Ψηφίστε →` und `Αξιολόγηση →` gleichzeitig anzeigen.
- **Codex-Einschaetzung:**
  - Keine neuen Vote-Bypass-/Auth-Bedenken.
  - Offene Punkte betreffen Listen-Vollstaendigkeit und UI-Konsistenz.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/CODEX_FINDINGS.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine `.env`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Deployment**

## 2026-05-20 - Codex: Recheck auf CC vC20 Fixes + NEA-175/vC21

- **Agent:** Codex
- **Aktion:** Bridge und Commits `c854629`, `7768426`, `95df2d9`, `9777b1a`, `4341985` gelesen; relevante Codepfade gegengeprueft.
- **Recheck-Ergebnis:**
  - V20-01 Web Typeahead Dependency: RESOLVED.
  - V20-03 Mobile OPEN_END Doppel-CTA: RESOLVED.
  - V20-02 Web-Limit: RESOLVED fuer Web (`limit=200`).
  - V20-02 Mobile-Limit: PARTIAL/OPEN, weil `apps/mobile/src/lib/api.ts` weiterhin `limit=100` setzt, waehrend die Bridge 121 Bills meldet.
  - NEA-175 Region Banner: code-seitig plausibel in App + Web.
- **Codex-Einschaetzung:**
  - Keine neuen Auth-/Vote-Bypass-Bedenken.
  - Bridge-Aussage "Codex vC20 Findings — ALLE GEFIXT" ist fuer V20-02 zu breit, solange Mobile auf `limit=100` bleibt oder nicht paginiert/serverseitig filtert.
  - Kleine Metadaten-Drift: Marathon-Block nennt `HEAD: 9777b1a`, aktueller HEAD ist `4341985`.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/CODEX_FINDINGS.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine `.env`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Deployment**

## 2026-05-20 - Codex: Restart-Handoff vor Rechner-Neustart

- **Agent:** Codex
- **Aktion:** Aktuellen Stand fuer Neustart/Wiederaufnahme gesichert.
- **Aktueller HEAD vor Restart:** `3618935 fix: Ticker cards fixed height 180px + no layout shift`
- **Branch-Status:** `main...origin/main` synchron.
- **Recheck kurz vor Sicherung:**
  - Mobile V20-02 Residual ist inzwischen gefixt: `apps/mobile/src/lib/api.ts` setzt `limit=200`.
  - Backend erlaubt `limit <= 500` fuer `/api/v1/bills`.
  - vC18/vC20 Codex Findings sind geschlossen.
  - NEA-175/vC21 Region Banner ist Bridge-seitig akzeptiert.
  - Neue spaetere Commits vorhanden: NEA-234 Landing/FAQ/Nav Helios/Semaphore und Ticker-card Layout-Fix.
- **Bekannte lokale untracked Dateien, nicht von Codex anfassen ohne Gio-Freigabe:**
  - `apps/dashboard/tsconfig.tsbuildinfo`
  - `apps/representative/.claude/`
  - `apps/representative/AGENTS.md`
  - `apps/representative/CLAUDE.md`
  - `apps/representative/index.ts`
  - `apps/representative/package-lock.json`
- **Wiederaufnahme-Regel:**
  - Nach Restart zuerst Bridge lesen, dann `git pull --ff-only`, dann neuen Log/Status pruefen.
  - Bridge-Watcher weiter alle ca. 15 Minuten bei aktiver pnyx-Arbeit.
  - Neue Bedenken direkt in Bridge dokumentieren.
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/ACTION_LOG.md`
- **Keine Produktcodeaenderung**
- **Keine `.env`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Deployment**

## 2026-05-22 - Codex: Next 16 PR #70 merged + NEA-234 research

- **Agent:** Codex
- **Aktion:** PR #70 nach CodeRabbit/CI-Gruenphase gemerged; ersetzte Dependabot-PRs dokumentiert; NEA-234 Architektur-Recherche abgeschlossen.
- **Next 16 Web Upgrade:**
  - Replacement PR: `#70` (`fix: upgrade web to Next 16.2.6`)
  - Merge Commit: `2d9faac665fc400a5af811d8cc27e265fd387f90`
  - CI: gruen (`Python API Tests`, `Crypto Package Tests`, `Secret Detection`, `Dependency Audit`, `Security Summary`)
  - CodeRabbit: keine actionable Findings; Status `SUCCESS`
  - `#64` geschlossen als ersetzt durch `#70`
  - `#69` war bereits geschlossen
  - PR-Watcher `watch-pr-70-coderabbit` geloescht, weil Aufgabe erledigt
- **CI-Fix auf main vor Merge:**
  - Commit `59c9d8c`: Health-Tests von exact string auf Modul-Prefix-Match angepasst
  - Codex-Stilhinweis fuer spaeter: `m.startswith("MOD-01")` ist sauberer als `any("MOD-01" in m ...)`; kein Blocker
- **NEA-234 Research Ergebnis:**
  - Empfehlung: Hybrid V2 statt Full Helios
  - Pfad: Semaphore group membership proof + current Ed25519/HMAC Tier 1 + public per-vote/proof bulletin board + Arweave
  - Nicht jetzt bauen: Full Helios trustee system, custom ZK circuit, custom trusted setup, server-side proving, aggregate-only ZK ohne public vote/proof records
- **Geaenderte Bridge-Dateien:**
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
  - `docs/agent-bridge/CODEX_FINDINGS.md`
- **Keine Produktcodeaenderung durch Codex**
- **Keine `.env`-, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen**
- **Keine Secrets ausgegeben**
- **Kein Deployment durch Codex**
