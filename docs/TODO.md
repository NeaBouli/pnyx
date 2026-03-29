# Ekklesia.gr — TODO

## Phase 0 (aktuell): Fundament
- [ ] Docker Compose (PostgreSQL, Redis, FastAPI, Next.js)
- [ ] FastAPI Grundgerüst + Health Check
- [ ] Alembic Setup + erste Migration
- [ ] packages/crypto: Ed25519 + Nullifier
- [ ] packages/i18n: el/en Basis-Strings
- [ ] GitHub Remote verknüpfen (https://github.com/NeaBouli/pnyx)

## Phase 1: MOD-01 Identity (Beta)
- [ ] SMS HLR Lookup (Twilio)
- [ ] Ed25519 Keypair Generierung
- [ ] Nullifier Hash (SHA256 + SERVER_SALT)
- [ ] Key Revokation Endpoint
- [ ] Mobile: expo-secure-store + expo-local-auth

## Phase 2: MOD-02 VAA + MOD-03 Parliament
- [ ] Parteien-Seed-Daten (6-8 griechische Parteien)
- [ ] 15 Thesen initial
- [ ] Matching-Algorithmus
- [ ] Βουλή API Cron Job (täglich 03:00)
- [ ] Bill Lifecycle State Machine

## Phase 3: MOD-04 CitizenVote
- [ ] POST /api/vote mit Ed25519 Signatur-Validierung
- [ ] UNIQUE INDEX gegen Doppelstimme
- [ ] WebSocket Live-Counter (WINDOW_24H)
- [ ] Divergence Score (MOD-05)
