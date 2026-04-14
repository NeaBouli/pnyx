# MIGRATION SECURITY MEMO
## Projekt: Ekklesia.gr / Pnyx
## Datum: 14.04.2026

### Was wurde gefixt
- Arweave Wallet: chmod 600 (nur Owner lesbar)
- GitHub OAuth: .secrets Datei geloescht (Cloudflare Wrangler Secrets verifiziert)
- OAuth Client ID aus tracked config.js entfernt
- .gitleaks.toml erstellt (GitHub OAuth, Arweave, API Keys)
- .github/workflows/security-audit.yml erstellt

### Bei Migration beachten
- [ ] GitHub OAuth Proxy laeuft auf Cloudflare Workers — kein eigener Server noetig
- [ ] Cloudflare Secrets bereits gesetzt (GITHUB_CLIENT_ID + SECRET)
- [ ] Arweave Wallet erst nach MOD-08 Live-Schaltung auf Server uebertragen
- [ ] arweave_wallet_path leer lassen = Dry Run (sicher)
- [ ] Server-Salt MUSS ein starker Zufallswert sein (nicht dev-salt-change-in-production)
- [ ] PostgreSQL Passwort MUSS geaendert werden (nicht devpassword)

### Benoetigte ENV-Variablen
- DATABASE_URL (PostgreSQL + asyncpg)
- SERVER_SALT (kryptographisch stark, min 32 Zeichen)
- REDIS_URL
- ARWEAVE_WALLET_PATH (leer fuer Dry Run, Pfad fuer Production)
- HLRLOOKUPS_USERNAME (SMS Verifikation)
- HLRLOOKUPS_PASSWORD
- GOVGR_CLIENT_ID (gov.gr OAuth — Phase 2)
- GOVGR_CLIENT_SECRET
- ACME_EMAIL (Let's Encrypt)

### Was NIE auf den Server darf
- arweave-wallet.json (erst bei MOD-08 Live-Schaltung, dann nur mit chmod 600)
- .secrets Dateien (geloescht, Cloudflare Vault nutzen)
- Lokale Entwickler-.env Dateien

### Migrations-Reihenfolge
1. Server aufsetzen (Docker Compose: PostgreSQL + Redis + FastAPI)
2. ENV-Variablen konfigurieren (SERVER_SALT, DB_PASSWORD stark!)
3. Alembic Migrations ausfuehren (alembic upgrade head)
4. Seeds laden (8 Parteien, 38 VAA-Thesen, 3 Bills)
5. Cloudflare Worker verifizieren (OAuth Proxy health check)
6. DNS auf Server zeigen
7. Let's Encrypt Zertifikat holen
8. Arweave Wallet NICHT deployen bis MOD-08 ready
