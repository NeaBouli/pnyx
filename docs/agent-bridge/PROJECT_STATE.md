# Project State

## Projekt

- **Name:** pnyx / ekklesia.gr
- **Beschreibung:** Digitale Direkte Demokratie Plattform fuer Griechenland
- **Lokaler Repo-Pfad:** `/Users/gio/Desktop/repo/pnyx`
- **GitHub:** https://github.com/NeaBouli/pnyx (oeffentlich)
- **Server:** Hetzner CX43 (8 vCPU / 16 GB RAM), Helsinki (`root@135.181.254.229`), Ubuntu 24.04.4 LTS
- **Server-Zugangsdaten:** NICHT in dieser Bridge — SSH-Key erforderlich
- **Copyright:** (c) 2026 V-Labs Development (MIT License)

## Git-Status

- **Branch:** `main`
- **Lokaler HEAD:** `95b1a51` (chore(bridge): F-Droid pipeline #2552331797 GRUEN — linsui notified, awaiting merge)
- **origin/main:** `95b1a51`
- **Release Tags:** `v1.0.1-20260526`, `v1.3.2-stable-20260524`, `v1.3.3-audit-clean-20260524`, `v1.3.4-forum-fix-20260524`, `v1.3.5-20260525`
- **Rollback Tags:** `rollback-pre-zk-20260524`
- **Server repo HEAD:** `8a71cc4` (web rebuilt mit Logout Modal + Screenshots)
- **Web container:** rebuilt (ADR-010), Logout Modal + Screenshots + ekprosopos UI fix live
- **API container code:** `9363e16` (NEA-265+268+270+271+272)
- **Dashboard container code:** `1964e1f` (NEA-269+267+270+271)
- **F-Droid !38007:** Pipeline #2552331797 GRUEN (9/9). Kommentar an linsui gepostet. Wartet auf Merge.
- **APK/AAB:** vC28 / 1.0.1 lokal gebaut. S10: `versionCode=28`, `versionName=1.0.1`.
- **Tags:** `v1.0.1-20260526` → `fa6366f` (vC28 release). `v1.3.5-20260525` → `47c1494` (alt/bridge).
- **Pending:** nur linsui Merge + Play Console AAB Upload.
- **Mobile App Fixes:** Gio-requested app fixes are still pending. Known candidates: POLIS ticket creation disabled/not working, Weekly Push label validation, Compass aggregated-position toggle validation/fix, Semaphore/ZK proof onboarding compatibility wizard. vC28 was release/version consistency, not completion of the app-fix backlog.

## Uncommitted Aenderungen

- `docs/agent-bridge/CODEX_FINDINGS.md` — lokal modifiziert, nicht durch Codex angefasst
- `apps/dashboard/tsconfig.tsbuildinfo` — build artifact
- `apps/representative/.claude/`, `AGENTS.md`, `CLAUDE.md`, `index.ts`, `package-lock.json` — Crash-Reste/untracked, nicht durch Codex anfassen ohne Gio-Freigabe

## Architektur / Stack

| Komponente | Technologie |
|---|---|
| API | Python FastAPI + Alembic + PostgreSQL + Redis |
| Web | Next.js 14 (App Router, i18n el/en, Tailwind, recharts) |
| Mobile | Expo / React Native (versionCode 28 / versionName 1.0.1, S10 verifiziert, AAB bereit fuer Play Upload) |
| Representative | Expo / React Native WebView (versionCode 2 / v1.1.0, APK bereit) |
| Crypto | Python + PyNaCl (Ed25519, Nullifier, HLR) |
| DB | PostgreSQL, 9+ Tabellen, 3 Enums, Alembic Migrations |
| Infra | Docker Compose (11+ Container), Traefik, Brevo Newsletter |
| Forum | Discourse (pnyx.ekklesia.gr), Sync alle 10min |
| Monitor | 3-tier self-healing (T1 API, T2 Docker restart, T3 Telegram) |

## Server-Deployment (Hetzner)

- **Container:** 11+ aktiv (api, web, db, redis, traefik, dashboard, monitor, docker-proxy, discourse, discourse-db, listmonk)
- **Scheduler Jobs:** 8 aktiv
- **AUTO_RECOVERY_T2:** true
- **Monitor:** 15 Rules, 3-tier recovery
- **Snapshot:** `ekklesia-gr-2026-04-21-stable`

## Completed this cycle (Session 24.05.2026) — 15 Commits

- ekprosopos UI fix: sticky header, badge inset, evaluation score overlap, 0% progress empty-state (`3633d69`, live after static pull)
- NEA-269: Dashboard /gov Demo-Daten entfernt + /users Revocation UX privacy-korrekt (`08994b0`, push-freigegeben; nicht als deployed markiert)
- NEA-270: Admin Logs Endpoint/Sicherheitsmodell analysiert (Analyse only, kein Produktcode)
- NEA-268: org_label auf parliament_bills + Forum [Φορέας X] Titel deployed (`3e965de`, 64 org_label backfilled, unknown labels 0)
- NEA-265 Follow-up: duplicate Discourse title Search-Miss Retry mit ADA-Suffix (`49d5780`)
- Branch Protection: required checks aktualisiert auf `Python API Tests` und `Crypto Package Tests`
- Forum Resync: 268/272 Topics aktualisiert; 4 residual (2× 429, 2× 422), kein Blocker
- NEA-267: SEO/GEO/KI — llms.txt enriched, robots.txt AI crawlers, JSON-LD on zk-voting + representative
- NEA-266b: Forum bad summary cleanup — 249 pill_el nulled, _is_bad_summary() guard
- NEA-266: Forum Diavgeia topic titles + region prefix [Βουλή]/[Περιφέρεια]/[Δήμος]/[Φορέας] + metadata
- NEA-265: Forum alert spam — duplicate Discourse title handling (search + link)
- NEA-264: npm audit remediation — 0 high (dashboard Next 16, web PWA fork, mobile xmldom)
- NEA-263: Newsletter → Telegram cross-publish (non-blocking, Brevo subject)
- NEA-261: Newsletter preview fix (ADMIN_KEY missing in dashboard container)
- PR #67: recharts 3.8.1 merged (Dependabot squash)
- App screenshots: landing page download section (4 screens, responsive)
- Dependabot alerts enabled
- 4 stable/rollback tags created

## Completed previous cycle (Session 21-23.05.2026)

- Full security audit (NEA-251..258): 2 HIGH + 5 MEDIUM all resolved
- Watcher 3-tier self-healing (NEA-241): live + T2 active
- ZK V2 ADR (NEA-249): blocked on mobile prover
- Dashboard: /politicians + /monitor + /newsletter-admin (21 pages total)
- Newsletter: Brevo compose + preview + draft + send
- Forum SSO: ADR-only (NEA-260)
- Alembic schema baseline ADR (NEA-256)
- Politician Evaluation (NEA-189/191): DB + API + Mobile + ekprosopos
- NEA-186b: periferia_id FK mapping + role-based bill visibility
- NEA-250: Evaluation region-locking

## Open / Backlog

- NEA-249: ZK V2 — BLOCKED, Mopro feasibility needed
- NEA-260: Forum SSO V1 — ADR, Discourse API investigation needed
- NEA-258: FORUM_SSO_SALT startup check (LOW)
- NEA-256: Alembic schema baseline repair migrations (ADR written, no DB changes)
- NEA-65: Off-site backup — waiting for first donation
- AAB vC28 Upload zu Play Console (BEREIT)
- F-Droid MR !38007 — wartet auf linsui Review

## Architecture Decisions (ADRs)

- docs/adr/NEA-249-zk-voting-v2-semaphore-hybrid.md
- docs/adr/NEA-256-alembic-schema-baseline.md
- docs/adr/NEA-260-seamless-forum-sso.md
- docs/adr/NEA-261-newsletter-compose-listmonk-vs-brevo.md

## Sicherheitsprinzipien

- Telefonnummer: sofort nach Nullifier-Generierung geloescht
- Private Key: einmalig zurueckgegeben, nie gespeichert
- Ed25519: Public Key auf Server, Private Key nur im Geraet
- Compass-Daten: 100% clientseitig, AES-256-GCM, nie auf Server

## Bekannte Risiken

- axios muss >= 1.14.0 bleiben (Supply-Chain-Audit)
- `.env.production` liegt im Repo-Root (gitignored)
- `arweave-wallet.json` liegt im Repo-Root — Secret, NICHT lesen
- `npm ci` statt `npm install`, `ignore-scripts=true` in .npmrc
- `packages/crypto/keypair.py` ueberschattet `apps/api/keypair.py` im Docker Python-Path
- APK und AAB koennen NICHT parallel gebaut werden (gleicher android/ Ordner)

## Tracking

- **Linear:** https://linear.app/neabouli/project/ekklesiagr-pnyx-76223f68c92f
- **Bridge:** Einziger CC-Codex Kommunikationskanal
