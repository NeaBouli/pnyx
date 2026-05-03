# pnyx / ekklesia.gr — Master Audit

- **Datum:** 2026-05-03
- **Auditor:** Codex
- **Scope:** lokales Repo `/Users/gio/Desktop/repo/pnyx`, GitHub `NeaBouli/pnyx`, Bridge-Dokumente, Website/Wiki `https://ekklesia.gr`, bekannte API-/Server-Komponenten read-only
- **Server read-only:** `hetzner-NeaBouli-cx33`, Docker-Inventar ohne Secret-Ausgabe
- **Nicht gelesen:** `.env`, `.env.*`, `.gitignore`, Keys, Wallets, Keystores, Dumps, Secret-Dateien
- **Keine Aktionen:** kein Commit, kein Push, kein Deployment, keine Datenbankänderung

## Executive Summary

Ekklesia ist ein fortgeschrittenes Monorepo mit FastAPI, Next.js, Expo, Dashboard, Crypto-Package, Docker/Traefik/Listmonk/Ollama und umfangreicher Doku. Der Funktionsumfang ist hoch, aber die Projektreife leidet unter Dokumentationsdrift, Admin-Auth-Altlasten, teils divergierenden Website-/Wiki-/README-Zahlen und mehreren UI/API-Kollisionen. Die jüngsten Chat/RAG- und Ollama-Fixes sind lokal dokumentiert und getestet. Der nächste harte Sicherheitsblock ist Admin-Authentifizierung und das Entfernen von Query-Admin-Keys aus Dashboard/Web.

## Geprüfte Quellen

- Lokal: `README.md`, `apps/api`, `apps/web`, `apps/dashboard`, `apps/mobile`, `packages/crypto`, `infra/docker`, `docs/wiki`, `wiki`, `docs/agent-bridge`
- Öffentlich: `https://ekklesia.gr`, `https://ekklesia.gr/wiki/`, `https://github.com/NeaBouli/pnyx`
- Server read-only: Docker-Containerliste und `/opt`-Top-Level-Struktur

## Aktueller lokaler Status

```text
## main...origin/main
 M docs/agent-bridge/ACTION_LOG.md
?? apps/api/services/greek_topics_scraper.py
```

`greek_topics_scraper.py` ist laut Bridge fachlich gesperrt/untracked und bleibt bis rechtlicher Klärung deaktiviert.

## Architektur

- API: FastAPI, SQLAlchemy asyncio, Alembic, PostgreSQL, Redis, APScheduler, PyNaCl, Argon2, Stripe, Ollama/DeepL.
- Web: Next.js 14, React, next-intl, Tailwind, public static docs under `docs/`.
- Dashboard: Next.js, NextAuth/GitHub, admin API calls.
- Mobile: Expo/React Native Android, SecureStore, Ed25519, notifications.
- Infra: Docker Compose lokal/produktiv, Traefik, Redis, PostgreSQL, Ollama, Listmonk, Discourse, Plausible.
- Server: `ekklesia-api`, `ekklesia-dashboard`, `ekklesia-web`, `ekklesia-ollama`, `vlabs-web`, `plausible`, `listmonk`, `traefik-central`, Discourse `app`, `ekklesia-db`, Redis.

## Critical Findings

### PNYX-CRIT-01 — Admin keys still flow through URLs

**Evidence:** `apps/dashboard/src/lib/api.ts` constructs `?admin_key=...`; several dashboard pages call admin endpoints with query parameters. API dependency still accepts deprecated query auth.

**Risk:** Query strings leak through browser history, reverse proxies, logs, analytics, referrers and screenshots. This is especially risky because dashboard and admin endpoints can affect bills, scraping, text fetch, compass generation and operational state.

**Recommendation:** Move all admin auth to server-side session/Bearer only. Dashboard API routes should proxy to API with server-side secrets, never expose `NEXT_PUBLIC_ADMIN_KEY`. Disable `admin_key` query fallback in production after a short migration window.

### PNYX-CRIT-02 — Public web/admin legacy panel still accepts typed admin key

**Evidence:** `apps/web/src/app/[locale]/admin/page.tsx` stores user-entered admin key in frontend state and calls admin endpoints.

**Risk:** Duplicate admin surfaces increase attack and maintenance surface. The dashboard has GitHub auth; the public web admin page is a drift source.

**Recommendation:** Remove or gate public web admin route in production. Consolidate all admin work into `dashboard.ekklesia.gr` with server-side auth and role checks.

### PNYX-HIGH-01 — `votes-timeline` masks real DB/API failures

**Evidence:** `apps/api/routers/analytics.py` catches all exceptions and returns an empty timeline with note "Keine Daten".

**Risk:** Real database, enum, timezone or query errors become invisible. Dashboard and audits can falsely report healthy zero-data state.

**Recommendation:** Catch known empty-data cases explicitly. Log unexpected exceptions with Sentry context and return 500 or a structured degraded status.

### PNYX-HIGH-02 — Documentation drift is material

**Evidence:** README states 22 modules, 70+ endpoints, 9 containers, 106 API tests, 47 crypto tests. Bridge/server state mentions 24 modules and 11 containers. Older docs/website/wiki mention other counts.

**Risk:** Developer onboarding, public claims, compliance posture and user trust drift. Automated agents may implement against stale numbers.

**Recommendation:** Add generated `PROJECT_FACTS.md` from code/health endpoints; publish only generated counts. Mark public docs as `PUBLIC_DOCS` until repo/server confirms.

### PNYX-HIGH-03 — Secret-bearing files exist locally and must stay excluded

**Evidence from filename-only scan:** `.env.production`, `arweave-wallet.json`, app `.env`, mobile keystores, `keystore-play.properties`, debug keystores exist locally. Contents were not read.

**Risk:** Accidental reads, prompt leakage, or commits would be high impact.

**Recommendation:** Keep hard deny rules in Bridge; add repo-level pre-commit scanning; ensure `git ls-files` never contains real secrets. Consider moving production secrets outside repo tree.

## Medium Findings

### PNYX-MED-01 — Ollama and Chat/RAG fixes need live deployment verification

**Evidence:** Bridge reports local fixes and tests: Chat/RAG `11 passed`; Ollama audit `19 passed`. No live post-deploy verification by Codex in this run.

**Risk:** Production may still serve old unsafe/incorrect behavior until deployed and KB seeded.

**Recommendation:** Claude Code should deploy API only, run KB seed, and rerun the 25 landing-chat regression questions live.

### PNYX-MED-02 — Dashboard logs page says backend endpoint missing, but backend endpoint exists

**Evidence:** Dashboard logs page text says `POST /admin/logs/explain` backend endpoint does not exist. API has `/api/v1/admin/logs/explain`.

**Risk:** UI disables a capability that exists; operators lose diagnostic function.

**Recommendation:** Wire dashboard logs action to the existing endpoint after admin-auth hardening.

### PNYX-MED-03 — `greek_topics_scraper.py` remains untracked and conceptually unresolved

**Evidence:** Local status and Bridge.

**Risk:** Scheduler/import behavior can drift; legal/neutrality risk if autoposting news into civic forum.

**Recommendation:** Keep disabled. Convert to moderation queue/Draft Review with source allowlist, copyright policy, rate limits, and human approval.

### PNYX-MED-04 — Static docs use extensive `innerHTML`

**Evidence:** `docs/index.html`, `docs/community.html`, `docs/tickets/polis.js`, wiki pages.

**Risk:** Some assignments use controlled translations, but mixed dynamic content increases XSS review burden.

**Recommendation:** Use `textContent` for text, DOM builders for links/cards, and a small sanitizer if HTML rendering is unavoidable.

### PNYX-MED-05 — Package ID drift

**Evidence:** Bridge notes Android code uses `ekklesia.gr`, F-Droid metadata/checklist references `gr.ekklesia.app`.

**Risk:** Store publication, update channel, F-Droid MR and Play listing mismatch.

**Recommendation:** Define canonical package ID and update all metadata/checklists before next app distribution step.

## Low / Quality Findings

- README has mojibake in copyright line and architecture tree characters.
- README claims auto-deploy, while Bridge says deploy workflow is manually dispatched.
- `apps/web` README is still generic Next.js starter-style.
- Some operational docs mention old statuses; mark resolved/open.
- Public docs should state gov.gr OAuth as deferred/gated, not active.

## Security Recommendations

1. Remove admin query auth from production.
2. Create a dashboard backend proxy that injects API admin auth server-side.
3. Add Sentry coverage for broad-except endpoints.
4. Run `git-secrets` or equivalent on full history before public releases.
5. Add CSP for static docs and landing chat.
6. Add E2E tests for dashboard admin pages against a mocked API.
7. Keep `greek_topics_scraper.py` out of deployment until reviewed.

## Functional Test Recommendations

- API: `cd apps/api && ./.venv/bin/python -m pytest tests/ -q`
- Chat/RAG: rerun `LANDING_CHAT_TRAINING_DATA_20260502.jsonl` live after deploy.
- Web: `cd apps/web && npm run build && npm run lint`
- Dashboard: `cd apps/dashboard && npm run build && npm run lint`
- Mobile: verify package ID, versionCode and Play/F-Droid metadata.

## Handover For Developers

Start with:

1. Admin auth cleanup.
2. Dashboard/API endpoint wiring mismatches.
3. Documentation generated facts.
4. Live Chat/RAG and Ollama regression.
5. `greek_topics_scraper` review flow design.

