# Ekklesia.gr — Projektstatus
# Copyright (c) 2026 Vendetta Labs — MIT License
# Stand: 2026-04-09 — Session 3 komplett (alle Commits gepusht)

---

## Kurzübersicht

| Eigenschaft         | Wert                                              |
|---------------------|---------------------------------------------------|
| **Projekt**         | Ekklesia.gr — Digitale Direkte Demokratie (GR)    |
| **Codename**        | pnyx                                              |
| **Repo**            | https://github.com/NeaBouli/pnyx                  |
| **HEAD**            | `99ae8ea` (main, Remote synchron)                 |
| **Rollback**        | Tag `pre-session3-20260409` → `cd050e5`           |
| **Phase**           | Beta — Kernmodule + Liquid Compass komplett        |
| **Lizenz**          | MIT — (c) 2026 Vendetta Labs                      |

---

## Session 3 — Abgeschlossene Arbeit (10 Commits)

### 1. Header-Bug + Tailwind 4
- 9 doppelte `<header>` entfernt, Tailwind 4 PostCSS migriert

### 2. Mobile Ed25519 Signing
- `@noble/curves` auf Expo, `signVote()` + `verifyVote()`, Nullifier `:` Bug gefixt

### 3. Cross-Platform Krypto-Tests
- 12 neue Tests: Web ↔ Mobile ↔ Backend Signatur-Kompatibilität

### 4. VAA Erweiterung 15 → 38 Thesen
- 23 neue Statements (echte griechische Debatten 2024-2026)
- 304 verifizierte Parteipositionen (8 × 38)

### 5. Liquid Political Compass (NEU)
- **4 Modelle:** Party Match, Links-Rechts, 2D Kompass, Thematischer Radar
- **User wählt:** Modell aktivieren/deaktivieren, oder Kompass komplett aus
- **Liquid:** VAA = optionaler Einstieg, jede Bill-Abstimmung aktualisiert den Kompass
- **Privacy:** AES-256-GCM verschlüsselt (HKDF vom Ed25519 Key), 100% clientseitig
- **Nie auf Server:** Kompass-Daten verlassen nie das Gerät
- **30 Kategorien** gemappt auf politische Dimensionen
- **Route:** `/[locale]/compass` — vollständiges Dashboard

---

## Modulstatus

| Modul   | Name                  | Status       | Plattform          |
|---------|-----------------------|--------------|--------------------|
| MOD-01  | Identity              | KOMPLETT     | API + Web + Mobile |
| MOD-02  | VAA Wahlkompass       | KOMPLETT     | API + Web (38 Thesen) |
| MOD-02b | Liquid Compass        | KOMPLETT     | Web (4 Modelle, AES-256-GCM) |
| MOD-03  | Parliament Bills      | KOMPLETT     | API + Web + Mobile |
| MOD-04  | CitizenVote           | KOMPLETT     | API + Web + Mobile |
| MOD-05  | Divergence Score      | KOMPLETT     | API + Web + Mobile |
| MOD-14  | Relevance Up/Down     | KOMPLETT     | API + Web        |

---

## Kryptographie

| Komponente                | Status      |
|---------------------------|-------------|
| Ed25519 Signing (Backend) | OK — PyNaCl |
| Ed25519 Signing (Web)     | OK — @noble/curves |
| Ed25519 Signing (Mobile)  | OK — @noble/curves + self-verify |
| Nullifier Hash            | OK — SHA256(phone:salt) |
| Compass Encryption        | OK — AES-256-GCM via HKDF-SHA256 |
| Cross-Platform Compat     | VERIFIZIERT — 12 Tests |

---

## Tests

| Suite              | Tests | Ergebnis |
|--------------------|-------|----------|
| Web (vitest)       | 29    | 29 passed |
| Python Crypto      | 12    | 12 passed |
| API (pytest)       | 67    | 51 passed, 16 xfailed |
| Web Build          | —     | next build OK (10 Routes) |
| Mobile tsc         | —     | clean |
| **TOTAL**          | **92**| **92 passed** |

---

*Stand: 2026-04-09. Nächstes Update: Session 4.*
