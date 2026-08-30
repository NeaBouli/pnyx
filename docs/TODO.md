# Ekklesia.gr — TODO
# Copyright (c) 2026 V-Labs Development — MIT License

Last reconciled: 2026-08-30

`docs/STATUS.md` is the authority for the current release. GitHub issues and
Linear are the authorities for active work. Older session notes are retained
below only as historical context; their unchecked boxes are not current tasks.

## Current gates

- [x] Merge bounded web lifecycle/lint fixes in PR #259 (`54ff2fc`): 40 tests,
  typecheck and build pass; 19 warnings removed without rule suppression.
- [x] Roll out PR #259 with PR #263 as the approved Web component release at
  `c935018` on 2026-08-30, with rollback images and live verification.
- [x] GH#258: add 29 SSO lifecycle tests, fix stale/duplicate session work and
  remove the final initialization warning without suppression. Web 69 tests,
  lint, typecheck, build and audit pass; Kimi review and Sol browser validation
  complete. Server signatures, nonce consumption and eligibility are unchanged.
- [x] Include GH#258 in the reversible Web rollout with live verification.
  See `docs/operations/forum-sso-lifecycle.md`.
- [ ] Complete one new voluntary smartphone login/logout canary for this Web
  rollout. Existing technical checks do not impersonate a verified citizen.
- [x] Confirm send-only owner intent and implement external newsletter reply
  routing (PR #262), keeping Brevo senders, lists, DOI and schedules unchanged.
- [x] Deploy only the five PR #262 mail files over API baseline `25d6c14` and
  verify operator-recipient configuration, runtime hashes and health. No domain
  inbox, Null MX or provider change. See `docs/operations/WEB_MAIL_RELEASE_2026-08-30.md`.
- [ ] Controlled real mail delivery and header verification remain separately
  gated; no campaign was sent as a rollout smoke test.
- [x] GH#261 read-only inventory: confirmed consent and campaign audience are
  disconnected; three of four Redis confirmations are absent from Brevo.
  No provider/contact writes. See `docs/operations/newsletter-delivery-audit.md`.
- [ ] GH#261 repair: review consent, preferences and suppression precedence,
  approve a no-write reconciliation manifest, then separately authorize any
  bounded provider writes and controlled test recipient. Do not bulk-import,
  resubscribe, replace list ownership or infer consent from missing records.

- [x] Merge and test signed personal-read preparation (PR #257, `9ec3591`).
- [ ] Complete GH#253 in stages: verify API
  readiness, release the compatible app, observe both read/write adoption,
  perform an explicitly approved reversible cutoff, then retire legacy code.
  Passing code tests alone does not close this release gate.
- [ ] Replace the transitive `ecdsa` path only with a compatible verified
  upstream release. Keep the existing explicit audit exception visible; no
  new suppression, forced dependency override or Arweave migration.
- [ ] Reconsider TypeScript 7 only after official support by the installed
  typescript-eslint tooling and all workspace checks.
- [ ] Separately triage retained Linear backlog NEA-262, NEA-185, NEA-167 and
  NEA-113 against its full acceptance scope; do not mark future features Done
  merely because related V1 functionality exists.

- [x] Web, Dashboard, Mobile, Representative and shared crypto verification
  added to pull-request CI.
- [x] Citizen and Representative Android bundles exported locally.
- [x] Android v1.0.29 published as direct APK, Google Play Closed Testing build
  and official F-Droid package.
- [x] Monthly Brevo newsletter implemented and scheduled for the first day of
  each month at 09:00 scheduler time (Linear `NEA-160` is superseded by this
  implementation state; end-to-end subscriber delivery remains GH#261).
- [x] Donation intake is PII-free, donations-only and fail-closed.
- [x] Public donation links and public wallet/account identifiers removed.
- [x] GitHub PR checks and merge for the 2026-07-12 readiness block (#131,
  `a99a12b`).
- [ ] Legal recipient, donation/tax/document policy and sandbox E2E approval.
- [ ] Google Play production-access tester/time requirement (external gate).
- [ ] Complete the DMARC observation window and collect representative evidence
  for every active sending path before proposing an enforcement policy. The
  private report catalog and sender inventory exist; review may begin on
  2026-09-01 but must wait for delayed reports covering 2026-08-31. Owner intent
  is send-only; reply routing is deployed, actual delivery evidence is pending (Linear
  `NEA-422`; no DNS change authorized).
- [x] Reconcile the production Docker/containerd image inventory without prune,
  image deletion or daemon restart; retain a recurrence check after future
  daemon restarts (GitHub #211).
- [x] Update Discourse from `v2026.8.0-latest` to the official patch tag
  `v2026.8.0-latest.1` with verified backups, rollback image and forum/topic/
  bill-sync acceptance checks (GitHub #215).
- [x] Restore the missing live DiscourseConnect configuration under separate
  owner authorization and verify the signed Discourse-to-API-to-verification
  chain, nonce TTL/consumption, forum services and protected logout route
  (GitHub #82 and #215).
- [x] Complete one voluntary real-citizen login/logout canary for GitHub #82 and
  #215 (confirmed by the owner on 2026-08-24).
- [ ] Replace the reviewed local `image-size` security backport only after an
  upstream Metro-compatible patched release exists; keep Dependabot #78-#81
  visible until then.
- [ ] Public iOS build and future release hardening. Android signing and the
  current controlled Android distribution are complete; device canaries remain
  release-specific verification work.
- [ ] Execute only the synthetic Phase-1 evidence tasks for the parallel Ekklesia
  Platform V2/Minima track (GitHub #217-#219; tracked by epic #216). GH#220-#223
  remain blocked until their documented identity, federation, repository,
  parity, migration and rollout gates pass. V1 remains the production baseline;
  no V2 repository, real identity/vote integration or rollout is permitted
  before its documented gates pass.

V2 architecture: `docs/architecture/EKKLESIA_V2_MINIMA.md`.

See `docs/SOFTWARE_READINESS_2026-07-12.md` for the current matrix. Older
session notes below are historical and must not be used as current HEAD status.

---

## Historical session notes — originated 2026-04-13

The remainder of this file preserves the pre-launch Session 3 notes together
with a few later completion annotations. It is not an operational checklist and
must be revalidated against `docs/STATUS.md`, GitHub and Linear before any item
is scheduled.

### Former session start flow

> **Lies das hier zuerst, bevor du irgendetwas änderst.**

```
1. git log --oneline -5              → Prüfe HEAD (sollte d7b09f4 sein)
2. git status                        → Muss sauber sein
3. git tag -l "pre-session*"         → Rollback-Punkte prüfen
4. Lies CLAUDE.md                    → Projekt-Kontext, Stack, Architektur
5. Lies docs/STATUS.md               → Aktueller Modulstatus, Tests, Known Issues
6. Lies docs/HANDOVER-SESSION3.md    → Was zuletzt gemacht wurde
7. Lies DIESE DATEI (docs/TODO.md)   → Was als nächstes ansteht
8. cd apps/web && npx vitest run     → Tests müssen 29/29 grün sein
9. cd apps/api && .venv/bin/python -m pytest tests/ -v  → 51+16xfail
```

**Rollback:** `git reset --hard pre-session4-20260413` bringt dich auf `d7b09f4`.

**npm install:** Braucht `--legacy-peer-deps` wegen eslint Peer-Conflict.

**Deploy-Workflow:** `.github/workflows/deploy.yml` ist absichtlich deaktiviert
(nur `workflow_dispatch`). NICHT den `push`-Trigger wieder einfügen bevor
Hetzner-Secrets gesetzt sind.

**Prinzipien:**
- Modular, smart, light
- Datenschutz = höchste Priorität (Daten sind unser höchstes Gut)
- Kryptosicherheit wahren (Ed25519, AES-256-GCM, Nullifier)
- Keine Kollisions-gefährlichen Änderungen (DB-Schema, Infra) ohne Absprache
- Jeden Schritt dokumentieren (TODO, HANDOVER, STATUS, README, Wiki, Landing)

---

### Former pre-launch critical list

### Infrastruktur
- [ ] Docker Compose lokal starten + `alembic upgrade head`
- [ ] Seed-Scripts: `seed.py` (38 Thesen) + `seed_real_bills.py` (10 Bills + 304 Positionen)
- [ ] E2E Test: Verify → VAA (38 Fragen) → Compass-Seed → Vote → Compass-Update → Results

### Web
- [ ] Compass Engine Unit Tests (vitest) — engine.ts Berechnungen
- [x] Next.js 16 Upgrade
- [ ] Secure Storage Hardening (localStorage → httpOnly Cookie)

### Mobile
- [ ] iOS + Android Build (Expo EAS)
- [ ] Compass auf Mobile portieren (useCompass → expo-secure-store)
- [ ] Shared Types: `packages/types/` für Web + Mobile

### Landing Page
- [x] App-Download-Buttons deaktiviert (2026-04-09) — alle 4 (App Store, Android, Google Play, F-Droid) auf "Σύντομα/Coming soon"
- [x] App-Buttons für Direct APK, Google Play Closed Testing und F-Droid reaktiviert
- [x] F-Droid-Metadaten gemergt und APK v1.0.29 / vC584 publiziert

---

### Former pre-public-beta list

### Plattform
- [ ] Hetzner CX21 + Traefik + Let's Encrypt SSL
- [ ] Production Docker Compose
- [ ] GitHub Secrets setzen: `HETZNER_HOST`, `HETZNER_USER`, `HETZNER_SSH_KEY`
- [ ] `/opt/ekklesia` auf Server anlegen + initial `git clone`
- [ ] Deploy-Workflow reaktivieren: `push: branches: [main]` in `deploy.yml` (aktuell nur `workflow_dispatch`)
- [ ] Domain ekklesia.gr → Hetzner
- [ ] CORS für Prod-Domain
- [ ] Externes Sicherheitsaudit
- [ ] `image-size`-Backport ablösen, sobald ein gepflegtes, Metro-kompatibles
      Release beide dokumentierten GHSAs behebt und vollständige Repository-CI
      sowie Security Audit bestehen; Dependabot `#78`–`#81` bis dahin offen und
      sichtbar halten

### Features
- [ ] VAA auf Mobile portieren
- [ ] Wiki Ticker → echte API-Daten
- [ ] MOD-16 Municipal Governance — Router-Implementierung
- [ ] WebSocket Live-Counter (WINDOW_24H Bills)

### Smart Notifications & Content Delivery (MOD-17)
Prinzip: Minimaler Datenverkehr, maximale User-Kontrolle, Privacy-by-Design.

**Benachrichtigungen:**
- [ ] Kategorie-Filter (Βουλή, Δήμος, VAA, Compass) + Ton pro Kategorie
- [ ] Templates lokal auf Gerät gespeichert
- [ ] Server sendet nur Ping (Topic-basiert), keine Inhalte im Push

**Content Delivery (User wählt Modus):**
- [ ] Manuell: Headline → bewusster Download
- [ ] Automatisch: Gesetze + Abstimmungen auto-laden
- [ ] Headline-Only: Überschriften, Download bei Interesse

**Technik:**
- [ ] `expo-notifications` (FCM/APNs)
- [ ] NotificationPreferences + ContentDeliveryMode Screens
- [ ] Lokaler Cache (expo-file-system), Badge-Counter

### Partei-Synchronisation (nach Server-Migration)
- [ ] L1: Parlaments-Scraper (hellenicparliament.gr → Auto-Update Positionen)
- [ ] L2: Admin-Review Panel
- [ ] L3: Community "Position veraltet?" Flagging
- [ ] `party_position_history` DB-Table
- [ ] Automatische Partei-Erkennung (ΥΠΕΣ Register)
- [ ] KI Programm-Analyse → Human Review

---

### Historical V2 / Alpha ideas

- [ ] packages/crypto-rs (Rust + WASM)
- [ ] Commit-Reveal ZK Abstimmung
- [ ] MOD-08 TrueRepublic Bridge
- [ ] MOD-09 gov.gr OAuth2.0
- [ ] MOD-10/11 KI-Scraper
- [ ] MOD-13 Mein Abgeordneter
- [ ] Deliberation (pol.is-Modell)

---

### Historical completed work

### Session 3 (2026-04-09/10) — 15 Commits
- [x] Rollback: `pre-session3-20260409`, `pre-session4-20260413`
- [x] 9 doppelte Headers entfernt
- [x] Tailwind 4 PostCSS Migration
- [x] Mobile Ed25519 Signing + Nullifier `:` Bug Fix
- [x] 12 Cross-Platform Krypto-Tests
- [x] VAA: 15 → 38 Thesen (304 Parteipositionen)
- [x] Liquid Compass: 4 Modelle, AES-256-GCM, 100% clientseitig
- [x] MOD-17 Smart Notifications spezifiziert
- [x] App-Buttons deaktiviert + F-Droid hinzugefügt
- [x] Deploy-Workflow deaktiviert (fehlende Hetzner-Secrets)
- [x] STATUS, HANDOVER, README, Wiki, Landing, FAQ aktualisiert

### Session 2 (2026-04-07) — Dependencies
- [x] 10 Dependabot PRs, TS 6.0 Fixes

### Session 1 (2026-03-29) — Foundation
- [x] Monorepo, CI/CD, 13 Router, 9 Tabellen, 5 Web-Seiten

---

*Historical notes originated 2026-04-13 at HEAD `d7b09f4`; later completion
annotations may appear. Rollback: `pre-session4-20260413`.*
