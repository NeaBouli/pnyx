# Handover — Session 3 (2026-04-09)
# Ekklesia.gr / pnyx — Vendetta Labs Core Dev Team
# Copyright (c) 2026 Vendetta Labs — MIT License

---

## Was wurde gemacht?

### 1. Header-Bug gefixt (`6c5d943`)
**Problem:** Jede Seite hatte ein eigenes `<header>`-Element, obwohl `NavHeader` bereits im Locale-Layout (`[locale]/layout.tsx`) gerendert wird. Ergebnis: Doppelter Header auf allen Seiten ausser Home und Verify.

**Lösung:** 9 redundante `<header>` aus 7 Dateien entfernt:
- `bills/page.tsx` — Sub-Navigation (Results/Analytics/MP) in Page-Content verschoben
- `bills/[id]/page.tsx` — Back-Link als Inline-Element
- `vaa/page.tsx` — 3 Header (Intro/Quiz/Results Phase) entfernt
- `results/page.tsx`, `analytics/page.tsx`, `mp/page.tsx` — Back-Link + Titel inline
- `admin/page.tsx` — Logout-Button inline

**Verifiziert:** `next build` erfolgreich, alle Seiten kompilieren.

### 2. Tailwind 4 PostCSS-Migration (`c13640e`)
**Problem:** Tailwind CSS v4 hat den PostCSS-Plugin in ein separates Paket verschoben. Build schlug fehl mit: `The PostCSS plugin has moved to @tailwindcss/postcss`.

**Lösung:**
- `npm install @tailwindcss/postcss --save-dev --legacy-peer-deps`
- `postcss.config.mjs`: `tailwindcss: {}` → `"@tailwindcss/postcss": {}`
- `globals.css`: `@tailwind base/components/utilities` → `@import "tailwindcss"`

**Achtung:** npm install braucht `--legacy-peer-deps` wegen eslint Peer-Conflict.

### 3. Mobile Ed25519 Signing (`4a11089`)
**Problem:** `VoteScreen.tsx` sendete `"beta-unsigned"` als Signatur. Das Backend hätte alle Mobile-Votes mit `401 Unauthorized` abgelehnt.

**Lösung:**
- `@noble/curves` als Dependency in `apps/mobile/` installiert
- `crypto-native.ts` erweitert um:
  - `hexToBytes()` / `bytesToHex()` — Hex-Konvertierung
  - `signVote(privateKeyHex, {bill_id, vote, nullifier_hash})` — Ed25519 Signatur
  - `verifyVote(publicKeyHex, params, signatureHex)` — Lokale Verifikation
- `VoteScreen.tsx`: Echte Signatur + Self-Verify vor Submit
- `navigation/index.tsx`: `Result` Route akzeptiert optionales `billTitle`

**KRITISCHER BUG GEFIXT:** `computeNullifier()` verwendete `phone + salt` statt `phone + ":" + salt`. Der Python-Backend nutzt `f"{phone}:{salt}"`. Ohne den `:` hätten Mobile-Nullifier nicht mit dem Backend übereingestimmt → Nutzer hätten sich nicht verifizieren können.

### 4. Cross-Platform Krypto-Tests (`d84fb84`)
**Neue Datei:** `apps/web/src/lib/crypto-compat.test.ts` (12 Tests)

Testet die kritische Kompatibilität zwischen Web, Mobile und Python:
- JSON-Message-Format: Alphabetisch sortierte Keys, kompakt, uppercase Vote
- Sign/Verify Round-Trips mit generierten Keypairs
- Determinismus (Ed25519 RFC 8032)
- Forgery-Resistance (falscher Key → invalid)
- Tampering-Detection (geänderter bill_id/nullifier → invalid)
- Hex-Format-Validierung (64-char Keys, 128-char Signatures)

---

## Was wurde NICHT angefasst?

Gemäss Absprache: Alles was Kollisionsgefahr mit Server-Migration hat.

- Keine DB-Schema-Änderungen / Alembic Migrations
- Keine Docker/Traefik/Infra-Änderungen
- Keine CORS-Config-Änderungen
- Keine Redis-abhängigen Features
- Keine Environment/Secrets-Änderungen
- Keine neuen API-Endpoints

---

## Rollback

Falls etwas nicht stimmt:

```bash
# Komplett zurück auf pre-Session-3:
git reset --hard pre-session3-20260409

# Einzelne Commits rückgängig machen:
git revert d84fb84   # Tests + Docs
git revert 4a11089   # Mobile Ed25519
git revert c13640e   # Tailwind 4
git revert 6c5d943   # Header Fix
```

**Stash:** `stash@{0}: On main: pre-session3-stash-20260409-005835` enthält die vorherigen uncommitted Änderungen (CLAUDE.md, package-lock.json, .claude/, BACKLOG.md).

---

## Teststatus

```
Web:    29/29 passed (vitest)     — npx vitest run
Crypto: 12/12 passed (pytest)    — .venv/bin/python -m pytest tests/ (von packages/crypto/)
API:    51/51 passed + 16 xfail  — .venv/bin/python -m pytest tests/ (von apps/api/)
Mobile: tsc --noEmit clean       — npx tsc --noEmit (von apps/mobile/)
Build:  next build OK            — npx next build (von apps/web/)
```

---

## Dateien geändert (19 total)

### Web (11 Dateien)
| Datei | Änderung |
|-------|----------|
| `apps/web/postcss.config.mjs` | Tailwind 4 PostCSS Plugin |
| `apps/web/src/app/globals.css` | `@import "tailwindcss"` statt `@tailwind` |
| `apps/web/package.json` | +@tailwindcss/postcss |
| `apps/web/package-lock.json` | Lockfile aktualisiert |
| `apps/web/src/app/[locale]/bills/page.tsx` | Header entfernt, Sub-Nav inline |
| `apps/web/src/app/[locale]/bills/[id]/page.tsx` | Header entfernt, Back-Link inline |
| `apps/web/src/app/[locale]/vaa/page.tsx` | 3 Header entfernt (Intro/Quiz/Results) |
| `apps/web/src/app/[locale]/results/page.tsx` | Header entfernt |
| `apps/web/src/app/[locale]/analytics/page.tsx` | Header entfernt |
| `apps/web/src/app/[locale]/mp/page.tsx` | Header entfernt |
| `apps/web/src/app/[locale]/admin/page.tsx` | Header entfernt |

### Web Tests (1 neue Datei)
| Datei | Änderung |
|-------|----------|
| `apps/web/src/lib/crypto-compat.test.ts` | **NEU** — 12 Cross-Platform Krypto-Tests |

### Mobile (5 Dateien)
| Datei | Änderung |
|-------|----------|
| `apps/mobile/package.json` | +@noble/curves |
| `apps/mobile/package-lock.json` | Lockfile aktualisiert |
| `apps/mobile/src/lib/crypto-native.ts` | +signVote, +verifyVote, +hex utils, Fix computeNullifier |
| `apps/mobile/src/screens/VoteScreen.tsx` | Echte Ed25519 Signatur statt "beta-unsigned" |
| `apps/mobile/src/navigation/index.tsx` | Result Route + optionales billTitle |

### Docs (2 Dateien)
| Datei | Änderung |
|-------|----------|
| `CLAUDE.md` | Teststatus aktualisiert |
| `docs/TODO.md` | Session 3 dokumentiert, Session 4 Tasks |

---

## Nächste Schritte (Session 4)

### Priorität 1 — Vor erstem Launch
1. **Docker lokal starten** — `docker-compose up` + `alembic upgrade head` + `seed.py`
2. **E2E Test** — API lokal → Web lokal → Verify → Vote → Results (kompletter Flow)
3. **Git Push** — 4 Commits auf Remote pushen

### Priorität 2 — Qualität
4. **iOS/Android Build** — `eas build --platform all` testen
5. **Shared Types** — `packages/types/` für Web + Mobile API-Typen
6. **Next.js 15 Upgrade** — Löst eslint Peer-Conflict

### Priorität 3 — Features
7. **Wiki Ticker** → echte API-Daten statt Dummy
8. **MOD-16 Municipal** — Router-Implementierung
9. **WebSocket Live-Counter** für WINDOW_24H Bills

---

## Kontakt

- **Repo:** https://github.com/NeaBouli/pnyx
- **Org:** Vendetta Labs
- **Lizenz:** MIT

*Handover erstellt: 2026-04-09, nach Session 3.*
