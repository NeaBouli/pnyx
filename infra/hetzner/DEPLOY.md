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
Jeder `git push` auf main → automatisches Deployment.

## Rollback
```bash
cd /opt/ekklesia
git log --oneline -5
git checkout <COMMIT_HASH>
docker compose -f infra/docker/docker-compose.prod.yml up -d --build
```
