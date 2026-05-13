# TODO — Ekklesia.gr / pnyx

## Aktiv / In Progress
- [ ] NEA-72: Hermes Phase 1 — qwen2.5:14b installiert, Architektur TBD
- [ ] AAB Upload zu Play Console (vC7 mit Scroll-Fix)

## Blocked
- [ ] NEA-59: F-Droid MR !38007 — wartet auf linsui Review
- [ ] NEA-65: Off-Site Backup — nach erster Spende
- [ ] NEA-73: Embed-System — Low Prio

## Done (Session 13.05.2026)
- [x] Server CX33 → CX43 Upgrade
- [x] Server Redeploy (199b7ea → 590dd9a)
- [x] NEA-110: bill_lifecycle tz-bug fix (494 errors)
- [x] NEA-111: Parliament Scraper DB Upsert
- [x] Diavgeia Session Rollback Fix
- [x] Docker Build Cache Prune (22.6 GB frei)
- [x] qwen2.5:14b Ollama Pull (9 GB)
- [x] APK auf Server deployen
- [x] AAB neu bauen (Scroll-Fix)
- [x] Redis Error-Counter resetten

## Hermes Entscheidungen (offen)
- Architektur: 3 separate Python-Services vs. monolithischer Agent?
- LLM Routing: 3b für einfache, 14b für komplexe Fragen?
- Telegram Bot Gateway: eigener Container oder in API integriert?
- KB Auto-Analyse: Chatbot-Logs auswerten, KB-Vorschläge generieren?
