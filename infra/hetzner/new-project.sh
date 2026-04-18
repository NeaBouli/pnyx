#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# new-project.sh — Scaffold a new project under /srv/
# ADR-009: Multi-project server architecture
# Usage: bash new-project.sh PROJEKTNAME DOMAIN [PORT]
# Example: bash new-project.sh parley parley.neabouli.com 8001
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

NAME="${1:?Usage: $0 PROJEKTNAME DOMAIN [PORT]}"
DOMAIN="${2:?Usage: $0 PROJEKTNAME DOMAIN [PORT]}"
PORT="${3:-8000}"

DIR="/srv/${NAME}"

if [ -d "$DIR" ]; then
    echo "ERROR: $DIR already exists"
    exit 1
fi

echo "═══ Creating project: ${NAME} ═══"
echo "  Domain:  ${DOMAIN}"
echo "  Port:    ${PORT}"
echo "  Dir:     ${DIR}"

# ── Create directory structure ────────────────────────────────
mkdir -p "${DIR}"

# ── Generate .env template ────────────────────────────────────
cat > "${DIR}/.env" << ENV
# ${NAME} — Environment Variables
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)
COMPOSE_PROJECT_NAME=${NAME}
DOMAIN=${DOMAIN}
APP_PORT=${PORT}

# Database (generate: openssl rand -hex 24)
POSTGRES_DB=${NAME}_prod
POSTGRES_USER=${NAME}
POSTGRES_PASSWORD=CHANGE_ME

# App secrets (generate: openssl rand -hex 32)
SECRET_KEY=CHANGE_ME
ENV

# ── Generate docker-compose.yml ───────────────────────────────
cat > "${DIR}/docker-compose.yml" << COMPOSE
services:
  app:
    build: .
    container_name: ${NAME}-app
    restart: unless-stopped
    env_file: .env
    networks:
      - traefik-public
      - internal
    depends_on:
      db:
        condition: service_healthy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.${NAME}.rule=Host(\\\`${DOMAIN}\\\`)"
      - "traefik.http.routers.${NAME}.entrypoints=websecure"
      - "traefik.http.routers.${NAME}.tls.certresolver=letsencrypt"
      - "traefik.http.services.${NAME}.loadbalancer.server.port=${PORT}"
      # Security headers
      - "traefik.http.middlewares.${NAME}-headers.headers.stsSeconds=31536000"
      - "traefik.http.middlewares.${NAME}-headers.headers.contentTypeNosniff=true"
      - "traefik.http.middlewares.${NAME}-headers.headers.frameDeny=true"
      - "traefik.http.routers.${NAME}.middlewares=${NAME}-headers"

  db:
    image: postgres:15-alpine
    container_name: ${NAME}-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: \${POSTGRES_DB}
      POSTGRES_USER: \${POSTGRES_USER}
      POSTGRES_PASSWORD: \${POSTGRES_PASSWORD}
    volumes:
      - db-data:/var/lib/postgresql/data
    networks:
      - internal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  db-data:

networks:
  traefik-public:
    external: true
  internal:
    internal: true
COMPOSE

echo ""
echo "═══ Project scaffolded ═══"
echo "  1. Edit secrets:  nano ${DIR}/.env"
echo "  2. Add Dockerfile: cp your-app/Dockerfile ${DIR}/"
echo "  3. Start:         cd ${DIR} && docker compose up -d"
echo "  4. DNS:           Point ${DOMAIN} → $(hostname -I | awk '{print $1}')"
