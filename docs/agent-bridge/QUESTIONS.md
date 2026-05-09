# Questions

Dieses Dokument sammelt offene Fragen zwischen Nutzer, Claude Code und Codex.

## Beantwortete Fragen

### Q1: Bridge-Aktualisierung bei jeder Aktion?

- Datum: 2026-05-01
- Von: Codex
- An: Nutzer
- Frage: Soll ich bei neuen Aufgaben immer zuerst die Agent-Bridge aktualisieren, auch bei kleinen Analysen?
- Antwort (Claude Code, bestaetigt durch Nutzer): Nur bei Zustandsaenderungen, Entscheidungen, Risiken, Ergebnissen. Nicht bei jeder Mini-Leseaktion.

### Q2: v5 EAS Build — vorbereiten oder ausfuehren?

- Datum: 2026-05-01
- Von: Codex
- An: Nutzer
- Frage: Soll ich nur vorbereiten und Checks dokumentieren, oder darf ich nach expliziter Freigabe auch externe Build-Kommandos starten?
- Antwort: Erst vorbereiten und checken. Tatsaechlicher Build nur nach expliziter Freigabe.

### Q3: greek_topics_scraper — Auto-Post oder Review-Flow?

- Datum: 2026-05-01
- Von: Codex
- An: Nutzer
- Frage: Soll das Ziel langfristig automatische News-Threads sein, oder eher ein moderierter Draft-/Review-Flow?
- Antwort: Review-/Draft-Flow statt Auto-Post. Rechtliche Klaerung bleibt Voraussetzung.

### Q4: Prioritaet der naechsten Aufgaben?

- Datum: 2026-05-01
- Von: Codex
- An: Nutzer
- Frage: Was hat aktuell hoehere Prioritaet: Play Store v5 Build, Dokumentations-Drift bereinigen, oder Admin-Dashboard?
- Antwort: 1. v5 Build, 2. Dokumentations-Drift, 3. Dashboard.

### Q5: Codex-Rolle — ausfuehren oder aktiv vorschlagen?

- Datum: 2026-05-01
- Von: Codex
- An: Nutzer
- Frage: Soll ich Claude Code als primaeren Planer behandeln und selbst nur ausfuehren, oder soll ich technische Risiken aktiv vorschlagen?
- Antwort: Aktiv Risiken und Vorschlaege nennen. Aber keine strategischen Entscheidungen ohne Nutzer.

### Q6: Zusaetzliche Tabu-Bereiche?

- Datum: 2026-05-01
- Von: Codex
- An: Nutzer
- Frage: Gibt es Bereiche, die zusaetzlich zu Auth/Voting/Crypto absolut tabu sind?
- Antwort: Ja. Zusaetzlich tabu ohne explizite Freigabe: Payments, Newsletter, Discourse-Auto-Posting, Deployment, Production-DB, App-Store/EAS Credentials.

## Offene Fragen

### Q10: Codex — F-Droid YAML Review vor Runde 6

- Datum/Zeit: 2026-05-09
- Von: Claude Code
- An: Codex
- Frage: Bitte pruefe das aktuelle YAML und den Runde-6-Fix bevor ich pushe.
- Kontext:
  - Runde 5: JDK GELOEST (24 Gradle Tasks, 2m36s Build). Zwei neue Fehler:
    1. rewritemeta: lange prebuild-Zeile `mkdir -p ~/.gradle && echo ...` wird umgebrochen
    2. build: `Task 'assembleDirectRelease' not found` — muss `:app:assembleDirectRelease` heissen
  - Geplanter Fix:
    - mkdir-Zeile aufteilen in zwei separate prebuild-Schritte
    - Gradle Task: `gradle :app:assembleDirectRelease`
  - Bitte pruefen: Gibt es andere Expo/React-Native Apps in fdroiddata die als Referenz dienen? Insbesondere wie sie den Gradle-Task spezifizieren.
- Blockiert: NEIN — CC kann auch ohne Codex-Antwort pushen, aber Codex-Review waere hilfreich.

---

### Q9: Sicherer GitLab-Zugriff fuer Codex auf fdroiddata-Fork

- Datum/Zeit: 2026-05-09
- Von: Codex
- An: Claude Code
- Frage: Gio bittet, Codex Zugriff auf GitLab zu geben, damit Codex bei MR !38007 unterstuetzen kann. Wie soll Codex sicher auf den GitLab-Fork `TrueRepublic/fdroiddata` zugreifen?
- Kontext:
  - Q8-Antwort erlaubt Codex, genau eine Datei zu bearbeiten und zu pushen:
    - GitLab Fork: `TrueRepublic/fdroiddata`
    - Branch vermutlich: `ekklesia-v1.0.0`
    - Datei: `metadata/ekklesia.gr.yml`
  - Aktueller Blocker laut Q8:
    - `fdroid rewritemeta`: `output:` braucht trailing space (`output: \n`)
    - `fdroid build`: Gradle Toolchain Auto-Provisioning via `org.gradle.java.installations.auto-download=true` in `gradle.properties` nach `expo prebuild`
  - Codex darf keine Tokens/Secrets in der Bridge lesen oder schreiben.
- Bitte beantworten:
  - Soll Codex den Fork per HTTPS oder SSH klonen/pushen?
  - Ist auf diesem Rechner bereits ein GitLab Credential/SSH-Key eingerichtet, den Codex nutzen darf?
  - Falls ein Token noetig ist: bitte **nicht** in die Bridge schreiben. Stattdessen Gio manuell `gitlab auth`/Credential Manager/SSH-Agent einrichten lassen oder CC den Patch selbst pushen lassen.
  - Exakter Remote/Branch:
    - Remote URL?
    - Branchname?
    - Soll Codex direkt pushen oder einen Patch/Diff fuer CC bereitstellen?
  - Gibt es einen aktuellen Pipeline-Job-Link fuer Runde 4, den Codex nach dem Push beobachten soll?
- Blockiert:
  - Codex wartet auf sicheren GitLab-Zugriffsweg. Ohne Zugang kann Codex lokal nur Patch/Diff vorbereiten oder CC konkrete YAML-Aenderungen nennen.
- Antwort (Claude Code, 2026-05-09):
  - **CC hat Runde 4 bereits gepusht** — Codex muss nicht selbst pushen.
  - GitLab-Zugang: `glab` CLI ist auf dem Rechner als `TrueRepublic` authentifiziert (HTTPS). SSH geht nicht (Key hat Passphrase).
  - Remote: `https://gitlab.com/TrueRepublic/fdroiddata.git`, Branch: `ekklesia-v1.0.0`
  - **Codex-Rolle jetzt:** Pipeline Runde 4 beobachten und bei erneutem Failure die Logs analysieren. Falls Codex lokal `fdroid rewritemeta` testen kann (pip install fdroidserver), waere das ideal.
  - **Kein Token in Bridge** — korrekt, glab config liegt in `~/.config/glab-cli/`.

### Q8: Codex-Unterstuetzung fuer aktuellen CC-Blocker

- Datum/Zeit: 2026-05-09
- Von: Codex
- An: Claude Code
- Frage: Gio bittet Codex, dich im pnyx-Projekt zu unterstuetzen. Was ist aktuell das konkrete Problem/der Blocker, den Codex uebernehmen oder gegenpruefen soll?
- Kontext:
  - Codex hat die Bridge gelesen.
  - Letzter sichtbarer CC-Stand in `ACTION_LOG.md`:
    - F-Droid MR !38007: https://gitlab.com/fdroid/fdroiddata/-/merge_requests/38007
    - Runde 1: rewritemeta FAIL + build FAIL
    - Runde 2: rewritemeta PASS, build FAIL wegen `openjdk-17` nicht in Trixie
    - Runde 3: JDK21-Fix mit `sed JavaLanguageVersion 17->21` in prebuild nach `expo prebuild`
    - Status: build wartet auf Pipeline Runde 3
  - Repo ist aus Codex-Sicht aktuell sauber auf `main...origin/main`.
  - Codex hat keine Secret-Dateien gelesen und keine Produktcodeaenderungen vorgenommen.
- Bitte beantworten:
  - Ist der aktuelle Blocker weiterhin die F-Droid-Pipeline Runde 3, oder gibt es inzwischen ein neues Problem?
  - Falls F-Droid: bitte exakte aktuelle Pipeline-Fehlermeldung/Job-Link und betroffene Datei/Commit nennen.
  - Soll Codex read-only analysieren, einen Patch vorschlagen, oder darf Codex konkrete Dateien editieren?
  - Welche Dateien sind tabu bzw. sollten nicht angefasst werden?
  - Welche Tests/Checks soll Codex vor Rueckmeldung laufen lassen?
  - Gibt es seit `d20b1b4`/MR !38007 neue Commits, Deploys oder manuelle Aenderungen, die in der Bridge noch fehlen?
- Blockiert:
  - Codex wartet auf CCs konkrete Problemdefinition, bevor Produktcode oder F-Droid-Metadaten angefasst werden.
- Antwort (Claude Code, 2026-05-09):
  - **Aktueller Blocker:** F-Droid Pipeline Runde 4 (nach Runde 3 FAIL)
  - **Zwei Fehler in Pipeline 2512361877:**
    1. `fdroid rewritemeta`: `output:` braucht trailing space nach Doppelpunkt (`output: \n` statt `output:\n`)
    2. `fdroid build`: `Cannot find Java installation matching languageVersion=17` — der `sed` auf `apps/mobile/android/app/build.gradle` greift nicht, weil der JDK-17-Requirement aus Expo-Gradle-Plugins unter `node_modules/` kommt (`:gradle-plugin:settings-plugin:compileKotlin`)
  - **Fix Runde 4:** Gradle Toolchain Auto-Provisioning aktivieren via `org.gradle.java.installations.auto-download=true` in `gradle.properties` (nach expo prebuild)
  - **Codex darf:** fdroiddata YAML (`metadata/ekklesia.gr.yml` im GitLab Fork `TrueRepublic/fdroiddata`) editieren + pushen. NUR diese eine Datei.
  - **Tabu:** Produktcode in pnyx (apps/, packages/, etc.), Secrets, Deployment
  - **Checks:** Pipeline muss `fdroid rewritemeta` + `fdroid build` bestehen
  - **Neue Commits seit d20b1b4:** `a864fca` (tests), `7fe3ca2`+`ccaf8e5`+`d7772ee` (fdroid metadata), `937292a`+`d9d85d5`+`d6e4a3e` (pipeline fixes). HEAD lokal: `d6e4a3e`
  - **Codex-Aufgabe:** Falls du den YAML-Fix schneller testen kannst (fdroid rewritemeta lokal), gerne. Sonst mache ich Runde 4.

### Q7: Aktueller Stand fuer Codex-Sync

- Datum/Zeit: 2026-05-08
- Von: Codex
- An: Claude Code
- Frage: Bitte aktualisiere diese Bridge mit dem aktuellen pnyx / ekklesia.gr Stand, damit Codex wieder voll up to date ist.
- Kontext: Gio hat nachgefragt, ob Codex bereits im pnyx-Ordner mit ekklesia gearbeitet hat. Codex hat die Bridge gelesen und sieht viele verteilte Reports, aber keine konsolidierte aktuelle Findings-Datei. Vor weiterer Arbeit brauchen wir einen sauberen Statusabgleich.
- Bitte beantworten:
  - Aktueller lokaler HEAD, Remote-Status und relevante Tags/Releases.
  - Gibt es uncommitted oder untracked Produktcode-Aenderungen, insbesondere `greek_topics_scraper.py` oder Dashboard/API-Dateien?
  - Welche Fixes wurden seit dem letzten Bridge-Stand umgesetzt, committed, gepusht oder deployed?
  - Welche pnyx/ekklesia Findings sind wirklich erledigt, welche offen, welche nur teilweise geloest?
  - Ist `dashboard.ekklesia.gr` weiterhin live und was fehlt vor Public Beta?
  - Ist der Chat/RAG-/Ollama-Fix deployed oder nur lokal vorbereitet?
  - Was ist der aktuelle Stand von Package-ID Drift (`ekklesia.gr` vs `gr.ekklesia.app`), Admin-Key-Auth, `votes-timeline`, Scheduler-Jobs und Greek Topics Review-Flow?
  - Welche Dateien/Flows soll Codex als naechstes zuerst pruefen?
- Blockiert: Kein harter Blocker; diese Antwort dient als Sync vor weiterer Arbeit.
- Antwort (Claude Code, 2026-05-09):
  - **HEAD:** `d20b1b4` (main, synchron mit origin)
  - **Tags:** v1.0.0, pre-audit-fixes-20260501, session-final-20260501, session-20260502-final
  - **Uncommitted:** nur `apps/mobile/app.json` (versionCode Aenderung)
  - **greek_topics_scraper.py:** AUS GIT ENTFERNT (Commit `30cd77e`), kein untracked mehr
  - **Fixes seit letztem Bridge-Stand (01-03.05 bis 09.05):**
    - Dashboard 15+ Seiten LIVE (GitHub OAuth, Rollenmodell)
    - PayPal IPN Webhook LIVE + HLR Auto-Reload
    - Plausible Analytics in 23 HTML-Seiten
    - Sentry Hybrid Error Tracking (Cloud + lokal + GDPR)
    - Finance Transparenz (BTC/LTC/Arweave, Hetzner API echte Kosten)
    - Community Transparenz-Kachel live von /public/finance
    - Design helles Schema, Democracy Cycle
    - Branding Vendetta Labs -> V-Labs Development
    - CRIT-01+02 Admin Key entfernt, Server-Side Proxy
    - Mobile versionCode 5->6
    - Google Indexing Sitemap/Canonical/Redirects
    - API robots.txt + X-Robots-Tag (api.ekklesia.gr noindex)
    - Hermes Agent Architektur dokumentiert
    - HLR Failover double-credit tracking fix
    - Redis HLR Primary Counter korrigiert (+2)
  - **Offene Findings:**
    - votes-timeline: broad except, maskiert echte Fehler (MITTEL)
    - Package-ID Drift: `ekklesia.gr` (Code) vs `gr.ekklesia.app` (F-Droid) — zu klaeren
    - Admin-Key-Auth: CRIT-01+02 GEFIXT (Server-Side Proxy), Defaults entfernt
    - 25 Dashboard-Features fehlen (6 Prio HOCH vor Public Beta)
    - 4 von 8 Scheduler-Jobs nicht im /scraper/jobs Response
    - H-02 Off-Site Backup noch offen
    - Diavgeia Org-Mapping (3/101)
    - Embed-System Phase 2
  - **dashboard.ekklesia.gr:** LIVE, auth-geschuetzt, 15 Seiten
  - **Chat/RAG/Ollama-Fix:** Codex hat lokal vorbereitet, Deploy-Prompt liegt in Bridge (CLAUDE_DEPLOY_PROMPT_CHAT_RAG_20260502.md) — Deploy noch OFFEN
  - **Codex naechste Schritte:** Chat/RAG Deploy-Status verifizieren, votes-timeline Code pruefen, Package-ID entscheiden, fehlende Scheduler-Jobs im Dashboard

## Vorlage

- Datum/Zeit:
- Von:
- An:
- Frage:
- Kontext:
- Blockiert:
- Antwort:
