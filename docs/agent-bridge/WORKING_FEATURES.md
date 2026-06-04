# WORKING FEATURES — Golden Path Registry

> **REGEL:** Bevor irgendeine dieser Funktionen oder ihre kritischen Dateien geändert werden,
> MUSS dieser Eintrag gelesen werden. Nach der Änderung MUSS jeder betroffene Punkt
> einzeln gegengeprüft werden. Kein Merge ohne Bestätigung dass der Golden Path intakt ist.

## Mobile App

| Feature | Status | Verifiziert | Commit | Kritische Dateien | Testart |
|---|---|---|---|---|---|
| Vote (NAI/OXI/ΑΠΟΧΗ) Signatur `bill_id:vote:nullifier` | ✅ | S10 01.06 | vC29 | VoteScreen.tsx, lib/crypto-native.ts, lib/api.ts | API + S10 |
| Already-voted Lock (Buttons ausgegraut) | ✅ | S10 03.06 | vC30 | VoteScreen.tsx | S10 |
| WINDOW_24H Korrektur (1x erlaubt) | ✅ | S10 03.06 | vC30 | VoteScreen.tsx | S10 |
| Forum-Fallback (`forum_topic_url`) in Detail | ✅ | S10 04.06 | 32d3085 | VoteScreen.tsx, ResultScreen.tsx, lib/api.ts | S10 |
| ANNOUNCED Bills klickbar + Read-only | ✅ | S10 01.06 | f23abec | BillsScreen.tsx, VoteScreen.tsx | S10 |
| Bill-Card Icons (💬↗✓⚖) | ✅ | S10 03.06 | vC30 | BillsScreen.tsx | S10 |
| PDF Source UX (📄 + Subtext) | ✅ | S10 04.06 | 00d4b2d | VoteScreen.tsx | S10 |
| Non-clickable Βουλή Fallback | ✅ | S10 04.06 | 9879328 | VoteScreen.tsx | S10 |
| POLIS Ticket List + Create | ✅ | S10 01.06 | vC29 | TicketsScreen.tsx | S10 |
| Evaluation /politicians/ | ✅ | API 01.06 | vC29 | EvaluatePoliticianScreen.tsx | API |
| Compass (2D + Εγγύτητα) | ✅ | S10 01.06 | vC29 | CompassScreen.tsx | S10 |
| Bill Loading Guard (kein Vote-Flash) | ✅ | S10 01.06 | 0225c00 | VoteScreen.tsx (`billLoaded`) | S10 |
| Summary Cascade (short → long → fallback) | ✅ | S10 03.06 | vC30 | VoteScreen.tsx | S10 |
| DIAVGEIA Source-Link | needs recheck | — | — | VoteScreen.tsx, source_links.py | S10 |

## Backend / API

| Feature | Status | Verifiziert | Commit | Kritische Dateien | Testart |
|---|---|---|---|---|---|
| Telegram Bot citizen_votes Count | ✅ | Live 01.06 | d6e4dfa | bill_lifecycle.py, telegram_community.py | Telegram |
| Telegram governance Topic-Routing | ✅ | Live 01.06 | d6e4dfa | bill_lifecycle.py, telegram_community.py | Telegram |
| Arweave Guards (PARLIAMENT + party_votes) | ✅ | DB 01.06 | b421b39 | bill_lifecycle.py, monitor.py | DB query |
| T3 Monitor Arweave (party_votes Guard) | ✅ | Telegram 02.06 | a90d508 | monitor.py | Monitor logs |
| Forum-Sync (alle 10 Min) | ✅ | DB 01.06 | 818c471 | discourse_sync.py, main.py | DB + Discourse |
| 4-Kanal-Fetcher Fallback (Jina→HTML→Ollama→Playwright) | ✅ | Code 03.06 | c1685b5 | parliament_fetcher.py | Code review |
| Quality-Gate (`_is_bad_parliament_text`) | ✅ | Code 03.06 | 9879328 | parliament_fetcher.py | Code review |
| Source-Policy (official_source_url computed) | ✅ | API 04.06 | 15b49c9 | source_links.py, parliament.py | API |
| Completeness-Job defensiv | ✅ | Code 03.06 | 15b49c9 | main.py | Code review |
| Bill Lifecycle Scheduler | ✅ | Live | — | bill_lifecycle.py | Monitor |

## Deploy-Regeln (nicht verhandelbar)

- Compose service: `api` (NICHT `ekklesia-api`)
- Env laden: `set -a && source /opt/ekklesia/.env.production && set +a`
- API stoppen ZUERST: `docker compose stop api` → build → `up -d api` (Race Condition)
- KEIN `docker cp` (ADR-010) — immer git pull + compose build
- `--env-file /opt/ekklesia/.env.production` bei compose up
- Ollama RAM: 2.4 GB Produktion, 12 GB nur temporär für qwen2.5:14b
- Kein `--apply` auf Backfill-Scripts ohne Sample-Abnahme

## Bekannte Defekte (NICHT fixen ohne Ticket + Bridge-Update)

| GH | Linear | Beschreibung |
|---|---|---|
| #102 | NEA-312 | 24h-Korrektur-Warntext bleibt |
| #103 | NEA-313 | Forum nur Summary, kein Volltext |
| #104 | NEA-314 | Deep-Link App vs Web |
| #105 | NEA-315 | Σύνοψη = Ανάλυση identisch |
| #106 | NEA-316 | Dark Cards Mobile unlesbar |
| #99 | — | DIAVGEIA Source-Link fehlt (VoteScreen) |
| #100 | — | DIAVGEIA zeigt pill statt Summary |
