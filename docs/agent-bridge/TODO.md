# TODO — Ekklesia.gr / pnyx

## Aktiv / In Progress
- [ ] NEA-272: POLIS Tickets in Mobile wirklich funktionsfaehig machen. Code-Sichtung: Browser/static POLIS existiert teilweise (`docs/tickets/*`, GitHub-Issue Backend in `polis.js`), QR-Auth existiert (`apps/api/routers/polis_qr.py`, `PolisLoginScreen.tsx`), aber Mobile `TicketsScreen.tsx` liest nur Issues und blockiert Create/Vote mit Phase-B Modal. Diagnose zuerst: Browser-Flow live end-to-end testen (QR-Session, Mobile-Auth, Ticket-Create, Vote/Reactions), dann Mobile sauber an bestehenden Flow/API anschliessen oder fehlende Backend-Endpoints bauen.
- [ ] NEA-272a: POLIS QR-Login Lokalisierung fixen. `docs/tickets/index.html` enthaelt hardcoded Deutsch im QR-Button/Modal (`Login mit App`, `Scanne den QR-Code...`, `Laden...`, `Warte auf App-Scan...`, `Abbrechen`). Muss EL default + EN Umschaltung wie restliche Seite nutzen.
- [ ] NEA-272b: POLIS Auth-Modell klaeren. GitHub Login ist fuer GitHub-Issue Ticket-Create/Reactions/Comments/Claim gedacht; QR/App Login verifiziert den Buerger im Browser. Fuer vC29 Option C entscheiden/reporten: beide Pfade behalten (QR + GitHub OAuth) oder spaeter API-Proxy bauen, der GitHub-Account-Pflicht entfernt.
- [ ] NEA-272c: Stale Desktop Phase-B Guard entfernen/ersetzen. `docs/tickets/index.html` ueberschreibt auf Desktop `.btn-new-ticket` und zeigt immer `phaseBModal`, selbst nach GitHub Login und QR/App-Verifikation. Fix: keine pauschale Desktop-Sperre; echte Auth-State-Checks verwenden.
- [ ] NEA-272d: QR-auth UX continuation fix. Nach GitHub+QR bleibt Browser unveraendert und Ticket-Form oeffnet nicht; App-Erfolgsscreen laesst sich nicht zuverlaessig schliessen. Fix: Web pending action + sichtbarer QR-verified state + nach QR Erfolg direkt `openNewTicketModal()`; Mobile `PolisLoginScreen` Close per safe reset/navigate to Tabs statt fragilem `goBack()`.
- [ ] NEA-272e: REJECTED by Gio as product solution. Browser redirect from Mobile is only a stopgap/debug build, not acceptable final behavior.
- [ ] NEA-272f: App-internal POLIS required. Verified app user must create/vote tickets inside Mobile. Basis exists: `apps/api/crypto/polis.py` validates signed ticket/vote payloads; `apps/mobile/src/lib/crypto-native.ts` derives persistent POLIS key. Missing: API endpoints, mobile signed payload builders, create form/vote action, DB or server-side GitHub proxy decision.
- [ ] NEA-272f Mobile Implementation Prompt sent to CC: replace GitHub Issues/browser redirect in `TicketsScreen.tsx` with app-internal `/api/v1/polis/*` flow. Add TS canonical register/ticket/vote signing helpers in `crypto-native.ts`, API methods in `api.ts`, create modal + up/down vote actions in `TicketsScreen.tsx`. No version bump/release until S10 test.
- [ ] NEA-272f Review Blocker: Backend commit `8b0e503` must NOT deploy until fixed. Findings: no verified identity binding for `pk_polis` (CRITICAL), unsigned ticket title (HIGH), tests are not real endpoint/DB tests (MEDIUM), DB IntegrityError/uniqueness races unhandled (MEDIUM).
- [ ] NEA-272f Re-Review Blocker: Fix commit `495a506` still must NOT deploy. `_verify_identity(nullifier_hash)` only checks ACTIVE nullifier, but does not bind identity to `pk_polis` or request. Need registered `pk_polis` mapping or identity-key signature over POLIS key/request. Real FastAPI/DB endpoint tests still missing.
- [ ] NEA-272f Re-Review Blocker: Commit `def7807` has correct Option A architecture, but still must NOT deploy. Remaining: `build_ticket_signed_bytes(... title_hash=\"\")` still has silent empty-title fallback, and real FastAPI/DB endpoint tests for register-key/create/vote are still missing.
- [ ] NEA-272f Re-Review Blocker: Commit `112adf5` fixes strict title signing, but still must NOT deploy. `bc7a8c7` argues xfail is project-standard, but Codex does not accept that as deploy evidence for this new security-sensitive DB flow. Need real non-xfail FastAPI/DB tests or disposable server/test-DB verification before production migration/deploy.
- [ ] NEA-272f Re-Review Blocker: Commit `106e892` adds useful non-xfail crypto/message-format tests, but still does NOT test FastAPI endpoints, DB behavior, `register_polis_key()`, `_verify_registered_key()`, `create_ticket()`, `vote_ticket()`, inserts, commits, or 409 paths. Still no production deploy/migration until router/DB-behavior tests or isolated disposable test-DB/server verification exists.
- [ ] NEA-272f Re-Review Follow-up: Commit `d96f93a` finally adds real router/DB tests with FastAPI + SQLite override. Good direction, but add remaining router/DB edge tests before deploy: same `pk_polis` different nullifier -> 409, wrong nullifier/key pair -> 403, duplicate vote/IntegrityError -> 409, and GET safe fields after a real inserted ticket.
- [ ] NEA-272f Re-Review Follow-up: Commit `b0d3ad2` adds the missing edge-test names, but two tests are still too loose. Fix wrong-pair test to require exact `KEY_MISMATCH` by registering `nh_wrong` with another `pk_polis`; fix duplicate-vote IntegrityError path by voting twice with same `pk_polis`/ticket but different `vote_nullifier`, expecting exact `409 DUPLICATE_VOTE`.
- [ ] NEA-272f Backend Deploy Gate: Commit `ab2a24c` clears Codex test-coverage review for backend (15/15 router/DB tests reported green; exact KEY_MISMATCH and DB unique duplicate vote now covered). Next step is controlled backend deploy/migration + server verification only after Gio approval; no public mobile release steps yet.
- [ ] NEA-272f Mobile Review Blocker: Commit `b30d38c` removes browser/GitHub redirect and uses backend POLIS API, but must NOT go to APK/deploy yet. Fix `@noble/curves/ed25519` imports to `@noble/curves/ed25519.js`; replace random `ticket_nullifier`/`vote_nullifier` with deterministic domain-separated nullifiers; add demo-mode POLIS guard. Then rerun `cd apps/mobile && npx tsc --noEmit` and report exact output.
- [ ] NEA-272f Integration Test Gate: Commit `505979c` resolves Codex mobile blockers (POLIS import path + deterministic nullifiers). Next step: controlled backend deploy/migrations + debug APK install on S10 only. No version bump, no public APK/Landingpage, no AAB/Play/F-Droid. Verify create/vote/self-vote/duplicate flows in-app.
- [ ] NEA-272f Full Interactive Verification: Gio reports S10 flow appears functional. CC must verify S10 app + API/browser + DB + API logs end-to-end, including ticket_id, DB rows, self-vote block, duplicate block, no stack traces, and no secret/full-nullifier/signature leakage. No public release steps.
- [ ] NEA-272f Remaining Error-Path Gate: `8e5e220` verifies create/register/API safe fields/DB/logs clean, but self-vote and duplicate-ticket S10 checks are still open. Must pass before marking POLIS done or releasing vC29/public APK.
- [ ] NEA-273: Mobile Compass Toggle Gesamtposition validieren/fixen. Erst Screen/Codepfad finden, dann S10 Debug-Test, nur reproduzierten Bug fixen.
- [ ] NEA-274: Mobile/ekprosopos Region-Filter Audit. National/regional/municipal/institutional Sichtbarkeit pruefen, S10-Test dokumentieren.
- [ ] NEA-275: vC29 Release Gate. Jeder App-Fix einzeln bauen und auf S10 testen. Keine neue public APK auf Landingpage, kein Play Upload, kein F-Droid Metadata Update, bis Gio alle Fixes abgenommen hat.
- [ ] Weekly Push/Digest Label: Linear free issue limit blockiert neues Ticket; vorerst unter NEA-275 getrackt. Exakten Screen/String finden, S10 validieren, ggf. fixen.
- [ ] ZK/Semaphore Wizard: Linear free issue limit blockiert neues Ticket; Kommentar auf NEA-249 + NEA-275. Nur Onboarding/Kompatibilitaetscheck, keine echten Proofs. NEA-249 bleibt fuer echte Mobile-Prover blocked.
- [ ] F-Droid MR !38007: Pipeline #2554446253 GRUEN (9/9) on fdroiddata commit `e72a2f44b`; root cause fixed by applying Expo `buildFromSource` to `package.json` (not `app.json`). Wartet auf linsui review/merge.
- [ ] F-Droid !38007 linsui feedback follow-up: `local-maven-repo` scanignore removal is on remote fdroiddata (`fe2040f7c`, count 0), but pipeline #2554315583 FAILED. Fix rewritemeta final blank line and build failure by following `templates/build-react-native.yml` (`expo.autolinking.android.buildFromSource`) instead of re-adding local Maven scanignore. Metadata-only; no pnyx app code/version/tag/APK/AAB changes.
- [ ] F-Droid !38007 pipeline #2554339926 follow-up: `buildFromSource` added, but `fdroid rewritemeta` failed because the long `node -e` prebuild command must be formatted as F-Droid rewritemeta wants (folded multi-line YAML). Apply rewritemeta/job diff, rerun pipeline. Metadata-only.
- [ ] F-Droid !38007 pipeline #2554363927 BLOCKER: fdroiddata commit `b12a50f17` emptied `metadata/ekklesia.gr.yml` (`80 deletions`), pipeline failed schema/lint/tools. Restore metadata from `18f01ab9c` or last full valid version, reapply only minimal rewritemeta-compatible buildFromSource command, verify YAML object and no `local-maven-repo`, rerun pipeline.
- [ ] F-Droid !38007 pipeline #2554378282 follow-up: metadata restored and schema/lint/tools pass, but `fdroid rewritemeta` still failed. Apply rewritemeta formatting for the long `python3 -c` prebuild command exactly, rerun pipeline. Metadata-only.
- [ ] F-Droid !38007 pipeline #2554402995 FAILED: rewritemeta/schema/lint/checkupdates/tools are green, but `fdroid build` fails because Gradle cannot resolve Expo local Maven artifacts (`expo-asset`, `expo-crypto`, `expo-device`, `expo-file-system`, etc.) after local Maven scanignore removal. Do not re-add local Maven scanignore; follow `templates/build-react-native.yml` so Expo local Maven artifacts are generated/available in the correct F-Droid phase. Metadata-only; no pnyx app code/tags/version/APK/AAB/Play/landingpage changes.
- [ ] F-Droid !38007 pipeline #2554421176 FAILED: sed/rewrite-meta formatting is green, but `fdroid build` still fails with the same missing Expo local Maven artifacts. The sed buildFromSource change did not make local Maven repos available to Gradle. Next attempt must compare against `templates/build-react-native.yml` and a working RN/Expo metadata example, then fix the F-Droid phase/buildFromSource behavior. Do not re-add local Maven scanignore. Metadata-only.
- [x] F-Droid !38007 fix applied: `e72a2f44b` changes sed target from `app.json` to `package.json`, because `expo-modules-autolinking` reads `expo.autolinking.android.buildFromSource` from `package.json`. Pipeline #2554446253 green 9/9 (`fdroid build` + `check apk` success).
- [ ] AAB vC28 Upload zu Play Console (lokal gebaut, `app-play-release.aab`)
- [ ] NEA-258: FORUM_SSO_SALT Startup-Check (LOW follow-up)
- [ ] CLAUDE.md Aktualisierung (INFO — stale CX33, 22 Module, Next 14)

## Blocked
- [ ] NEA-249: ZK Voting V2 — BLOCKED (mobile prover unresolved, ADR geschrieben)
- [ ] NEA-249 Follow-up: Mopro native Expo Module feasibility plan

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
