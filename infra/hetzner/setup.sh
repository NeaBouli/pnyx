#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# setup.sh — Initial server hardening + Docker + central Traefik
# Run once on a fresh Hetzner CX33 (Ubuntu 24.04)
# ADR-009: Multi-project /srv/ layout
# Usage: bash setup.sh
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

ACME_EMAIL="${ACME_EMAIL:-kaspartisan@proton.me}"

echo "═══ NeaBouli Server Setup ═══"

# ── 1. System update ──────────────────────────────────────────
echo "[1/6] System update..."
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq curl git ufw fail2ban unattended-upgrades

# ── 2. Firewall ───────────────────────────────────────────────
echo "[2/6] UFW firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment "SSH"
ufw allow 80/tcp comment "HTTP"
ufw allow 443/tcp comment "HTTPS"
ufw --force enable

# ── 3. SSH hardening ──────────────────────────────────────────
echo "[3/6] SSH hardening..."
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl reload sshd

# ── 4. Docker ─────────────────────────────────────────────────
echo "[4/6] Docker CE..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
fi
docker --version
docker compose version

# ── 5. Directory layout ──────────────────────────────────────
echo "[5/6] Creating /srv/ layout..."
mkdir -p /srv/traefik/acme /srv/_template
chmod 600 /srv/traefik/acme

# Create shared Traefik network
docker network create traefik-public 2>/dev/null || true

# ── 6. Central Traefik ────────────────────────────────────────
echo "[6/6] Central Traefik..."

cat > /srv/traefik/traefik.yml << 'TRAEFIK'
api:
  dashboard: false

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure
          scheme: https
  websecure:
    address: ":443"

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
    network: traefik-public

certificatesResolvers:
  letsencrypt:
    acme:
      email: "${ACME_EMAIL}"
      storage: /acme/acme.json
      tlsChallenge: {}

log:
  level: WARN
TRAEFIK

cat > /srv/traefik/docker-compose.yml << 'COMPOSE'
services:
  traefik:
    image: traefik:v3.6
    container_name: traefik-central
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik.yml:/traefik.yml:ro
      - ./acme:/acme
    networks:
      - traefik-public
    environment:
      DOCKER_API_VERSION: "1.46"

networks:
  traefik-public:
    external: true
COMPOSE

echo ""
echo "═══ Setup complete ═══"
echo "  Firewall:  UFW active (22/80/443)"
echo "  Docker:    $(docker --version)"
echo "  Layout:    /srv/traefik/ + /srv/_template/"
echo "  Network:   traefik-public"
echo ""
echo "  IMPORTANT: Do NOT start central Traefik while ekklesia's"
echo "  embedded Traefik owns ports 80/443. See ADR-009 for migration."
echo ""
echo "  Next: bash new-project.sh PROJEKTNAME DOMAIN"
