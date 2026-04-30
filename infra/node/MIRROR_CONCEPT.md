# ekklesia.gr Mirror Server — Architektur & Konzept
## Version 1.0 | 2026-04-30 | Vendetta Labs

---

## 1. Was ist ein Mirror?

Ein Mirror ist eine **Read-Only Kopie** des ekklesia.gr Hauptservers. Er dient als:
- **Ausfallschutz:** Wenn der Hauptserver offline geht, bleiben die Daten zugänglich
- **Zensurschutz:** Mehrere unabhängige Server in verschiedenen Jurisdiktionen
- **Lastverteilung:** Traffic wird auf mehrere Server verteilt
- **Community-Empowerment:** Jeder Bürger kann einen Mirror betreiben

### Was ein Mirror KANN:
- Bills anzeigen (alle Status)
- Abstimmungsergebnisse anzeigen
- Analytics, Divergence Scores, MP Comparison
- Wiki, FAQ, Community-Seiten
- Chatbot (lokal via Ollama oder cached Antworten)
- Sich automatisch alle 5 Min synchronisieren

### Was ein Mirror NICHT KANN:
- Votes entgegennehmen (Read-Only — Votes gehen immer an api.ekklesia.gr)
- Identitäten verifizieren (HLR Lookup nur auf Hauptserver)
- Forum betreiben (Discourse bleibt zentral auf pnyx.ekklesia.gr)
- Newsletter versenden

---

## 2. Architektur

### 2.1 Hauptserver (ekklesia.gr) — MASTER

```
┌─────────────────────────────────────────┐
│           HAUPTSERVER (Master)          │
│         Hetzner CX33, Helsinki          │
├─────────────────────────────────────────┤
│  ekklesia-web    (Next.js, Port 3000)   │
│  ekklesia-api    (FastAPI, Port 8000)   │
│  ekklesia-db     (PostgreSQL 15)        │
│  ekklesia-redis  (Redis 7)              │
│  ekklesia-ollama (Ollama llama3.2)      │
│  traefik         (SSL/TLS)              │
│  discourse       (Forum)                │
│  listmonk        (Newsletter)           │
├─────────────────────────────────────────┤
│  Domains:                               │
│  - ekklesia.gr                          │
│  - api.ekklesia.gr                      │
│  - pnyx.ekklesia.gr                     │
│  - newsletter.ekklesia.gr               │
└─────────────────────────────────────────┘
```

### 2.2 Mirror-Server (1/2/3.ekklesia.gr) — READ-ONLY

```
┌─────────────────────────────────────────┐
│          MIRROR SERVER (Slave)          │
│        Beliebiger VPS, min 1GB RAM      │
├─────────────────────────────────────────┤
│  ekklesia-web    (Next.js, Port 3000)   │
│  mirror-api      (Caching Proxy, 8000)  │
│  redis           (Cache, Port 6379)     │
│  traefik         (SSL/TLS)              │
├─────────────────────────────────────────┤
│  KEIN PostgreSQL                        │
│  KEIN Ollama (optional)                 │
│  KEIN Discourse                         │
│  KEIN Listmonk                          │
├─────────────────────────────────────────┤
│  Domain: z.B. 1.ekklesia.gr            │
│  Sync: api.ekklesia.gr → alle 5 Min    │
└─────────────────────────────────────────┘
```

### 2.3 Sync-Flow

```
MASTER (api.ekklesia.gr)          MIRROR (mirror-api)
         │                              │
         │  GET /api/v1/mirror/snapshot  │
         │◄─────────────────────────────│  (alle 5 Min)
         │                              │
         │  JSON Response:              │
         │  - bills[] (alle)            │
         │  - results[] (alle)          │
         │  - parties[]                 │
         │  - analytics{}               │
         │  - knowledge_base[]          │
         │  - signature (Ed25519)       │
         │─────────────────────────────►│
         │                              │
         │                    ┌─────────┤
         │                    │ Redis   │
         │                    │ Cache   │
         │                    │ (TTL    │
         │                    │  5 Min) │
         │                    └─────────┤
         │                              │
    USER ─────────────────────────────► │
         │                    GET /bills │
         │                    (aus      │
         │                     Cache)   │
```

### 2.4 Vote-Redirect

Wenn ein User auf dem Mirror abstimmen will:
```
Mirror-Web → "Ψηφίστε" Button → Redirect zu https://ekklesia.gr/el/bills/{id}
```
Der Mirror leitet den User zum Hauptserver weiter. Votes werden NIEMALS lokal verarbeitet.

---

## 3. Mirror-API (Caching Proxy)

### 3.1 Endpoints

| Endpoint | Quelle | Cache TTL |
|----------|--------|-----------|
| GET /health | Lokal | - |
| GET /api/v1/bills | Redis Cache | 5 Min |
| GET /api/v1/bills/{id} | Redis Cache | 5 Min |
| GET /api/v1/bills/{id}/results | Redis Cache | 5 Min |
| GET /api/v1/analytics/overview | Redis Cache | 5 Min |
| GET /api/v1/mp/ranking | Redis Cache | 30 Min |
| GET /api/v1/public/* | Redis Cache | 5 Min |
| POST /api/v1/vote | **REDIRECT** → api.ekklesia.gr | - |
| POST /api/v1/identity/* | **REDIRECT** → api.ekklesia.gr | - |
| POST /api/v1/agent/ask | **REDIRECT** oder lokaler Ollama | - |

### 3.2 Signatur-Verifizierung

Der Hauptserver signiert jeden Snapshot mit Ed25519:
```python
# Master: Snapshot signieren
snapshot_json = json.dumps(data, sort_keys=True)
signature = ed25519.sign(snapshot_json.encode(), MASTER_PRIVATE_KEY)

# Mirror: Signatur verifizieren
ed25519.verify(signature, snapshot_json.encode(), MASTER_PUBLIC_KEY)
# Nur verifizierte Daten werden in Redis gespeichert
```

Der Master Public Key ist im Mirror-Code hardcoded — so kann niemand gefälschte Daten einschleusen.

---

## 4. Setup-Prozess

### 4.1 Voraussetzungen Mirror-Betreiber
- VPS mit Ubuntu 22.04+ oder Debian 12+
- Minimum 1 GB RAM, 10 GB Disk
- Root-Zugang
- DNS: A-Record für die zugewiesene Subdomain

### 4.2 Ein-Befehl Installation

```bash
curl -fsSL https://ekklesia.gr/mirror-setup.sh | sudo bash
```

### 4.3 Wizard-Flow

```
╔═══════════════════════════════════════╗
║     ekklesia.gr — Mirror Setup       ║
║     Εγκατάσταση Κατόπτρου            ║
╚═══════════════════════════════════════╝

[1/4] Έλεγχος συστήματος...
  ✓ Ubuntu 24.04
  ✓ RAM: 2048 MB
  ✓ Disk: 25 GB frei
  ✓ Docker installiert

[2/4] Διαθέσιμες Subdomains:
  ✅ 1.ekklesia.gr — ελεύθερο
  ❌ 2.ekklesia.gr — κατειλημμένο
  ✅ 3.ekklesia.gr — ελεύθερο

  Επιλέξτε (1/3): 1

[3/4] Admin Email: user@example.com

[4/4] Επιβεβαίωση:
  Mirror: 1.ekklesia.gr
  Server: 203.0.113.42
  Admin:  user@example.com

  Συνέχεια; (y/N): y

[Εγκατάσταση...]
  ✓ Docker containers ξεκίνησαν
  ✓ SSL πιστοποιητικό εκδόθηκε
  ✓ Πρώτος συγχρονισμός ολοκληρώθηκε
  ✓ Κατοχυρώθηκε στο ekklesia.gr

╔═══════════════════════════════════════════╗
║  ✓ Το κάτοπτρο είναι έτοιμο!            ║
║                                           ║
║  URL:    https://1.ekklesia.gr            ║
║  Status: https://1.ekklesia.gr/health     ║
║  Logs:   docker logs mirror-api -f        ║
║                                           ║
║  Αυτόματες ενημερώσεις: Ενεργοποιημένες  ║
║  Συγχρονισμός: Κάθε 5 λεπτά              ║
╚═══════════════════════════════════════════╝
```

---

## 5. Subdomain-System

### 5.1 Vorkonfigurierte Subdomains

| Subdomain | DNS | Status |
|-----------|-----|--------|
| 1.ekklesia.gr | A → Mirror-IP | Verfügbar |
| 2.ekklesia.gr | A → Mirror-IP | Verfügbar |
| 3.ekklesia.gr | A → Mirror-IP | Verfügbar |

### 5.2 DNS-Verwaltung

- DNS A-Records werden **manuell** vom ekklesia-Team gesetzt (Gio)
- Mirror-Betreiber meldet sich an → teilt Server-IP mit
- Team setzt DNS → Mirror startet mit SSL
- Bei mehr als 3 Mirrors: neue Subdomains (4, 5, 6...) anlegen

### 5.3 Counter auf Community-Seite

```
┌────────────────────────────────────┐
│  🪞 Mirror Server                  │
│                                    │
│  1.ekklesia.gr  ✅ Online          │
│  2.ekklesia.gr  ⬚ Verfügbar       │
│  3.ekklesia.gr  ⬚ Verfügbar       │
│                                    │
│  [Mirror einrichten →]             │
│                                    │
│  3 Subdomains · 1 aktiv · 2 frei  │
└────────────────────────────────────┘
```

---

## 6. Hetzner Snapshot als Basis

### 6.1 Snapshot: `ekklesia-secure-2026-04-18-k`

Dieser Snapshot enthält den kompletten Server-Stand. Für einen Mirror:
1. Snapshot als neuen Server deployen (Hetzner Console)
2. DB + Discourse + Listmonk entfernen
3. API auf Read-Only umschalten
4. Sync-Service aktivieren

### 6.2 Alternativ: Docker Image (empfohlen)

Statt Snapshot → vorgefertigtes Docker Image:
```
ghcr.io/neabouli/ekklesia-mirror:latest
```
Enthält: Next.js Web + Mirror-API + Redis Config
Wird automatisch via Watchtower aktualisiert.

---

## 7. Master-API: Snapshot-Endpoint

### 7.1 Neuer Endpoint auf api.ekklesia.gr

```
GET /api/v1/mirror/snapshot
Authorization: Bearer MIRROR_TOKEN
```

Response:
```json
{
  "timestamp": "2026-04-30T12:00:00Z",
  "version": "1.0",
  "data": {
    "bills": [...],
    "results": {...},
    "parties": [...],
    "analytics": {...},
    "knowledge_base": [...]
  },
  "signature": "Ed25519-SIGNATURE-HEX"
}
```

### 7.2 Mirror-Registrierung

```
POST /api/v1/mirror/register
{
  "subdomain": "1",
  "server_ip": "203.0.113.42",
  "admin_email": "user@example.com",
  "public_key": "Ed25519-PUBLIC-KEY"
}
```

Response: `{ "status": "pending", "mirror_token": "..." }`

### 7.3 Mirror-Health Reporting

Jeder Mirror meldet alle 5 Min seinen Status:
```
POST /api/v1/mirror/heartbeat
Authorization: Bearer MIRROR_TOKEN
{
  "subdomain": "1",
  "uptime_seconds": 86400,
  "last_sync": "2026-04-30T12:00:00Z",
  "cache_size_mb": 12,
  "requests_served": 1234
}
```

---

## 8. Sicherheit

### 8.1 Daten auf dem Mirror
- **Keine** personenbezogenen Daten (keine DB, keine Identity-Records)
- Nur öffentliche Daten: Bills, Results, Analytics, KB
- Redis-Cache ist flüchtig (geht bei Neustart verloren)

### 8.2 Signatur-Kette
- Master signiert jeden Snapshot mit Ed25519
- Master Public Key ist im Mirror-Code hardcoded
- Mirror akzeptiert nur signierte Daten
- Man-in-the-Middle kann keine gefälschten Bills einschleusen

### 8.3 Token-System
- Jeder Mirror hat ein einzigartiges Bearer Token
- Token wird bei Registrierung generiert (SHA256)
- Token-Hash gespeichert auf Master (nicht der Token selbst)
- Kompromittierter Mirror kann jederzeit gesperrt werden

### 8.4 Auto-Update
- Watchtower prüft täglich auf neue Docker Images
- Sicherheits-Patches werden automatisch eingespielt
- Kein manueller Eingriff nötig

---

## 9. Implementierungs-Reihenfolge

### Phase 1: Master-API (2h)
1. `GET /api/v1/mirror/snapshot` — öffentliche Daten + Signatur
2. `POST /api/v1/mirror/register` — Mirror-Registrierung
3. `POST /api/v1/mirror/heartbeat` — Status-Meldung
4. DB-Migration: `mirror_nodes` Tabelle

### Phase 2: Mirror Docker Image (3h)
1. `mirror-api.py` — Caching Proxy (FastAPI, ~200 Zeilen)
2. `docker-compose.mirror.yml` — Web + Mirror-API + Redis + Traefik
3. `Dockerfile.mirror` — Leichtgewichtig

### Phase 3: Setup-Script (2h)
1. `mirror-setup.sh` — Ein-Befehl Installer
2. `mirror-wizard.sh` — Interaktiver Wizard
3. Subdomain-Verfügbarkeit prüfen via API

### Phase 4: Community-Seite (1h)
1. Mirror-Kachel auf community.html
2. Counter: aktive/verfügbare Mirrors
3. Link zur Setup-Anleitung (versteckte Seite)

### Phase 5: DNS + Go-Live (30 Min)
1. DNS: 1.ekklesia.gr, 2.ekklesia.gr, 3.ekklesia.gr
2. Test-Mirror auf eigenem zweiten Server
3. Community-Ankündigung

---

## 10. Kosten für Mirror-Betreiber

| Posten | Kosten |
|--------|--------|
| VPS (z.B. Hetzner CX22) | ~4€/Monat |
| Domain | 0€ (Subdomain von ekklesia.gr) |
| SSL | 0€ (Let's Encrypt) |
| Wartung | 0€ (Auto-Update) |
| **Gesamt** | **~4€/Monat** |

---

*© 2026 Vendetta Labs — MIT License*
*Kontakt: github.com/NeaBouli/pnyx/issues*
