# Ausstehende Major Upgrades

> Erstellt: 2026-04-14 | Alle PRs geschlossen mit Verweis auf diese Datei.
>
> Offene Dependabot-Alerts ohne bekannte Patch-Version im GitHub-Snapshot (Stand 2026-10-10): [Reachability-Assessment](operations/DEPENDENCY_ALERT_REACHABILITY_2026-10-10.md).

## Pnyx

| PR | Package | Von | Zu | Aufwand | Priorität |
|----|---------|-----|----|---------|-----------|
| #22 | redis (Python + Server) | 5.0.8 / 7 | 8.1.0 / 8.10 | Abgeschlossen | - |
| #28 | next | 14.2.35 | 16.2.3 | Gross | 5 |
| #30 | eslint-config-next | 14.2.35 | 16.2.3 | Gross | 5 |

## Migrationsreihenfolge

1. **#22 — Redis 8.10** — ABGESCHLOSSEN
   - API und Monitor verwenden redis-py 8.1.0.
   - CI und Compose testen beziehungsweise verwenden Redis 8.10.
   - RDB-Vorabsicherung und Redis-7-Rollback sind im Handover dokumentiert.

2. **#28 + #30 — Next.js 16 + eslint-config-next 16** — GROSS
   - Erfordert React 19 (concurrent features, use() Hook)
   - App Router Änderungen, Middleware-API Updates
   - eslint-config-next 16 hängt von Next.js 16 ab → zusammen migrieren
   - Gesamtes Frontend (`apps/web/`) betroffen
   - Eigene Session einplanen

## Hinweise

- Dependabot wird diese PRs erneut öffnen — ggf. `ignore` Regeln in `.github/dependabot.yml` setzen
- Vor jeder Migration: lokalen Branch erstellen, vollständige Testsuite durchlaufen
# Open Upstream Security Exception

- `PYSEC-2026-1325` affects `ecdsa`, pulled transitively by
  `arweave-python-client==1.0.19`. Ekklesia uses only the library's RSA Arweave
  wallet/signing path, but the package cannot currently be installed without
  `python-jose` and `ecdsa`.
- `CVE-2026-85394` (GHSA-3qf3-8w2g-rqmx) affects `python-jose` through 3.5.0
  (latest, no fix): asymmetric keys are accepted for HMAC initialization.
  The Arweave client uses `jose` only for base64url helpers and
  `jwk.construct(..., RS256)` on our own wallet; `apps/api` never imports
  `jose` and no HMAC/JWT path uses it. Added 2026-10-08 (T-604);
  review_by 2026-11-01.
- The security workflow ignores only these two advisories. Remove them when
  an upstream Arweave client release drops the dependency or when MOD-08 moves
  to a maintained client.
