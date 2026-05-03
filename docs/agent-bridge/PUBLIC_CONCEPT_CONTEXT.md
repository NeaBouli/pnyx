# Public Concept Context

Dieses Dokument enthaelt oeffentlich dokumentierte Aussagen ueber ekklesia.gr,
extrahiert aus der Website und dem GitHub Wiki. Diese Aussagen sind NICHT
als Repo-Fakten zu behandeln, solange der lokale Code sie nicht bestaetigt.

Quellen-Datum: 2026-05-01

---

## Quelle: ekklesia.gr (Website)

Tag: `PUBLIC_DOCS:WEBSITE`

- 16 Module (MOD-01 bis MOD-16)
- 16 API Endpoints
- Ed25519 anonyme Abstimmung
- 4 Political-Compass-Modelle
- Divergence Score (Parlament vs. Buerger)
- Arweave permanente Archivierung
- Keine Cookies, kein Tracking, DSGVO-konform
- K-Anonymity Datenschutzmodell
- Nullifier-System
- SMS-Verifikation (sofortige Loeschung)
- Governance-Ebenen: Parlament, Periferia, Dimos
- AI: Ollama + DeepL fuer Zusammenfassungen
- Roadmap Beta → Alpha (500 User + 3 NGOs + gov.gr OAuth) → V2 (Blockchain)
- V-Labs Development, MIT License

## Quelle: GitHub Wiki (NeaBouli/pnyx/wiki)

Tag: `PUBLIC_DOCS:WIKI`

- 22 Module (MOD-01 bis MOD-22)
- 70+ API Endpoints
- 15+ Datenbank-Tabellen (Alembic)
- 9 Container (API, Web, DB, Redis, Ollama, Traefik, Listmonk x3)
- 106 API Tests passing
- 47 Crypto Tests (Nullifier + Polis Validation)
- 488 Commits
- Security Score: ~90/100
- Ed25519 + SHA256 + Argon2id
- AI: Ollama llama3.2:3b (2.6 GB RAM, 5 GB Limit)
- RAG-basierter Q&A Agent
- Auto-healing Web Scraper
- Newsletter: Listmonk + Brevo SMTP, 6 Subscriber-Listen
- Push Notifications: Expo Push API
- Stripe Donations
- Municipal Governance: 13 Regionen, 325 Gemeinden
- Rate Limiting: 60 req/min/IP global, 5 req/min/IP fuer AI
- Circuit Breaker: 3 Fehler → 24h Pause
- Distribution: APK direkt, GitHub Releases v1.0.0, Play Store (Closed Testing), F-Droid (MR #37087 pending)
- Roadmap: Beta (aktiv) → Alpha (500 User + 3 NGOs + gov.gr OAuth) → V2 (TrueRepublic Bridge + PnyxCoin)

---

## Dokumentations-Drift (ACHTUNG)

Folgende Widersprueche bestehen zwischen den oeffentlichen Quellen und/oder
dem lokalen Repo (CLAUDE.md, Session Memory). Jede Zahl ist UNSICHER bis
durch Code-Inspektion bestaetigt.

### Modul-Anzahl

| Quelle | Wert |
|---|---|
| CLAUDE.md (Repo, v7.0 Spec) | 15 Module |
| Website ekklesia.gr | 16 Module (MOD-01–MOD-16) |
| Wiki | 22 Module (MOD-01–MOD-22) |
| Session Memory (01.05.2026) | 24 Module |
| **API /health (Server, 01.05.2026)** | **24 Module** |

**Status:** GEKLAERT — API /health listet 24 Module. CLAUDE.md und Website/Wiki sind veraltet. 24 ist korrekt.

### API Endpoints

| Quelle | Wert |
|---|---|
| CLAUDE.md (Repo) | 13 Endpoints |
| Website ekklesia.gr | 16 Endpoints |
| Wiki | 70+ Endpoints |

**Status:** DRIFT — Wiki zaehlt vermutlich alle Sub-Routen, CLAUDE.md nur die Haupt-Module. Klarstellung noetig.

### Datenbank-Tabellen

| Quelle | Wert |
|---|---|
| CLAUDE.md (Repo) | 9 Tabellen, 3 Enums |
| Wiki | 15+ Tabellen |

**Status:** DRIFT — CLAUDE.md stammt aus einer aelteren Session. Alembic-Migrationen koennen Tabellen hinzugefuegt haben.

### Test-Zahlen

| Quelle | Wert |
|---|---|
| CLAUDE.md (Repo, Stand 09.04) | API 51 + 16 xfail, Crypto 12, Web 29 |
| Wiki | API 106, Crypto 47 |

**Status:** DRIFT — Wiki-Zahlen sind hoeher. Entweder Tests hinzugefuegt oder Wiki zaehlt anders.

### Container-Anzahl

| Quelle | Wert |
|---|---|
| Session Memory | 10 Container |
| Wiki | 9 Container |

**Status:** DRIFT — Differenz von 1. Discourse-Container evtl. separat gezaehlt. Server-Check noetig.

### Security Score

| Quelle | Wert |
|---|---|
| Session Memory | ~96/100 |
| Wiki | ~90/100 |

**Status:** DRIFT — Wiki moeglicherweise veraltet, oder Score-Methodik unterschiedlich.

### Political Compass Modelle

| Quelle | Wert |
|---|---|
| CLAUDE.md | 4 Modelle |
| Website | 4 Modelle |

**Status:** KONSISTENT

---

## gov.gr OAuth2.0

**Status:** DEFERRED / GATED

Alle Quellen (Website, Wiki, CLAUDE.md) stimmen ueberein:
- gov.gr OAuth wird erst in der Alpha-Phase aktiviert
- Gate: 500+ Nutzer UND 3+ NGO-Partnerschaften
- Aktuell NICHT implementiert, nur als Roadmap-Item
- Im Code als `MOD-09` gefuehrt
- Nicht als Feature bewerben, nicht als vorhanden behandeln

---

## Hinweise fuer Agenten

1. **Zahlen aus PUBLIC_DOCS sind Richtwerte, keine Fakten.** Nur Code/DB/CI sind massgeblich.
2. **Wiki wird manuell gepflegt** und kann dem Repo voraus oder hinterher sein.
3. **Website-Texte sind Marketing-nah** — Feature-Counts koennen geplante Module mitzaehlen.
4. **Bei Widerspruch: lokaler Code > Session Memory > Wiki > Website.**
5. **gov.gr OAuth ist GATED** — nie als verfuegbar behandeln.
6. **Keine Zahlen aus diesem Dokument in Produktcode oder API-Responses verwenden.**
