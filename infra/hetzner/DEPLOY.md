# Ekklesia.gr — Hetzner Deployment Guide

## Schritt 1: Server erstellen
- Hetzner Cloud → New Server
- Image: Ubuntu 24.04
- Type: CX21 (2 vCPU, 4GB RAM, ~7€/Monat)
- SSH Key hinterlegen
- Firewall: Port 22, 80, 443

## Schritt 2: Server einrichten
```bash
ssh root@<SERVER_IP>
curl -fsSL https://raw.githubusercontent.com/NeaBouli/pnyx/main/infra/hetzner/setup.sh | bash
```

## Schritt 3: Secrets eintragen
```bash
nano /opt/ekklesia/.env.production
# Alle REPLACE_WITH_... Werte ersetzen
```

## Schritt 4: Starten
```bash
cd /opt/ekklesia/infra/docker
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
docker compose -f docker-compose.prod.yml exec api python seeds/seed.py
```

## Schritt 5: GitHub Secrets setzen
Unter github.com/NeaBouli/pnyx/settings/secrets/actions:
- HETZNER_HOST = <SERVER_IP>
- HETZNER_USER = root
- HETZNER_SSH_KEY = <Private SSH Key>

## Schritt 6: community.html aktualisieren
```javascript
var SERVER_DUE_DATE = new Date("YYYY-MM-DD");
var SERVER_RF       = "RF__ ____ ____ ____";
```

## Fertig
Kein automatisches Deployment: `.github/workflows/deploy.yml` ist nur `workflow_dispatch`. Produktions-Releases laufen nach dem Verfahren unten ("Production release procedure").

## Mobile App

### Android APK
- EAS Project: kaspartisan/ekklesia-gr
- Build: https://expo.dev/accounts/kaspartisan/projects/ekklesia-gr/builds/07f282ee-1f5f-498a-a852-8fcffc4254c5
- Neuen Build erstellen: `cd apps/mobile && eas build --platform android --profile preview --non-interactive`

### iOS (PWA — kein App Store nötig)
- Nutzer öffnet ekklesia.gr in Safari
- "Zum Homescreen hinzufügen"
- Funktioniert als native App

## Production release procedure (current, since 2026-10)

Production runs on the host behind Traefik with the repository checkout at
`/opt/ekklesia/app` and the environment in `/opt/ekklesia/.env.production`
(never printed or copied). Every rollout needs the owner's explicit approval
for its scope. Each release gets its own directory
`/opt/ekklesia/releases/<name>-<commit8>-<UTC timestamp>/` that holds
`compose.release.yml`, `compose.rollback.yml`, a README, build logs and a
`postflight.txt`.

1. **Inventory (read-only).** Record the checkout commit, the running image
   tag and image id of each `ekklesia-*` container, and the Compose override
   chain (`com.docker.compose.project.config_files` label). Compare with the
   target commit: pending Alembic revisions (`alembic current` in `api`),
   compose changes, and environment variable *names* the code or compose file
   needs. Stop and escalate on a destructive migration, a missing required
   secret, an unclear diff, or anything that would run the knowledge-base
   sync.
2. **Rollback point.**
   - `git tag rollback-pre-<release>-<TS> <live commit>` in `/opt/ekklesia/app`.
   - Database dump: `docker exec ekklesia-db pg_dump -U ekklesia ekklesia_prod | gzip > /opt/backups/ekklesia_prod_pre-<release>-<TS>.sql.gz`,
     then `gzip -t`, and record size and SHA-256. Do **not** use
     `/opt/ekklesia/scripts/backup.sh` for this: it deletes all but the newest
     seven dumps.
   - `docker tag <running image id> <repo>:rollback-pre-<release>-<TS>` for
     every service that will change.
3. **Build.** Fast-forward the checkout (`git merge --ff-only origin/main`,
   never force), then build with the base file plus the new override so the
   images get release tags and existing tags stay untouched:
   `docker compose -p docker --env-file /opt/ekklesia/.env.production -f infra/docker/docker-compose.prod.yml -f <release>/compose.release.yml build <service>`.
4. **Roll out one service at a time** with
   `up -d --no-deps --no-build <service>` and the same `-f` chain:
   `api` → check `https://api.ekklesia.gr/health` (the API health route is
   `/health`; there is no `/api/v1/health`) → `alembic upgrade head` inside
   `api` → `web` → `dashboard` → `docker-proxy` and `monitor`.
   Never run `seed_knowledge_base.py sync` as part of a release; it is a
   separate, owner-approved operator step with its own rollback point.
5. **Live checks.** All `ekklesia-*` containers running without restarts;
   `https://ekklesia.gr/`, `/health`, bills list and detail, vote results for
   a real bill, `/el/sso-verify`, `https://pnyx.ekklesia.gr/` (forum bridge);
   desktop and phone viewport for UI changes. Write `postflight.txt`.
6. **Rollback** if a live check fails:
   `git checkout rollback-pre-<release>-<TS>` in `/opt/ekklesia/app`, then
   `up -d --no-deps --no-build <service>` with
   `-f <release>/compose.rollback.yml`; for the database, downgrade Alembic to
   the recorded revision or restore the dump.

## Rollback (legacy single-checkout setup)
```bash
cd /opt/ekklesia
git log --oneline -5
git checkout <COMMIT_HASH>
docker compose -f infra/docker/docker-compose.prod.yml up -d --build
```
