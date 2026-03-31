#!/bin/bash
set -e
echo "=== Ekklesia.gr Server Setup ==="
apt-get update && apt-get upgrade -y
curl -fsSL https://get.docker.com | sh
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
mkdir -p /opt/ekklesia && cd /opt/ekklesia
git clone https://github.com/NeaBouli/pnyx.git .
cp .env.production.template .env.production
echo ""
echo "=== Secrets ==="
echo "SECRET_KEY=$(openssl rand -hex 64)"
echo "SERVER_SALT=$(openssl rand -hex 32)"
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32)"
echo ""
echo "Edit: nano /opt/ekklesia/.env.production"
echo "Start: cd infra/docker && docker compose -f docker-compose.prod.yml up -d"
echo ""
echo "=== Nach Start: Ollama Modell installieren ==="
echo "docker exec ekklesia-ollama ollama pull llama3.2"
