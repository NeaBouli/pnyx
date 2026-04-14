# Ausstehende Major Upgrades

> Erstellt: 2026-04-14 | Alle PRs geschlossen mit Verweis auf diese Datei.

## Pnyx

| PR | Package | Von | Zu | Aufwand | Priorität |
|----|---------|-----|----|---------|-----------|
| #22 | redis (Python) | 5.0.8 | 7.4.0 | Mittel | 2 |
| #28 | next | 14.2.35 | 16.2.3 | Gross | 5 |
| #30 | eslint-config-next | 14.2.35 | 16.2.3 | Gross | 5 |

## Migrationsreihenfolge

1. **#22 — Redis 7** — MITTEL
   - Async API-Änderungen, Connection-Pool Breaking Changes
   - `apps/api/` betroffen — alle Redis-Calls prüfen
   - Separat testbar, kein Frontend-Impact

2. **#28 + #30 — Next.js 16 + eslint-config-next 16** — GROSS
   - Erfordert React 19 (concurrent features, use() Hook)
   - App Router Änderungen, Middleware-API Updates
   - eslint-config-next 16 hängt von Next.js 16 ab → zusammen migrieren
   - Gesamtes Frontend (`apps/web/`) betroffen
   - Eigene Session einplanen

## Hinweise

- Dependabot wird diese PRs erneut öffnen — ggf. `ignore` Regeln in `.github/dependabot.yml` setzen
- Vor jeder Migration: lokalen Branch erstellen, vollständige Testsuite durchlaufen
