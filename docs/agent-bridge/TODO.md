# TODO — Ekklesia.gr / pnyx

## Aktive Roadmap — Stand 2026-06-12

### Aktiv baubar (Reihenfolge)
1. [x] Pagination `Όλα` — GH#107 / NEA-317
   - gebaut: Mobile API `limit`/`offset`, BillsScreen lazy-load `PAGE_SIZE=10`, `Περισσότερα`
   - verifiziert: Live API liefert `offset=0/10/20` je 10 Bills; mobile tests + TSC gruen; APK gebaut und S10 installiert
   - S10-Akzeptanz: `Περισσότερα` sichtbar, Tap lädt weitere Bills, keine ANR
2. [x] Landing `Votes in Progress` — GH#108 / NEA-318
   - gebaut/deployed: aggregierter Endpoint `/api/v1/vote/results/in-progress`
   - Env-Schwelle: `VOTES_IN_PROGRESS_THRESHOLD=1` fuer Testbetrieb, spaeter auf `50` setzen
   - verifiziert: Live Endpoint liefert nur aggregierte Daten, keine Seed-Bills, Landing hat keine alten Fake-Ticker-Strings
3. [x] Analysis-Fallback — GH#103 / GH#105
   - konservativ geloest: keine KI-Analyse als Fallback ohne Review
   - Web zeigt `analysis_el` nur wenn vorhanden; sonst `Επίσημο κείμενο` / offizieller Text + PDF-/Dokumentlinks
   - qwen2.5:14b ist nicht release-tauglich (Halluzination `αθέμιτων παρόχων` bestätigt)

### Blocked / Extern (kein Bau)
- [ ] GH#102 / NEA-312 — echter `WINDOW_24H` Bill nötig
- [ ] GH#79 — F-Droid !38007 wartet auf linsui Merge
- [ ] GH#80 — Off-site Backup wartet auf Hetzner Storage Box / erste Spende
- [x] GH#81 — Android Native-Prover Self-Test auf S10 erfolgreich; produktives ZK-Voting bleibt Feature-Flag-guarded bis Backend/Arweave-Integration
- [x] NEA-286 / GH#94 — Lifecycle WINDOW_24H stuck: resolved/stale; Production 2026-06-09 ohne stuck Rows, Scheduler healthy

### Release Follow-ups
- [ ] Future Production Size/R8 Optimization — Play Console warns about size/mapping when R8 is not active.
  - Current prepared Play/direct build: vC47 / v1.0.18; R8/minify remains OFF, so no `mapping.txt` exists for this artifact.
  - Cause of size: native Semaphore/ZK prover and multi-ABI native libraries.
  - Next pass before Production (not Closed Testing): evaluate ABI restrictions and R8/ProGuard + `mapping.txt`, rebuild, install on S10, verify vote/source/ZK paths.

## Tracking: GitHub Issues #71-#83 (Linear = read-only Archiv)

## Aktiv / In Progress
- [ ] F-Droid !38007 (#79): GitLab MR !38007 offen, mergeable, Diskussionen resolved, Pipeline gruen; wartet auf linsui/F-Droid Merge
## Done (Session 25-27.05.2026)
- [x] vC29 Release Gate (#78/NEA-280): S10 Funktionstest PASS, APK live auf ekklesia.gr, AAB in Play Console hochgeladen (`5eb37cf`)
- [x] vC29 Final Build Gate: versionCode 29/versionName 1.0.2, APK+AAB gebaut, SHA lokal/live verifiziert, Release abgeschlossen
- [x] vC29 Release Gate Audit: API, Vote, Evaluation, POLIS List, ANNOUNCED Source Link, DB/API Integrity, Visual Audit und Crash-Check PASS
- [x] vC29 Blocker Order: Compass, ANNOUNCED, Region-Filter, NEA-292/NEA-273 Release-Fixes abgeschlossen
- [x] vC29 #76 Region-Filter Audit: Audit clean / nicht blockierend fuer vC29
- [x] F-Droid !38007 linsui Java 21/template feedback — fdroiddata `61af54f58` + `05a86ac05`; Java auto-download disabled, Java 21 RN patch, `expo-notifications` native excluded while JS remains resolvable, pipeline `#2564438256` green 9/9, linsui comment posted
- [x] #75 Compass Result Toggle/Layout/Pulse — `740a82b` + `f17d0ef` + `fba09cc`, S10 debug APK verified by Gio; full X/Y grid restored, tap toggles to pulsing green result point and back
- [x] F-Droid !38007 linsui follow-up direct fix — `82379b722`, old 1.0.0 build removed, `subdir: apps/mobile/android/app`, rewritemeta scalar `build: ...`, pipeline `#2555756552` green 9/9, linsui comment posted
- [x] vC29 #73 ANNOUNCED Bills Badge — `6accbd3`, filter tab `Ανακοιν.`, navigation disabled, badge existed, tsc reported 0 errors
- [x] Compass tsc Fehler fixen (`engine.ts:57-58`) — `c6fd27b`, `npx tsc --noEmit` reported 0 errors
- [x] NEA-272f: POLIS app-internal — Backend + Mobile, 15 router/DB tests, S10 verified, Self-Vote/Duplicate blockiert
- [x] NEA-265/268/269/270/271/272: alle deployed
- [x] NEA-266: README rewrite
- [x] NEA-267: SEO JSON-LD 17 Seiten
- [x] NEA-273: Compass Toggle committed (5328a42)
- [x] F-Droid Pipeline gruen (9/9), Autoupdate, linsui notified
- [x] Branch Protection, Forum Resync, org_label 192/192
- [x] GitHub Issues Migration (#71-#83)
- [x] ekprosopos UI fixes + Logout Modal + APK Manifest
- [x] F-Droid !38007 fix applied: `e72a2f44b` changes sed target from `app.json` to `package.json`, because `expo-modules-autolinking` reads `expo.autolinking.android.buildFromSource` from `package.json`. Pipeline #2554446253 green 9/9 (`fdroid build` + `check apk` success).
- [x] AAB vC29 Upload zu Play Console (lokal gebaut, `app-play-release.aab`; SHA256 `d4d72bd733fdc0a5c2e2bfb85a8fe9d309cf688308ca0d128f720e2d118a4e2e`)
- [x] NEA-258/NEA-277: FORUM_SSO_SALT Startup-Check (fail-closed vorhanden, Template + Tests ergänzt)
- [x] CLAUDE.md Aktualisierung (NEA-278 — stale CX33, 22 Module, Next 14 korrigiert)
- [x] NEA-303: Admin-Testaccount + DEMO-123 Region permanent im Code gesetzt

## Guarded Follow-ups
- [ ] GH#112 / NEA-249 Follow-up: ZK V2 Produktintegration nur nach `GH112_IMPLEMENTATION_PLAN.md`
  - [x] Gate 1: additive DB storage live (`r101a2b3c4d5`), Backup vorher, keine Tier-1-Änderung
  - [x] Gate 2: `/api/v1/zk/status` live fail-closed; `/api/v1/zk/verify` bleibt 503 solange `ZK_VOTING_ENABLED=false`
  - [x] Gate 5 prep: public receipt serializer + read-only `/api/v1/zk/receipts/{vote_scope_id}` live, aktuell leer
  - [x] Canary prep: hidden `ZK-CANARY-001` scope + exact allowlist enforcement + admin-only preflight built/tested
  - [x] Gated `/api/v1/zk/vote` receipt path live fail-closed; no tallies/Arweave while flags are off
  - [x] Mobile prep: ZK opt-in UI benötigt lokale native Fähigkeit UND Server `opt_in_enabled=true`
  - [x] Hidden operator canary path submits real S10 opt-in/vote payloads and requires verify-only mutation checks before vote
  - [x] Hidden S10 Canary passed end-to-end with vC38 (`bill:ZK-CANARY-001`); production flags returned OFF
  - [x] Production scope safety gates: canary allowlist, production allowlist, optional global rollout flag
  - [x] Tally/API policy: public results aggregate Tier-1 votes + valid ZK receipts; hidden canary remains excluded by `admin_hidden`
  - [x] Public verifier payload / Arweave publication policy: admin + flag-gated pending receipt publisher, public verifier payload only, no identity bridge fields, no canary Arweave publication
  - [x] Security review for scoped production rollout readiness (`GH112_SECURITY_REVIEW.md`)
  - [x] First public scoped ZK rollout window PASS for `bill:GR-d4c62ed4` with vC43/S10; public result `tier1=0`, `zk=1`, `total=1`; global rollout remains OFF; ZK Arweave publisher remains OFF
  - [ ] Staged/global ZK rollout follow-up: only after review of rollout policy, Arweave publication policy, and per-scope monitoring

## Done (Session 25.05.2026)
- [x] F-Droid !38007 autoupdate: `AutoUpdateMode: Version`, `UpdateCheckMode: Tags`, CurrentVersion 1.3.2/27 pushed to fdroiddata (`3d81d65c1`) + linsui comment posted
- [x] ADR-010 cleanup: ekprosopos `docker cp` hotfix replaced by clean `ekklesia-web` rebuild, container + live HTML verified
- [x] ekprosopos UI fix initial static pull: server pulled to `125d45a`; later corrected by ADR-010 clean rebuild
- [x] ekprosopos APK validation: live `/download/ekprosopos-latest.apk` matches `~/Desktop/ekprosopos-v1.1.0-vC2.apk` SHA-256 `4b9d49d888465cac2f1de94f50e46efc8dbfea49cb805fd715459bbbb28a761e`
- [x] ekprosopos APK manifest/checksum tracked in `docs/download/APK_MANIFEST.md` and `docs/download/ekprosopos-latest.apk.sha256`
- [x] ekprosopos UI fix: sticky header, badge inset, score-overlap fixed, 0%-progress empty-state (`3633d69`, pushed)
- [x] NEA-272: org_label resolve (43/43 UIDs) + backfill (168 bills), 192/192 INSTITUTIONAL have org_label (`9363e16`)
- [x] NEA-271: Dashboard /logs live container + ollama + stream endpoints deployed (`1964e1f`)
- [x] NEA-262: Forum Alerts — CANCELLED (historisch, NEA-265 hat den Bug gefixt, 0 bills ohne topic)
- [x] NEA-270: Admin Logs Hardening — Sanitization + Dashboard Button live, 12 Tests, live-verifiziert (`1fc2183`)
- [x] F-Droid !38007: Fastlane Metadaten komplett (en-US + el-GR, Screenshots, Changelogs), MR Description + Kommentar gepostet (`53c03bb`)
- [x] NEA-267: JSON-LD auf 12 neue Seiten (wiki, tickets, govgr-dimos), sitemap cleanup, votes noindex (`7fc3f26`)
- [x] NEA-266: README vollständig aktualisiert — Encoding, Versionen, Links, Features, SEO-Sektion (`221815c`)

## Done (Session 24.05.2026)
- [x] NEA-269: Dashboard /gov Demo-Daten entfernt + /users Revocation UX privacy-korrekt (`08994b0`)
- [x] NEA-270 Analyse: Admin Logs Endpoint Gap/Sicherheitsmodell analysiert (kein Produktcode)
- [x] NEA-268: org_label auf parliament_bills + Forum [Φορέας X] Titel live/deployed (`3e965de`)
- [x] NEA-265 Follow-up: Duplicate-Title Search-Miss Retry mit ADA-Suffix (`49d5780`)
- [x] Branch Protection: stale checks korrigiert auf `Python API Tests`/`Crypto Package Tests`
- [x] Forum Resync: 268/272 Topics aktualisiert, [Φορέας X] Stichproben verifiziert
- [x] NEA-267: SEO/GEO/KI — llms.txt, robots.txt AI crawlers, JSON-LD (TechArticle, WebPage)
- [x] NEA-266b: Forum bad summary cleanup — 249 pill_el nulled, _is_bad_summary() guard
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
- [x] NEA-249: ADR geschrieben — Semaphore Hybrid V2
- [x] NEA-249: Android Native-Prover auf S10 verifiziert; Produktintegration separat unter GH#112 gated
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
- [ ] GH#111 / NEA-335 follow-up: Nullifier v2 Production Activation — scaffold deployed, production preflight green, fresh identity backup exists at `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_042119`, focused endpoint regression proves same-row v1->v2 migration, Redis in-flight locking, and atomic row-locked existing-identity re-registration with mocked HLR, read-only snapshot/compare/report helper is ready with v2 invariant counters (`37 passed` focused set), and the S10 UI path to VerifyScreen is verified without mutation. Production remains v1 until an explicit operator canary with a real phone/HLR identity re-registration path is run. Admin-test identities are not sufficient. Runbook: `docs/agent-bridge/GH111_NULLIFIER_V2_CANARY_RUNBOOK.md`; design checklist: `docs/adr/ADR-004-nullifier-kdf-migration.md`.
- [ ] GH#112 / ZK V2 staged/global follow-up — first public scoped rollout passed for `bill:GR-d4c62ed4`; production ZK remains scoped by exact allowlist; global rollout and ZK Arweave publisher remain OFF pending review.
- [x] vC46 Play/direct release: AAB/APK built, hashes verified, S10 install/launch passed, verified-account state preserved, landing/API version live.
- [x] vC47 Play/direct release: AAB/APK built, hashes verified, S10 install passed, landing/API live, GitHub release live, CI/Security Audit green.

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
