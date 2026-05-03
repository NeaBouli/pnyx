# AUDIT_MUST_READ

Vor jeder Arbeit an diesem Repository zuerst den Master-Audit in diesem Ordner lesen.

Pflichtdatei:

- `pnyx_MASTER_AUDIT_20260503.md`

Arbeitsregeln:

- Findings und Risiken vor Codeaenderungen pruefen.
- Keine `.env`, `.env.*`, `.gitignore`, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien lesen.
- Keine Secrets ausgeben.
- Kein Commit, Push, Deployment oder SSH ohne explizite Nutzerfreigabe.
- Bei pnyx zusaetzlich die Agent-Bridge unter `docs/agent-bridge/` aktuell halten.

