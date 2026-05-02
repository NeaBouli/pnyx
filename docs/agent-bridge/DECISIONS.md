# Decisions

## Initiale Entscheidungen

- Agenten kommunizieren ueber Markdown-Dateien im Repo.
- Der gemeinsame Kommunikations- und Informationsaustausch findet in `docs/agent-bridge/` statt.
- Nach jeder Aktion wird der Zustand aktualisiert.
- `ACTION_LOG.md` und `PROJECT_STATE.md` werden nach jeder Aktion aktualisiert.
- Secrets und Deployment sind gesperrt, solange der Nutzer nicht explizit freigibt.
- Commit, Push, Deployment, SSH und Server-Aktionen sind ohne explizite Nutzerfreigabe gesperrt.
- Bestehende uncommitted Aenderungen werden ohne explizite Nutzerfreigabe nicht angefasst.

## Public Concept Context

- `docs/agent-bridge/PUBLIC_CONCEPT_CONTEXT.md` ist die zentrale Datei fuer oeffentliche Konzeptinformationen.
- `docs/agent-bridge/PROJECT_STATE.md` verweist nur darauf.
- Derselbe Public-Concept-Kontext wird nicht doppelt gepflegt.

## Arbeitsmodell Claude Code / Codex (2026-05-01)

### Bridge-Aktualisierung
- Bridge-Dateien werden nur bei Zustandsaenderungen, Entscheidungen, Risiken und Ergebnissen aktualisiert.
- Reine Lese-/Analyseaktionen ohne Ergebnis erfordern keinen Bridge-Eintrag.
- ACTION_LOG.md wird bei jeder substanziellen Aktion aktualisiert.

### Aufgaben-Freigabe
- Externe Build-Kommandos (EAS, Deploy, Push) nur nach expliziter Nutzerfreigabe.
- Vorbereitung und Checks duerfen eigenstaendig durchgefuehrt werden.

### Codex-Rolle
- Codex darf und soll technische Risiken, Verbesserungen und Bedenken aktiv nennen.
- Strategische Entscheidungen (Architektur, Roadmap, Feature-Scope) trifft der Nutzer.
- Claude Code ist primaerer Planer; Codex ergaenzt und fuehrt aus.

### greek_topics_scraper
- Zielarchitektur: Review-/Draft-Flow (Artikel werden vorgeschlagen, nicht automatisch gepostet).
- Aktueller Status: Feature-Flag OFF, bleibt deaktiviert bis rechtliche Klaerung abgeschlossen.
- Auto-Post ist KEINE akzeptierte Loesung.

### Prioritaetsreihenfolge
1. v5 EAS Build (Play Store)
2. Dokumentations-Drift bereinigen
3. dashboard.ekklesia.gr (Admin Dashboard)

### Erweiterte Tabu-Bereiche (ohne explizite Freigabe)
Zusaetzlich zu Auth/Voting/Crypto sind folgende Bereiche gesperrt:
- Payments (Stripe)
- Newsletter (Listmonk)
- Discourse-Auto-Posting
- Deployment (alle Formen)
- Production-DB (direkte Aenderungen)
- App-Store / EAS Credentials

## Read-only Zugriff auf Projekt-Repos und Server (2026-05-01)

- Nutzerfreigabe: Codex darf grundsaetzlich lesend auf alle Repositories zum Projekt `ekklesia / pnyx` zugreifen.
- Nutzerfreigabe: Codex darf sich per SSH mit dem Hetzner-Server verbinden, sofern die Aktion read-only bleibt.
- Erlaubt sind read-only Inventarisierung, Statuschecks, Logs/Config-Struktur ohne Secret-Ausgabe, Git-Status, Containerstatus und Dokumentationsabgleich.
- Nicht erlaubt ohne separate explizite Freigabe: Schreiben, Editieren, Neustart, Migration, Deployment, Push, Commit, Merge, Release, Production-DB-Aenderung, Secret-Aenderung.
- Secret-Inhalte bleiben geschuetzt: `.env`, Tokens, Keys, Credentials, Wallet-Dateien und Produktionsdaten duerfen nicht ausgegeben oder in die Bridge kopiert werden.
- Falls ein read-only Check zufaellig sensible Werte beruehren koennte, muss Codex vorher eingrenzen oder nachfragen.

## Master Audit Prompt (2026-05-01)

- Ziel: maximal umfassender Audit-Prompt fuer ChatGPT/externen Audit-Agenten.
- Scope: gesamtes Projekt `ekklesia / pnyx`, inklusive Repo, Server read-only, Website, Wiki, Docs, Mobile, Web, API, Infra, Security, Privacy, UX/UI/Style, Farben, rechtliche und fachliche Stimmigkeit.
- Zentrale Datei: `docs/agent-bridge/MASTER_AUDIT_PROMPT.md`
- Der Audit-Agent darf nichts veraendern und muss Secrets redigieren.
- Primaere Codex-Aufgabe: den Master-Audit-Plan laufend anhand neuer Repo-Fakten, Server-Fakten, Claude-Bridge-Erkenntnisse, Nutzerangaben und Audit-Ergebnissen aktualisieren und verfeinern.
- Rollenverteilung: Codex prueft/auditiert/pflegt den Plan; Claude Code baut und fixt.
- Audit-Ergebnisse sind Rueckkopplung: Findings, geklaerte Drift, neue Risiken und Verbesserungsvorschlaege muessen in den Master-Audit-Plan einfliessen.
