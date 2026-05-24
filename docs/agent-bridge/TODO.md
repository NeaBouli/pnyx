# TODO — Ekklesia.gr / pnyx

## Aktiv / In Progress
- [ ] NEA-258: FORUM_SSO_SALT Startup-Check (LOW follow-up)
- [ ] README/CLAUDE.md Aktualisierung (INFO — stale Next 14, CX33, 22 Module)
- [ ] AAB vC27 Upload zu Play Console (`~/Desktop/ekklesia-v1.3.2-vC27-PLAY.aab` BEREIT)

## Blocked
- [ ] NEA-249: ZK Voting V2 — BLOCKED (mobile prover unresolved, ADR geschrieben)
- [ ] NEA-249 Follow-up: Mopro native Expo Module feasibility plan

## Done (Session 24.05.2026)
- [x] NEA-266: Forum Diavgeia topic titles + region prefix + metadata
- [x] NEA-265: Forum alert spam — duplicate title search + link
- [x] NEA-264: npm audit remediation — ALL 0 high (dashboard next 16, web PWA fork, mobile xmldom)
- [x] PR #67: recharts 3.8.1 merged (Dependabot, squash)
- [x] NEA-261: Newsletter Preview Fix (ADMIN_KEY missing + error handling)
- [x] NEA-263: Newsletter → Telegram cross-publish (non-blocking, Brevo subject)
- [x] Dashboard ADMIN_KEY injection fix
- [x] App Screenshots on Landing Page (4 screens, responsive)
- [x] Dependabot alerts enabled
- [x] Release Tag v1.3.2-stable-20260524 + v1.3.3-audit-clean-20260524

## Done (Session 23.05.2026)
- [x] NEA-251: Discourse SSO callback signed (HIGH) — `272f73a`
- [x] NEA-252: Municipal vote Ed25519 signature (HIGH) — `1bc3b39`
- [x] NEA-253: Relevance signal Ed25519 signature (MEDIUM) — `4ce07e6`
- [x] NEA-254: Receipt + Compass signed POST, GET deprecated (MEDIUM) — `73952cc`
- [x] NEA-255: Finance endpoints admin auth (MEDIUM) — `1ff0394`
- [x] NEA-256: Alembic schema baseline ADR (docs only) — `217ee97`
- [x] NEA-257: CI security audit hard-fail (MEDIUM) — `8ccf2ac`
- [x] NEA-242: Audit log (3 commits + 2 Codex rechecks + HOTFIX metadata reserved)
- [x] NEA-243: Discourse update 2026.5.0-latest.1 (CVE-2026-42945)
- [x] NEA-186b: periferia_id FK mapping + invite pipeline
- [x] NEA-250: Evaluation region-locking
- [x] NEA-249: ADR + Phase 0 STOP + Docs Helios→Semaphore
- [x] PR #70: Next.js 16 merged + #64/#69 closed
- [x] CI fix: health module tests prefix match
- [x] HOTFIX: API crash loop (AuditLog metadata reserved)
- [x] HOTFIX: Monitor DNS internal URL
- [x] Audit A: Website (31 pages, all 200 OK)
- [x] Audit B: Code Security (7 findings, all resolved)

## Done (Session 22.05.2026)
- [x] NEA-249: ADR geschrieben — Semaphore Hybrid V2, blocked (mobile prover)
- [x] NEA-249: Phase 0 Spike STOP — snarkjs/Mopro/RN inkompatibel
- [x] NEA-222: Server-side Wahlbezirk-Filter (parliament.py periferia_id/dimos_id)
- [x] NEA-188: votes-timeline DEMO filter + inline fix (500 bug)
- [x] NEA-247: Web stale vote display fix + Mobile ResultScreen fromVote
- [x] NEA-248: QR modal ESC key
- [x] NEA-229+227: Roadmap dedup MOD-25 + FAQ JSON-LD
- [x] NEA-246: Dashboard /politicians + /monitor + Diavgeia filter
- [x] NEA-190: SEO (robots.txt, sitemap +3, JSON-LD, OG tags)
- [x] NEA-186: Rep role-based bill visibility + org_label auto-detection
- [x] NEA-186 Hotfix 1+2: Codex audit — visibility helper, divergence gate, docstring
- [x] NEA-231+235: Forum content fallback + resync 185/187 topics
- [x] NEA-241: Watcher 3-tier auto-recovery (T1+T2+T3) + docker-socket-proxy
- [x] NEA-239+224: Community.html live counters + DEMO filtered
- [x] Lifecycle stuck alert cooldown per bill_id
- [x] CI fix: health module tests prefix match
- [x] PR #70: Next.js 16 upgrade branch (rebased, wartet auf merge)
- [x] vC26+vC27 APK+AAB gebaut + deployed
- [x] Global Kohaerenz: 25 Module everywhere
- [x] T2 AUTO_RECOVERY_T2=true aktiviert

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
