# Hermes Agent — Server Mind Architecture
## Stand: 2026-05-08 | Planung vor CX43 Upgrade
## Basis: Nous Research Hermes Agent (MIT License)

---

## Konzept: Server Mind

Ein einziger Hermes Agent der auf dem CX43 Server laeuft
und ALLE Projekte ueberwacht, koordiniert und lernt.

```
Hetzner CX43 (16GB RAM, nach Upgrade)
|
+-- ekklesia.gr Stack (~8 Container)
+-- inferno ($IFR Token Projekt)
+-- vendeta (Price Transparency)
+-- [weitere V-Labs Projekte]
|
+-- hermes-agent (Server Mind)
    +-- LLM: Ollama qwen2.5:14b (lokal, 0 EUR)
    +-- Memory: SQLite FTS5 (persistent)
    +-- Gateway: Telegram Bot
    +-- Skills: selbstlernend
    +-- Tools: Docker, SSH, DB, Logs
```

---

## Rollen des Hermes Agent

### 1. Server-Ueberwachung (sofort nach Install)
- Docker Container Status alle 5 Min pruefen
- Wenn Service down -> Telegram Alert an Admin
- RAM/CPU/Disk Ueberwachung
- Traefik Error-Rate ueberwachen
- Automatic Recovery: `docker restart [container]`

### 2. Log-Analyse (lernend)
- ekklesia API Logs taeglich zusammenfassen
- Sentry Errors clustern und priorisieren
- Anomalien erkennen (ungewoehnliche Traffic-Muster)
- Bericht taeglich 08:00 via Telegram

### 3. Routine-Aufgaben (automatisiert)
- DB-Backup taeglich 03:00
- Redis Cache-Flush bei Bedarf
- Alte Docker Images aufraeumen
- Discourse Backup triggern

### 4. Projekt-Koordination
- Weiss ueber alle Projekte auf dem Server Bescheid
- Kann Fragen beantworten: "Was laeuft auf dem Server?"
- Dokumentiert automatisch neue Deployments
- Trackt Versionen aller Services

---

## Hermes + ekklesia.gr — direkte Integration

### A. Chatbot Knowledge Base aufwerten
Problem aktuell: Ollama llama3.2:3b halluziniert bei
komplexen Fragen, KB-Eintraege sind statisch.

Loesung mit Hermes:
- Hermes analysiert taeglich Chatbot-Logs
- Erkennt welche Fragen schlecht beantwortet wurden
- Generiert neue KB-Eintraege automatisch
- Submitted KB-Updates zur Review (kein Auto-Deploy)
- Ueber Zeit: KB wird immer vollstaendiger

### B. Ollama Performance verbessern
Problem: llama3.2:3b ist zu klein fuer komplexe Anfragen.

Nach CX43 + qwen2.5:14b:
- Hermes routet Anfragen intelligent:
  * Einfache Fragen -> llama3.2:3b (schnell)
  * Komplexe Fragen -> qwen2.5:14b (besser)
  * Sehr komplex -> Claude Haiku (Fallback, minimal)
- Hermes lernt welche Fragen welches Modell brauchen

### C. Hermes 3 Modelle (Nous Research)
Die Hermes 3 Familie (8B, 14B, 70B) ist speziell
optimiert fuer:
- Tool Calling (perfekt fuer Agent-Tasks)
- Strukturierte Outputs (JSON)
- Instruktions-Folge

Hermes-3-8B koennte llama3.2:3b im Chatbot ersetzen:
- Besser in Griechisch
- Weniger Halluzinationen
- Besser bei ekklesia-spezifischen Fragen

### D. Autonome KB-Verbesserung
Hermes Agent hat persistente Memory ueber Sessions:
- Erinnert sich an Nutzer-Fragen die schlecht beantwortet
- Sammelt ueber Zeit Muster
- Schlaegt KB-Verbesserungen vor
- Dev-Team reviewed + approved

---

## Tech Stack

| Komponente | Technologie | Kosten |
|---|---|---|
| Agent Framework | Hermes Agent (MIT) | 0 EUR |
| LLM (Routing) | Ollama qwen2.5:14b | 0 EUR |
| LLM (Chatbot) | Hermes-3-8B via Ollama | 0 EUR |
| Memory | SQLite FTS5 (lokal) | 0 EUR |
| Gateway | Telegram Bot | 0 EUR |
| Monitoring | Docker API + Prometheus | 0 EUR |
| Fallback LLM | Claude Haiku | minimal |

**Gesamtkosten: ~0 EUR/Monat**

---

## Implementierungs-Phasen

### Phase 0 (heute — Vorbereitung):
- Architektur dokumentiert
- Telegram Bot Token besorgen
- Hermes Agent lokal testen

### Phase 1 (nach CX43 Upgrade):
- Hermes Agent auf Server installieren
- Ollama auf qwen2.5:14b upgraden
- Telegram Gateway einrichten
- Basis-Monitoring aktivieren

### Phase 2 (1-2 Wochen):
- Hermes-3-8B als Chatbot-Modell testen
- KB Auto-Analyse Pipeline aufbauen
- Intelligentes LLM-Routing implementieren

### Phase 3 (1 Monat):
- Autonome KB-Verbesserung aktiv
- Hermes ueberwacht alle V-Labs Projekte
- Self-Learning Skills aufgebaut

---

## Installation (Phase 1)

```bash
# Auf CX43 nach Upgrade:
curl -fsSL https://hermesagent.agency/install.sh | bash

# Ollama Modell upgraden:
ollama pull qwen2.5:14b
ollama pull hermes3:8b  # falls verfuegbar

# Hermes konfigurieren:
hermes config set model ollama/qwen2.5:14b
hermes gateway setup telegram
hermes start
```

---

## Wichtige Links
- Hermes Agent: https://github.com/nousresearch/hermes-agent
- Hermes 3 Modelle: https://huggingface.co/NousResearch
- Ollama: https://ollama.ai

---

*Erstellt: 2026-05-08*
*Status: PLANUNG — Implementierung nach CX43 Upgrade*
*Autor: Kaspartizan + Claude*
