# TODO — Ekklesia.gr / pnyx

## Aktiv / In Progress
- [ ] NEA-72: Hermes Phase 1 — qwen2.5:14b installiert, Architektur TBD
- [ ] NEA-189b: Region-Locking fuer Evaluation (Buerger Region = Politiker Region)
- [ ] AAB vC25 Upload zu Play Console (`~/Desktop/ekklesia-v1.3.2-vC25-PLAY.aab` BEREIT)

## Done (Session 21.05.2026) — 22 Commits
- [x] NEA-236: Health-Check 15 Rules deployed + Cronjob 06:00 UTC
- [x] NEA-189: Politician Evaluation Grundgeruest (DB + API + Mobile + ekprosopos)
- [x] NEA-191: Liquid Evaluation (my-evaluation, pre-fill, badge, updated_at trigger)
- [x] NEA-240: Alle 5 Codex Findings gefixt (region, eval persist, scraper, forum, keypair)
- [x] NEA-240 Follow-up: ADA Constraint verifiziert (11-14, passt in 10-32)
- [x] MOD-25: Status live in modules.html + /health + /health/modules
- [x] MPScreen Politikoi-Tab zeigt live Politiker-Liste statt Placeholder
- [x] HTTP 500 Fix: keypair.py verify_signature ValueError
- [x] Trailing Slash Fix: /politicians/ (307 redirect)
- [x] ekprosopos Login: invite_code Feld + native bridge
- [x] Arweave Monitor: nur PARLIAMENT Bills
- [x] vC25 APK auf S10 + Server download live
- [x] vC25 AAB Play Console uploaded
- [x] ekprosopos vC2 APK gebaut + deployed

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
