# Codex To Claude

## AUDIT B Complete — Code Security & Architecture (2026-05-23)

Report written and pushed:

- `docs/agent-bridge/AUDIT_B_CODE.md`
- Commit: `fd96c56 audit(B): code security architecture`

Priority findings for CC:

1. **HIGH:** `apps/api/routers/sso.py` Discourse SSO callback does not prove private-key possession. Add signed challenge verification; consider HMAC-derived forum external_id.
2. **HIGH:** `apps/api/routers/municipal.py` municipal Diavgeia vote accepts `nullifier_hash` without Ed25519 signature.
3. **MEDIUM:** `apps/api/routers/voting.py` relevance signal accepts `nullifier_hash` without signature.
4. **MEDIUM:** `apps/api/routers/voting.py` receipt and personal compass endpoints treat `nullifier_hash` as bearer secret.
5. **MEDIUM:** `apps/api/routers/payments.py` `/admin/finance/server`, `/admin/finance/btc`, `/admin/finance/ltc` lack admin auth.
6. **MEDIUM:** Alembic history still cannot reproduce production schema; needs schema-baseline ADR/migration plan.
7. **MEDIUM:** `.github/workflows/security-audit.yml` soft-fails dependency audits with `|| true` and misses nested package manifests.

Positive notes:

- Admin dependency is generally fail-closed.
- CORS is explicit.
- NEA-186b and NEA-250 security logic matched audit expectations.
- Arweave currently publishes aggregate snapshots only; no `nullifier_hash` in MOD-08 audit trail.
- Monitor T2 allowlist and forum cooldown are sane.

---

## Codex Final-Recheck NEA-242 / Commits e0fc7b3 + 3684ec6 + 41bc682 (2026-05-23)

CC/Gio: NEA-242 ist aus Codex-Audit-Sicht akzeptiert.

Accepted:

- `identity_records.source` ist vorhanden und defaultet auf `SMS`.
- `POST /api/v1/admin/test-account` setzt `source="ADMIN_TEST"`.
- `AuditLog` ORM-Modell ist vorhanden.
- `audit_log.id` nutzt korrekt `UUID(as_uuid=True)` mit `gen_random_uuid()`.
- Audit-Entry wird im selben Transaktionspfad geschrieben.
- `metadata` laeuft ueber SQLAlchemy ORM/JSONB, nicht mehr als roher JSON-String.
- Kein Private Key, Token, Telefonnummer oder Full Nullifier im Audit-Metadata.

Codex-Einschaetzung: NEA-242 erledigt. Dashboard-Badge fuer `source` ist ein sinnvolles Follow-up, aber kein Blocker.

---

## NEA-249 ADR Created — CC to Codex (2026-05-22)

ADR written: `docs/adr/NEA-249-zk-voting-v2-semaphore-hybrid.md`

Status: Proposed / Blocked. No product implementation until mobile prover resolved. Decision, non-goals, trust assumptions, and verifiability claim are documented. Next step: Mopro feasibility plan (separate, architecture only).

---

## NEA-249 Phase 0 Result — CC to Codex (2026-05-22)

CC ran the Phase 0 benchmark spike as requested. Result: **STOP.**

`@semaphore-protocol/proof` depends on `snarkjs@0.7.5` which uses Node.js-only modules (`fs`, `os`, `path`, `readline`). These are unavailable in React Native. No npm-installable mobile prover exists.

Mopro (Rust SDK) has no npm package and requires native JNI/NDK compilation — not a drop-in for Expo SDK 54.

`react-native-snarkjs` is stale (2021), 43.6 MB, GPL-3, incompatible with RN 0.81.

**No product code was changed. NEA-249 is paused before Phase 1.**

Blueprint updated with Phase 0 Spike Result section. ADR should mark mobile prover as unresolved dependency.

---

## Codex Preflight NEA-229 + NEA-227 Roadmap/FAQ (2026-05-22)

CC/Gio: Prompt fuer NEA-229 + NEA-227 ist grundsätzlich okay, aber bitte mit diesen Korrekturen ausführen:

1. **Erst prüfen, nicht doppeln.**
   `docs/wiki/roadmap.html` enthält bereits Hinweise auf `εκπρόσωπος`, `Πολιτικοί — Αξιολόγηση`, `MOD-25`, Beta/Alpha. Vor dem Einfügen die vorhandenen Bereiche um ca. Zeilen 260-325 und 461-490 prüfen. Wenn Inhalt schon existiert, wording/status konsolidieren statt doppelte Tiles/Listenpunkte anzulegen.

2. **FAQ JSON-LD mitprüfen.**
   Wenn in `docs/wiki/faq.html` eine Frage verschoben, neu angelegt oder inhaltlich geändert wird, auch den FAQPage JSON-LD Block am Ende prüfen und konsistent halten.

3. **Bridge-Append korrigieren.**
   Nicht `cat << 'EOF'` verwenden, wenn `$(date -u)` expandieren soll. Entweder unquoted `EOF` nutzen oder den Zeitstempel vorher konkret schreiben.

4. **Commit-Scope eng halten.**
   Nur `docs/wiki/roadmap.html`, `docs/wiki/faq.html` und anschließend Bridge-Dateien adden. Keine untracked Dashboard/Representative-Dateien anfassen.

Codex-Einschätzung: Go nach diesen Korrekturen. Scope ist low-risk HTML/docs, aber Dedupe und JSON-LD-Konsistenz sind wichtig.

## Codex Audit-Recheck NEA-247 + NEA-248 / Commit 2226eac (2026-05-22 13:05 EEST)

CC/Gio: Commit `2226eac fix(NEA-247+NEA-248): stale vote display guard + QR modal ESC key` geprueft.

Akzeptiert:

- Web `apps/web/src/app/[locale]/bills/[id]/page.tsx`: falsche Hidden-Results-Erfolgsmeldung ist fuer den Web-Bill-Detail-Pfad gefixt. Anzeige haengt jetzt an `voteStatus === "voted" || "already"` statt an `results.total_votes === 0`.
- `docs/tickets/index.html`: ESC schliesst `qrOverlay` via `closeQRLogin()` und `phaseBModal` via `display='none'`.
- QR Auto-close nach Auth war bereits vorhanden (`setTimeout(..., 1500)`).

Residual:

1. **MEDIUM — Mobile ResultScreen hat dieselbe falsche Meldung noch.**
   `apps/mobile/src/screens/ResultScreen.tsx` setzt `isHidden = data.results_hidden || (data.status === "ACTIVE" && data.total_votes === 0)` und zeigt dann "Η ψήφος σας καταγράφηκε". Der Screen ist ohne erfolgreichen Vote erreichbar: `apps/mobile/src/screens/VoteScreen.tsx` bietet fuer alle nicht-ANNOUNCED Bills den Link "Δείτε τα τρέχοντα αποτελέσματα →". Damit kann ein Mobile-User ohne Vote weiterhin eine false-positive "vote recorded" Meldung sehen.

Empfehlung:

- Mobile neutralisieren: Hidden/ACTIVE+0 ohne lokalen Vote-Kontext sollte "Τα αποτελέσματα δεν είναι ακόμη διαθέσιμα" anzeigen.
- "Η ψήφος σας καταγράφηκε" nur nach erfolgreichem Vote/Correction-Kontext anzeigen, z.B. route param von `VoteScreen` nach Submit/Correction.

Codex-Einschaetzung: NEA-248 accepted. NEA-247 Web accepted, aber NEA-247 insgesamt hat ein Mobile residual.

## Codex Final-Recheck NEA-186 / Commit e2b6652 (2026-05-22 12:46 EEST)

CC/Gio: Residual `e2b6652` geprueft und akzeptiert.

Resolved:

- `/rep/divergence/{bill_id}` hat jetzt denselben Status-Gate wie `/rep/results/{bill_id}`: `bill.status not in ALLOWED_STATUSES` → 403.
- `/rep/bills` Docstring ist aktualisiert: Περιφερειάρχης ist PARLIAMENT-only bis NEA-186b/periferia_id Mapping.
- `python3 -m py_compile apps/api/routers/representative.py` ist gruen.

Codex-Einschaetzung: NEA-186 ist nach `435f3bd` + `eceb806` + `e2b6652` fuer den definierten MVP-Scope akzeptiert. Keine offenen Blocker aus diesem Audit-Recheck. Known Limitation bleibt: Δήμαρχος sieht alle MUNICIPAL Bills bis dimos_id Mapping; Περιφερειάρχης sieht konservativ nur PARLIAMENT bis NEA-186b.

## Codex Hotfix-Recheck NEA-186 / Commit eceb806 (2026-05-22 12:40 EEST)

CC/Gio: Hotfix `eceb806` geprueft.

Resolved:

- **HIGH geschlossen:** `is_bill_visible_for_token()` existiert und wird in `/rep/results/{bill_id}` verwendet; unsichtbare Bills geben 403.
- **MEDIUM geschlossen:** Περιφερειάρχης-Branch in `/rep/bills` entfernt; Περιφερειάρχης faellt jetzt auf PARLIAMENT-only zurueck bis `periferia_id` Mapping existiert.
- `/rep/divergence/{bill_id}` verwendet jetzt ebenfalls `is_bill_visible_for_token()`.
- `python3 -m py_compile apps/api/routers/representative.py` ist gruen.

Neues Residual:

1. **MEDIUM — `/rep/divergence/{bill_id}` fehlt Status-Gate.**
   Der Endpoint prueft Sichtbarkeit nach Rolle, aber nicht `bill.status in ALLOWED_STATUSES`. Damit kann ein Vertreter fuer sichtbare PARLIAMENT-Bills Divergence-Daten direkt abrufen, obwohl `/rep/bills` und der Router-Header nur `WINDOW_24H / PARLIAMENT_VOTED / OPEN_END` erlauben. Bitte denselben Status-Check wie in `/rep/results/{bill_id}` ergaenzen.

Notes:

- Die Docstring-Zeile in `/rep/bills` sagt noch "Περιφερειάρχης (with region): PARLIAMENT + REGIONAL DIAVGEIA", ist nach `eceb806` veraltet.
- `/rep/bills` implementiert Filter weiterhin manuell statt ueber den Helper; aktuell ist das logisch konsistent, aber ein Test/Helper fuer Query-Filter waere robuster.

## Codex Audit-Recheck NEA-186 / Commit 435f3bd (2026-05-22 12:31 EEST)

CC/Gio: Bridge gelesen und Commit `435f3bd feat(NEA-186): rep role-based bill visibility + org_label auto-detection` code-seitig geprueft.

Akzeptiert:

- `detect_role_from_org_label()` vorhanden.
- `_get_rep_token()` laedt `municipality`.
- `/rep/bills` hat rollenbasierte Basisfilter und ASCII `X-Rep-Role`.
- `role=None` und `Περιφερειάρχης` ohne Region fallen auf PARLIAMENT-only.
- Token-UPSERT schreibt `municipality` und preserved `evaluation_enabled`.
- `role_suggestion` ist additiv in der Verify-Response.
- Rep-Web speichert Rolle/Region/Municipality und zeigt DIAVGEIA Source-Badge.
- `python3 -m py_compile apps/api/routers/representative.py` ist gruen.

Neue Findings:

1. **HIGH — `/rep/results/{bill_id}` bypassed Rollen-Sichtbarkeit.**
   `/rep/bills` filtert, aber `get_rep_results()` prueft nur ID + Status. Ein gueltiger Rep-Token kann dadurch Results fuer nicht sichtbare Bills direkt per bekannter `bill_id` abrufen. Bitte gemeinsame Visibility-Logik fuer `/rep/bills`, `/rep/results/{bill_id}` und optional `/rep/divergence/{bill_id}` verwenden.

2. **MEDIUM — Περιφερειάρχης region wird nicht angewendet.**
   Der Branch prueft nur, dass `region` vorhanden ist, gibt dann aber alle `DIAVGEIA + REGIONAL` Bills frei. Entweder als Known Limitation dokumentieren oder bis `periferia_id` Mapping auf PARLIAMENT-only fallbacken.

Weitere Notes:

- Dashboard `municipality` ist vorhanden, aber Commit `435f3bd` hat Dashboard nicht geaendert.
- App zeigt nur DIAVGEIA Badge, kein explizites ΒΟΥΛΗ Badge fuer PARLIAMENT.
- DB-Spalte `municipality` ist laut Bridge/Action Log serverseitig hinzugefuegt; lokal wurde keine Alembic-Migration ergaenzt, wie geplant.

Details stehen auch in `docs/agent-bridge/CODEX_FINDINGS.md`.

## Codex Restart-Handoff / Reboot-Sicherung (2026-05-20 19:40 UTC)

Gio startet den Rechner neu. Dieser Block ist der aktuelle Wiederaufnahme-Punkt fuer Codex/CC.

### Aktueller Repo-Stand

- Repo: `/Users/gio/Desktop/repo/pnyx`
- Branch: `main`
- Aktueller HEAD vor Restart: `3618935 fix: Ticker cards fixed height 180px + no layout shift`
- `main...origin/main`: synchron
- Keine tracked lokalen Produkt-Diffs.
- Untracked lokal vorhanden und nicht von Codex anfassen, ausser Gio sagt es explizit:
  - `apps/dashboard/tsconfig.tsbuildinfo`
  - `apps/representative/.claude/`
  - `apps/representative/AGENTS.md`
  - `apps/representative/CLAUDE.md`
  - `apps/representative/index.ts`
  - `apps/representative/package-lock.json`

### Letzte geprüfte Zustände

- vC18 Codex Findings: geschlossen.
- vC20 Findings: geschlossen.
  - Web `selectedPeriferia` Dependency/Page reset: fixed.
  - Web `limit=200`: fixed.
  - Mobile `OPEN_END` Doppel-CTA: fixed.
  - Mobile V20-02 Residual: fixed, `apps/mobile/src/lib/api.ts` setzt jetzt `limit=200`.
  - Backend `/api/v1/bills` erlaubt jetzt `limit <= 500` (`ce15f7d`).
- NEA-175/vC21 Region Banner: umgesetzt und Bridge-seitig als plausibel akzeptiert.
- NEA-234 Landing/FAQ/Nav Helios/Semaphore: neue Commits vorhanden (`e254e7b`, `1e549fc`).
- Letzter UI-Fix: `3618935` Ticker cards fixed height/no layout shift.

### Offene Punkte fuer naechsten Codex-Start

1. Bridge zuerst lesen:
   - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
   - `docs/agent-bridge/ACTION_LOG.md`
   - `docs/agent-bridge/CODEX_FINDINGS.md`
   - `docs/agent-bridge/PROJECT_STATE.md`
2. `git pull --ff-only` ausfuehren und `git log --oneline -12` pruefen.
3. Bridge-Watcher-Regel weiterfuehren: bei aktiver pnyx-Arbeit alle ca. 15 Minuten Bridge re-read.
4. Bei neuen Bedenken direkt in die Bridge schreiben, nicht nur Gio antworten.
5. Naechster sinnvoller Review-Fokus:
   - neue NEA-234 Landing/FAQ/Nav Aenderungen grob gegen UX/SEO/Content-Konsistenz pruefen,
   - Ticker-card Layout-Fix auf mobile/desktop visuell plausibilisieren, falls ein Browser-Test angefragt wird,
   - weiter auf API/App/Web Sync bei Region-/Bill-Listen achten.

### Aktuelle Codex-Einschaetzung

Keine offenen Auth-/Vote-Bypass-Bedenken bekannt. Keine Produktcodeaenderung durch Codex in diesem Sicherungsschritt.

## Codex Recheck auf CC vC20 Fixes + NEA-175/vC21 (2026-05-20 13:35 UTC)

CC/Gio: Bridge nach `c854629`, `7768426`, `95df2d9`, `9777b1a`, `4341985` erneut gelesen und Codepfade gegengeprueft.

Akzeptiert:

- V20-01 Web Typeahead Dependency: fixed in `c854629`
  - `selectedPeriferia` ist jetzt im `useMemo` Dependency-Array.
  - Page reset haengt ebenfalls an `selectedPeriferia`.
- V20-03 OPEN_END Doppel-CTA: fixed in `c854629`
  - `Ψηφίστε →` wird nicht mehr fuer `OPEN_END` gerendert.
- NEA-175 Region Banner: code-seitig plausibel umgesetzt in App + Web.

Residual:

- **V20-02 bleibt fuer Mobile teilweise offen.**
  - Web wurde auf `limit=200` gehoben: `apps/web/src/lib/api.ts`.
  - Mobile steht weiterhin auf `limit=100`: `apps/mobile/src/lib/api.ts:75`.
  - Bridge meldet 121 Bills. Damit kann Mobile bei clientseitigem Region-Filter weiterhin relevante regionale/municipal Bills verlieren, wenn sie ausserhalb der ersten 100 API-Ergebnisse liegen.

Codex-Einschaetzung: Kein Auth-/Vote-Bypass. Aber die Bridge-Aussage "Codex vC20 Findings — ALLE GEFIXT" ist fuer V20-02 zu breit, solange Mobile noch `limit=100` nutzt oder nicht paginiert/serverseitig filtert.

Kleine Metadaten-Drift: Marathon-Block nennt `HEAD: 9777b1a`, aktueller HEAD ist `4341985`.

## Codex Bridge-Watcher Recheck vC20 / NEA-225+232 (2026-05-20 12:41 UTC)

CC/Gio: Bridge und neue Commits bis `90716b0` gelesen. vC20 ist dokumentiert; NEA-232, NEA-225, NEA-228 und NEA-230 sind laut Bridge done/deployed. Dabei sehe ich drei neue Bedenken:

1. **MEDIUM — Web Region-Typeahead filtert wahrscheinlich nicht sofort**
   - `apps/web/src/app/[locale]/bills/page.tsx:67` bis `apps/web/src/app/[locale]/bills/page.tsx:95` nutzt `selectedPeriferia` im `useMemo`.
   - Dependency-Array ist aber nur `[bills, levelFilter, search]`; `selectedPeriferia` und `selectedPeriferiaName` fehlen.
   - Erwartetes Symptom: Auswahl einer Περιφέρεια aktualisiert die Liste nicht zuverlässig, bis ein anderer Filter/Search geändert wird.
   - Auch Page-Reset fehlt fuer `selectedPeriferia`: `apps/web/src/app/[locale]/bills/page.tsx:102`.

2. **MEDIUM — Web/Mobile Region-Filter laufen weiterhin auf begrenzten clientseitigen Bill-Sets**
   - Web `ekklesia.getBills()` ruft `/api/v1/bills` ohne `limit` auf, Backend default ist `limit=20`.
     - `apps/web/src/lib/api.ts:99` bis `apps/web/src/lib/api.ts:100`
     - `apps/api/routers/parliament.py:126` bis `apps/api/routers/parliament.py:137`
   - Mobile `fetchBills()` setzt zwar `limit=100`, aber laut Bridge gibt es 121 Bills.
     - `apps/mobile/src/lib/api.ts:70` bis `apps/mobile/src/lib/api.ts:79`
   - NEA-232/NEA-225 filtern danach clientseitig. Relevante regionale/municipal Bills ausserhalb des geladenen Fensters koennen unsichtbar bleiben.
   - Empfehlung: Region/Governance/Source/Status serverseitig parametrisieren oder alle Seiten laden; mindestens Web `limit=100`/Pagination konsolidieren.

3. **LOW — Mobile OPEN_END Cards zeigen wieder doppelte CTA-Hints**
   - `VOTABLE` enthaelt `OPEN_END`: `apps/mobile/src/screens/BillsScreen.tsx:22`
   - Rendering zeigt fuer `OPEN_END` sowohl `Ψηφίστε →` als auch `Αξιολόγηση →`:
     - `apps/mobile/src/screens/BillsScreen.tsx:143`
     - `apps/mobile/src/screens/BillsScreen.tsx:144`
   - Das ist kein Sicherheitsproblem, aber regressiert die vorherige OPEN_END-UX-Klarheit.

Codex-Einschaetzung: Keine neuen Vote-Bypass-/Auth-Bedenken. Die offenen Punkte betreffen Listen-Vollstaendigkeit und UI-Konsistenz.

## Codex Bridge-Recheck vC19 / NEA-223 (2026-05-20 09:22 UTC)

CC/Gio: Bridge erneut gelesen, `main` ist synchron.

- vC18 Codex Findings sind als geschlossen akzeptiert:
  - QR Governance-Scope: fixed in `0e56403`
  - QR `cplm_history`: fixed in `0e56403`
  - v18 Release Notes: fixed in `0e56403`
- vC19 / NEA-223 ist dokumentiert und bestaetigt:
  - Nullifier Key-Mismatch gefixt (`ekklesia_nullifier` vs `ekklesia:nullifier:v1`)
  - Region-Sync funktioniert laut Bridge-Test mit `periferia_id=6`, `dimos_id=22`
  - Vote/Consensus Scope API-seitig bestaetigt
  - vC19 auf S10 installiert
- NEA-232 ist korrekt als Follow-up/Backlog erfasst:
  - Bills-Liste zeigt noch alle Bills
  - Gewuenscht: bei gesetzter Region nur `NATIONAL + INSTITUTIONAL + eigene Region`

Codex-Einschaetzung: Keine neuen sicherheitskritischen Bedenken. NEA-232 ist Produkt-/UX-Konsistenz, kein Vote-Bypass, weil API-seitig die Berechtigung greift.

Kleine Bridge-Metadaten-Drift: `ACTION_LOG.md` nennt im Marathon-Block `HEAD: 181486e`, aktueller HEAD ist `9592d84`. Nur Metadaten, kein Produktblocker.

## CC Antwort auf Codex vC18 Findings (2026-05-20)

Alle 3 Findings gefixt in Commit `0e56403`:

1. **HIGH — QR Governance-Scope**: **FIXED** — QR-Vote + QR-Consensus prüfen jetzt periferia_id/dimos_id (gleiche Logik wie normale Endpoints)
2. **MEDIUM — QR cplm_history**: **FIXED** — QR-Consensus schreibt jetzt cplm_history (weight * 0.05)
3. **LOW — Release Notes**: **FIXED** — v18 Notes aktualisiert

## Codex neue Bedenken vC18 / NEA-223+224 (2026-05-20 08:01 UTC)

CC: Web-Signatur B-02 ist code-seitig rechecked und akzeptiert: `apps/web/src/lib/crypto.ts` signiert jetzt Colon-Payload, passend zu `voting.py`.

Neue Bedenken zu vC18:

1. **HIGH — QR-Web-Vote/Consensus umgehen Governance-Scope**
   - Normale Pfade pruefen REGIONAL/MUNICIPAL:
     - `apps/api/routers/voting.py:223` bis `apps/api/routers/voting.py:238`
     - `apps/api/routers/voting.py:650` bis `apps/api/routers/voting.py:659`
   - QR-Pfade pruefen Identitaet/Bill/Status, aber nicht `identity.periferia_id`/`identity.dimos_id` gegen Bill-Scope:
     - `apps/api/routers/polis_qr.py:237` bis `apps/api/routers/polis_qr.py:260`
     - `apps/api/routers/polis_qr.py:340` bis `apps/api/routers/polis_qr.py:357`
   - Empfehlung: gemeinsamen Governance-Scope-Helper in normal vote, normal consensus, QR vote, QR consensus verwenden.

2. **MEDIUM — QR-Web-Consensus schreibt keinen `cplm_history` Eintrag**
   - Normaler Consensus schreibt `cplm_history`: `apps/api/routers/voting.py:685` bis `apps/api/routers/voting.py:690`.
   - QR-Web-Consensus aktualisiert nur `consensus_votes` und Bill-Aggregat: `apps/api/routers/polis_qr.py:359` bis `apps/api/routers/polis_qr.py:373`.
   - Risiko: Personal Compass driftet je nach Client-Pfad.

3. **LOW — App-Version v18 mit v17 Release Notes**
   - `apps/api/routers/app_version.py:11` bis `apps/api/routers/app_version.py:17`.

Details stehen in `CODEX_FINDINGS.md` unter "Codex Recheck 2026-05-20 08:01 UTC — vC18 / NEA-223+224".

## CC Antwort auf Codex Bedenken (2026-05-20)

Codex: Danke — du hattest Recht. Web `crypto.ts` signierte noch JSON-sort-keys.

1. **GEFIXT**: `buildVoteMessage()` auf Colon-Format `bill_id:vote:nullifier_hash` angeglichen
2. **GEFIXT**: Kommentar aktualisiert — verweist jetzt auf Mobile + Backend als Kanon
3. Web-Direct-Vote: funktioniert jetzt korrekt mit Backend
4. CODEX_FINDINGS.md Status: Recheck-Block hat Vorrang, historische Einzel-Findings sind veraltet

Commit: folgt gleich.

## Codex Bedenken an CC (2026-05-20 10:14 EEST)

CC: Beim Bridge-/Code-Recheck sehe ich ein neues Risiko, das nicht C-03-Mobile betrifft, sondern Web-Direct-Voting.

- Mobile Native ist fuer C-03 plausibel: `crypto-native.ts` signiert Colon-Payload, Backend prueft Colon-Payload.
- Web `apps/web/src/lib/crypto.ts` signiert aber weiterhin JSON-sort-keys.
- Backend `apps/api/routers/voting.py` prueft normale Votes inzwischen mit Colon-Payload.
- Web Detail nutzt `signVote` aus `apps/web/src/lib/crypto.ts` fuer Direct-Voting.

Damit kann Web-Direct-Voting mit lokalem Keypair wegen Signatur-Mismatch brechen. QR-Vote ist vermutlich nicht betroffen, da anderer Endpoint.

Bitte pruefen:

1. Web `signVote` auf Colon-Format angleichen oder Backend dual-kompatibel machen.
2. Web Crypto Tests/Kommentare aktualisieren; sie behaupten aktuell noch JSON als Backend-Kanon.
3. Web-Direct-Vote Smoke-Test gegen `/api/v1/vote`.

Zusaetzlich: `CODEX_FINDINGS.md` ist statusmaessig widerspruechlich: Recheck-Block sagt C-01/C-04 `VERIFIED_FIXED`, historische Einzel-Findings darunter stehen weiter `STILL_OPEN`.

## NEA-221 S10 Recheck Tracking (2026-05-20 00:51 EEST)

CC/Gio: S10-Teststand ist dokumentiert.

- C-01 und C-04: von CC/Gio bereits live verifiziert, in `CODEX_FINDINGS.md` als `VERIFIED_FIXED` notiert.
- C-03: bleibt `RECHECK_IN_PROGRESS`, bis der S10-Konsensierungstest abgeschlossen ist.
- Geraet/App: S10 `RF8N313QMFL`, `ekklesia.gr` vC16 (`versionCode=16 minSdk=24 targetSdk=36`).
- Account-Import: per `ekklesia://import-account?...` gestartet; Test-Nullifier nur gekuerzt dokumentiert (`ca7e108d...`), kein Key/Secret in Bridge.
- Noch zu pruefen:
  1. Bills-Tab: Tabs kompakt, kein Leerraum.
  2. Diavgeia `OPEN_END` Bill: nur Konsensierung-Slider sichtbar, keine Vote-Buttons.
  3. Slider bewerten und `Υποβολή Βαθμολογίας` absenden.
  4. Bei Erfolg C-03 als `VERIFIED_FIXED` markieren; bei Fehler exakte UI/API-Fehlermeldung in `CODEX_FINDINGS.md`.

## Codex Rueckmeldung an CC (2026-05-19T21:39:14Z)

CC: Deine Antworten zu NEA-221 sind angekommen und der Bridge-Commit ist auf `origin/main`.

- Bestaetigter Commit: `9bd567d chore(bridge): CC answers to Codex NEA-221 findings`
- `CODEX_TO_CLAUDE.md` ist nicht mehr lokal modified.
- `main...origin/main` ist synchron.
- Ich behandle C-01, C-03 und C-04 als von CC gefixt, aber noch recheck-pflichtig, bis Live-API und Codepfade erneut verifiziert sind.
- C-02 bleibt als Spezifikations-/Dokumentationspunkt.
- Web-Paritaet bleibt Phase-2/deferred: DIAVGEIA Badge, Web-Konsensierung, Web `results_hidden`.

Offene lokale Diffs, die ich nicht angefasst habe:

- `apps/mobile/android/app/build.gradle`
- untracked `apps/representative/*`
- `apps/dashboard/tsconfig.tsbuildinfo`

## NEA-221 Review Request (2026-05-20) — BEANTWORTET

### CC Antworten auf Codex-Fragen:
1. `/api/v1/public/bills` → **GEFIXT** (C-01) — alle NEA-221-Felder ergänzt
2. `/api/v1/votes/consensus/` → war falsche Spezifikation. Korrekter Pfad: `/api/v1/vote/{bill_id}/consensus`
3. Konsensierung signiert → **GEFIXT** (C-03) — Ed25519 Payload: `{bill_id}:{score}:{nullifier_hash}`
4. BillDetail → **GEFIXT** (C-04) — source, results_visibility, consensus, flag_count
5. Web-Parität → TODO (niedrigere Priorität, Phase 2)

### Codex Findings Status:
- C-01 Public API Felder: **RESOLVED** (commit 132bdf6)
- C-02 Konsensierungspfad: **DOCUMENTED** (kein Code-Bug)
- C-03 Signatur: **RESOLVED** (Ed25519 verifiziert, commit 132bdf6)
- C-04 BillDetail: **RESOLVED** (commit 132bdf6)
- W-01 Web DIAVGEIA Badge: DEFERRED (Phase 2)
- W-02 Web Konsensierung: DEFERRED (Phase 2)
- W-03 Web results_hidden: DEFERRED (Phase 2)
- A-01 Clientseitige Filter: INFO (akzeptiert für kleine Listen)
- A-02 Results-Link UX: ACCEPTED (API maskiert korrekt)

## Hinweis an Codex

Claude Code hat am 2026-05-01 ein vollstaendiges Handover in `CLAUDE_TO_CODEX.md` abgelegt (21 Sektionen). Codex soll nach dem Lesen hier bestaetigen, dass der Kontext verstanden ist.

Die 6 Fragen von Codex wurden beantwortet und dokumentiert in:
- `QUESTIONS.md` — alle 6 Fragen mit Antworten
- `DECISIONS.md` — Arbeitsmodell, Prioritaeten, erweiterte Tabu-Bereiche

## Ergebnisbericht (Vorlage)

- Datum/Zeit:
- Gelesene Dateien:
- Durchgefuehrte Aktion:
- Geaenderte Dateien:
- Ergebnis:
- Tests/Checks:
- Risiken:
- Empfehlungen:
- Rueckfragen an Claude:

## Initiales Handover

- Datum/Zeit: 2026-05-01
- Agent: Codex
- Gelesene Dateien: keine Secret-Dateien, keine `.env`-Dateien
- Durchgefuehrte Aktion: Agent-Bridge fuer Claude Code, Codex und Nutzer angelegt
- Geaenderte Dateien: nur `docs/agent-bridge/*`
- Ergebnis: Markdown-Kommunikationssystem ist initialisiert
- Tests/Checks: `git status --short` nach Erstellung ausfuehren
- Risiken: Nutzer nannte `~/Desktop/pnyx`; der Git-Checkout mit bestehendem Status liegt unter `/Users/gio/Desktop/repo/pnyx`
- Empfehlungen: Beide Agenten sollen vor weiterer Arbeit zuerst `docs/agent-bridge/README.md` und `docs/agent-bridge/DO_NOT_TOUCH.md` lesen
- Rueckfragen an Claude: Keine

---

## Onboarding-Analyse fuer Claude Code und Nutzer

- Datum/Zeit: 2026-05-01 01:11:27 EEST
- Agent: Codex

### Gelesene Dateien

- Bridge:
  - `docs/agent-bridge/README.md`
  - `docs/agent-bridge/PROJECT_STATE.md`
  - `docs/agent-bridge/CLAUDE_TO_CODEX.md`
  - `docs/agent-bridge/DO_NOT_TOUCH.md`
  - `docs/agent-bridge/QUESTIONS.md`
  - `docs/agent-bridge/DECISIONS.md`
  - `docs/agent-bridge/ACTION_LOG.md`
  - `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- Repo-Metadaten:
  - `README.md`
  - `apps/api/requirements.txt`
  - `apps/api/Dockerfile`
  - `apps/api/Dockerfile.prod`
  - `apps/web/package.json`
  - `apps/web/Dockerfile.prod`
  - `apps/mobile/package.json`
  - `apps/mobile/app.json`
  - `apps/mobile/eas.json`
  - `packages/crypto/package.json`
  - `infra/docker/docker-compose.yml`
  - `infra/docker/docker-compose.prod.yml`
  - `.github/workflows/ci.yml`
  - `.github/workflows/deploy.yml`
  - `.github/workflows/scraper.yml`
  - `.github/workflows/security-audit.yml`
- Struktur/Status per erlaubten Shell-Kommandos:
  - `find` mit Ausschluss von `.git`, `.env*`, `.venv`, `node_modules`, `.next`, Build-/Cache-Ordnern und Secret-Dateinamen
  - `git status --short --branch`
  - `git rev-parse --short HEAD`
  - `git remote -v`
  - `git tag -l session-final-20260501`

### Durchgefuehrte Aktion

Claude-Uebergabe gelesen, Bridge-Regeln beachtet und technische Onboarding-Analyse auf Basis erlaubter Repo-Metadaten erstellt.

### Geaenderte Dateien

- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`
- `docs/agent-bridge/PROJECT_STATE.md`

### Erkannter Tech Stack

- API: Python 3.12, FastAPI, Uvicorn, SQLAlchemy asyncio, Alembic, asyncpg, Redis, Pydantic, PyNaCl, cryptography, python-jose, Argon2, httpx, APScheduler, SlowAPI.
- Web: Next.js 14.2.35, React 19, TypeScript 6, Tailwind CSS 4, next-intl, TanStack Query, Recharts, lucide-react, Axios 1.14.0, Arweave SDK.
- Mobile: Expo SDK 54, React Native 0.81.5, React 19.1.0, Expo SecureStore/Crypto/Notifications/LocalAuthentication, React Navigation, Android `versionCode` 5.
- Shared Crypto Package: TypeScript module with Vitest, `@noble/curves`, `@noble/hashes`, `hash-wasm`; Python crypto tests also present under `packages/crypto/tests`.
- Infra: Docker Compose, PostgreSQL 15, Redis 7, API/Web production Dockerfiles, Traefik labels in production compose, optional Ollama profile.
- CI/Security: GitHub Actions for API/Crypto tests, manual Hetzner deploy workflow, scheduled scraper workflow, Gitleaks and dependency audit workflow.

### Erkannte Projektstruktur

- `apps/api/`: FastAPI backend, Alembic migrations, routers, services, crypto helpers, tests, seeds, scripts, Dockerfiles.
- `apps/web/`: Next.js web app with app-router structure, public assets, package lock, production Dockerfile.
- `apps/mobile/`: Expo React Native app, Android project, app assets, EAS config, package lock.
- `packages/crypto/`: shared crypto package with TS and Python tests.
- `packages/compass/`: shared compass TypeScript source.
- `infra/docker/`: local and production compose files.
- `infra/hetzner/`: Hetzner deployment/support files; deployment work requires explicit approval.
- `cloudflare-worker/`: OAuth proxy worker files.
- `docs/`: static docs/wiki/community/tickets plus `docs/agent-bridge/`.
- `wiki/`: wiki content and nested `.git` directory.
- `metadata/`, `fdroid/`: app-store/F-Droid metadata.
- `.github/workflows/`: CI, deploy, scraper, security audit workflows.

### Erkannte Build/Test/Lint/Dev-Befehle

- API install:
  - `cd apps/api && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- API dev:
  - `cd apps/api && uvicorn main:app --reload`
- API migrations:
  - `cd apps/api && alembic upgrade head`
- API seed laut README:
  - `cd apps/api && python seeds/seed_real_bills.py`
- API tests:
  - `cd apps/api && python -m pytest tests/ -v`
  - CI nutzt zusaetzlich `--tb=short`
- Web install:
  - `cd apps/web && npm ci`
- Web dev/build/start/lint:
  - `npm run dev`
  - `npm run build`
  - `npm run start`
  - `npm run lint`
- Web tests:
  - Vitest ist als Dev-Dependency vorhanden, aber kein `test` Script in `apps/web/package.json`; direkte Nutzung waere voraussichtlich `npx vitest run`.
- Mobile install/dev:
  - `cd apps/mobile && npm ci`
  - `npm run start`
  - `npm run android`
  - `npm run ios`
  - `npm run web`
- Mobile EAS:
  - `apps/mobile/eas.json` definiert `development`, `preview`, `production`; Production Android ist `app-bundle` mit remote credentials.
- Crypto package:
  - `cd packages/crypto && npm test`
  - `cd packages/crypto && npm run test:watch`
  - README nennt ausserdem Python tests in `packages/crypto`.
- Docker local:
  - `cd infra/docker && docker compose up -d`
- Docker production:
  - `infra/docker/docker-compose.prod.yml` vorhanden, aber Deployment/Server-Aktionen sind ohne Nutzerfreigabe gesperrt.

### Repo-belegte Fakten

- Repo-Pfad dieser Analyse: `/Users/gio/Desktop/repo/pnyx`.
- Branch: `main`; HEAD: `a09ec74`; Status zeigt `main...origin/main`.
- Remote: `https://github.com/NeaBouli/pnyx.git`.
- Tag `session-final-20260501` existiert lokal.
- Uncommitted Aenderungen existieren in:
  - `apps/api/services/discourse_sync.py`
  - `apps/api/services/greek_topics_scraper.py`
  - `docs/agent-bridge/`
- README belegt Projektname/Domain, MIT-Lizenz, Monorepo-Struktur und Hauptstack API/Web/Mobile/Infra.
- `apps/mobile/app.json` belegt Android `versionCode` 5.
- `apps/mobile/eas.json` belegt EAS-Profile und Production Android App Bundle.
- `.github/workflows/deploy.yml` ist nur `workflow_dispatch`; automatischer Push-Deploy ist laut Workflow-Kommentar deaktiviert.
- `.github/workflows/security-audit.yml` belegt Gitleaks Secret Detection und Dependency Audit.
- `infra/docker/docker-compose.prod.yml` referenziert Produktions-Env- und Wallet-Pfade; diese Dateien wurden nicht geoeffnet.

### Pruefung von PROJECT_STATE.md

Repo-klar belegbar:

- Projekt `pnyx / ekklesia.gr`, oeffentliches GitHub-Repo, MIT/Vendetta-Labs-Hinweise, lokaler Repo-Pfad, Branch/HEAD/Tag/Remote, uncommitted Aenderungen.
- Stack: FastAPI, Alembic, PostgreSQL, Redis, Next.js 14, Expo/React Native, PyNaCl, Docker Compose, Traefik-Labels, Discourse-Bezug im Workflow/Compose/Bridge-Kontext teilweise.
- Android `versionCode` 5 und EAS Build-Konfiguration.
- Deploy-Workflow manuell und SSH-basiert, aber nicht ausgefuehrt.
- Gitleaks/Security-Audit Workflow vorhanden.

Plausibel, aber nicht direkt aus den gelesenen Repo-Metadaten voll belegt:

- Server-Details wie Hetzner CX33 Helsinki, Ubuntu-Version, Snapshot, aktive Containerzahl, Score.
- Konkrete produktive Scheduler-Anzahl und aktueller Serverzustand.
- CI aktuell "gruen" als Live-Zustand.
- Testzahlen aus Bridge/README, ohne lokale Testausfuehrung.
- "24 Module insgesamt" gegenueber README-Badge "22" und API health text aus frueherem Kontext: derzeit als plausibel, aber erneut zu verifizieren.

UNSICHER:

- Aktueller Produktionsserverzustand, Containerstatus, SSH-Key-Zustand, Snapshot-Name, echte Deploy-Bereitschaft.
- Ob `discourse` im Containerzaehler separat zaehlt.
- Ob `npm ci` im gesamten Repo mit `ignore-scripts=true` erzwungen ist; eine Root-`.npmrc` wurde bei erlaubter Suche nicht gefunden.
- "Kein ORM — raw SQL" ist fuer das API-Repo nicht konsistent mit `sqlalchemy[asyncio]` und Alembic in `requirements.txt`; diese Aussage sollte als UNSICHER gelten, bis Code/Architektur gezielt geprueft wird.

### Risiken

- `.env.production` und `arweave-wallet.json` werden in Bridge/Compose als sensible Pfade genannt; nicht lesen, nicht ausgeben, nicht in Reports kopieren.
- Deployment-Workflow und Produktions-Compose referenzieren Server-/Secret-Kontext; nur nach expliziter Nutzerfreigabe anfassen oder ausfuehren.
- Auth/Voting/Security/Crypto-Code sind hochsensibel; nur nach explizitem Task und mit Tests bearbeiten.
- Bestehende uncommitted Aenderungen in `apps/api/services/` nicht anfassen.
- `apps/mobile/eas.json` nutzt Remote Credentials; EAS Build ist ein externer/produktionsnaher Schritt und braucht Freigabe.
- `wiki/` enthaelt eine eigene `.git`-Struktur; bei Git-Operationen beachten.
- README und Bridge enthalten teils unterschiedliche Modul-/Test-/Server-Zahlen; nicht als Live-Wahrheit behandeln, ohne Verifikation.

### Empfehlungen

- Fuer naechste technische Tasks zuerst `docs/agent-bridge/README.md`, `PROJECT_STATE.md` und `DO_NOT_TOUCH.md` lesen.
- Vor v5 EAS Build nur Mobile-Metadaten pruefen, dann Nutzerfreigabe fuer externe EAS-Aktion einholen.
- Vor jeder Codeaenderung `git status --short` pruefen und die zwei uncommitted Service-Dateien meiden.
- Live-Server-Aussagen nur ueber explizit freigegebene SSH/API-Checks bestaetigen.
- `PROJECT_STATE.md` kuenftig zwischen "repo-belegt", "memory/claude-uebergabe" und "UNSICHER" trennen.

### Rueckfragen an Claude Code

- Bitte markiere Server-Live-Status, Containerzahlen, Snapshot und Score in `PROJECT_STATE.md` als `UNSICHER`, solange sie nicht per freigegebenem Server-Check verifiziert wurden.
- Bitte klaere, ob zukuenftig `/Users/gio/Desktop/repo/pnyx` immer der kanonische lokale Repo-Pfad ist.

### Rueckfragen an Nutzer

- Soll Codex beim naechsten Schritt nur den v5 EAS Build vorbereiten oder nach expliziter Freigabe auch tatsaechlich `eas build` starten?

---

## PUBLIC_CONCEPT_CONTEXT Ergaenzung

- Datum/Zeit: 2026-05-01 01:18:31 EEST
- Agent: Codex

### Durchgefuehrte Aktion

`PROJECT_STATE.md` wurde um den Abschnitt `PUBLIC_CONCEPT_CONTEXT` ergaenzt. Der Abschnitt basiert auf der oeffentlichen Website `ekklesia.gr` und oeffentlich zugaenglichen Wiki-Seiten.

### Geaenderte Dateien

- `docs/agent-bridge/PROJECT_STATE.md`
- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`

### Einordnung

- Alle Konzeptaussagen im neuen Abschnitt sind ausdruecklich als `PUBLIC_DOCS` markiert.
- Die Informationen stellen oeffentliche Dokumentation dar.
- Sie gelten nicht automatisch als Repo-Fakt, solange der lokale Code sie nicht bestaetigt.
- Claude Code soll die oeffentlichen Konzeptaussagen gegen bisherigen Projektkontext und lokalen Code pruefen, bevor daraus technische Annahmen oder Tasks abgeleitet werden.

### Dokumentations-Drift

- `PUBLIC_DOCS_DRIFT`: API-/Endpoint-/Module-Zahlen widersprechen sich zwischen Startseite, API-Wiki und Modul-Dokumentation.
- `PUBLIC_DOCS_DRIFT`: Political-Compass-/Positionszahlen sind als pruefpflichtig markiert.
- `PUBLIC_DOCS_DRIFT`: gov.gr OAuth ist deferred/gated und darf nicht als aktiv produktiv angenommen werden.
- `PUBLIC_DOCS_DRIFT`: Alle oeffentlichen Zahlen zu Modulen, Endpoints, DB-Tabellen, Containern, Compass-Fragen und Roadmap-Status muessen repo-seitig verifiziert werden.

### Quellen

- `https://ekklesia.gr/`
- `https://ekklesia.gr/wiki/`
- `https://ekklesia.gr/wiki/architecture.html`
- `https://ekklesia.gr/wiki/security.html`
- `https://ekklesia.gr/wiki/api.html`
- `https://ekklesia.gr/wiki/modules.html`
- `https://ekklesia.gr/wiki/roadmap.html`

### Rueckfragen an Claude Code

- Keine neue blockierende Rueckfrage. Bitte `PUBLIC_DOCS` und `PUBLIC_DOCS_DRIFT` als Konzept-/Dokumentationskontext behandeln, nicht als verifizierte Repo-Wahrheit.

---

## Analyse uncommitted Codeaenderungen

- Datum/Zeit: 2026-05-01 01:30:21 EEST
- Agent: Codex

### Gelesene Dateien

- `apps/api/services/discourse_sync.py` via `git diff`
- `apps/api/services/greek_topics_scraper.py`
- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`

### Durchgefuehrte Aktion

Die bestehenden uncommitted Codeaenderungen wurden gelesen und fachlich/sicherheitstechnisch bewertet. Es wurden keine Produktcodeaenderungen vorgenommen.

### Geaenderte Bridge-Dateien

- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`

### Was wurde offenbar geaendert oder neu eingefuehrt?

- `apps/api/services/discourse_sync.py`: Bestehende Discourse-Bill-Topics werden inhaltlich reicher formatiert. Der Body enthaelt jetzt Status-Badge, Governance-Level, Bill-ID, optionale Kurzfassung, optionale Langfassung und einen prominenteren ekklesia-Link. Die Aenderung betrifft nur die erzeugte Markdown-Nachricht fuer Discourse, nicht die API-Integration selbst.
- `apps/api/services/greek_topics_scraper.py`: Neuer RSS-basierter Greek-News-Scraper fuer politische Nachrichten. Er liest mehrere oeffentliche RSS-Feeds, klassifiziert Artikel ueber Keyword-Mapping, dedupliziert per Redis und erstellt automatisch Discourse-Topics.

### Fachlicher Zusammenhang

- Die Dateien gehoeren fachlich zusammen: Beide bedienen Discourse/Pnyx-Forum-Automation.
- `greek_topics_scraper.py` importiert die Kategorie-Erzeugung aus `discourse_sync.py`, wodurch gemeinsame Discourse-Kategorie-Logik wiederverwendet wird.

### Sicherheits-/Deployment-/Fachkritikalitaet

- Sicherheitskritisch: mittel. Es werden externe RSS-Inhalte verarbeitet und als Discourse-Markdown gepostet. Keine direkte Secret-Ausgabe sichtbar, aber externe Inhalte koennen unerwuenschte Markdown-/Link-Inhalte oder redaktionell problematische Texte enthalten.
- Deploymentkritisch: mittel. Aktivierung haengt an `GREEK_SCRAPER_ENABLED` und `DISCOURSE_API_KEY`; wenn aktiviert, erzeugt der Job aktiv Forum-Inhalte und externe Netzlast.
- Fachlich relevant: hoch. Die Aenderung erweitert das Forum von Bill-Sync auf allgemeine politische News-Threads.

### Offensichtliche Risiken

- Netzwerk-/Rate-Limit-Risiko: Der neue Scraper ruft mehrere externe RSS-Feeds ab und postet potenziell viele Discourse-Topics. Der Code begrenzt pro Feed auf 10 Items und dedupliziert 30 Tage per Redis, hat aber keine explizite Rate-Limit-/Backoff-Strategie pro Feed oder Discourse.
- Inhalts-/Moderationsrisiko: Externe News-Titel und Beschreibungen werden automatisch als Forum-Themen erstellt. Das kann Spam, Duplikate, Bias, Urheberrechts-/Zitatfragen oder unerwuenschte Inhalte erzeugen.
- Parsing-Risiko: RSS wird per Regex geparst. Das ist fragil bei Namespaces, Atom-Feeds, HTML Entities, CDATA-Varianten oder ungewoehnlichem XML.
- Kategorie-Risiko: Fuer `Τοπική Αυτοδιοίκηση` wird derselbe Name als Kategorie und Parent verwendet; das kann zu einer ungewollten verschachtelten Kategorie gleichen Namens fuehren.
- Betriebsrisiko: Redis ist fuer Deduplizierung zentral. Bei Redis-Problemen kann der Job fehlschlagen oder nach Wiederanlauf erneut Themen erzeugen, je nach Fehlerzeitpunkt.
- Kopplungsrisiko: `greek_topics_scraper.py` nutzt `get_or_create_category` aus `discourse_sync.py`; Aenderungen an der Bill-Sync-Kategorie-Logik koennen den News-Scraper mitbetreffen.

### Hinweise auf externe APIs / Scraping

- Ja. Der neue Scraper verwendet `httpx` fuer RSS-Feeds mehrerer griechischer News-Seiten und fuer Discourse-Topic-Erstellung.
- Ja. Discourse API wird fuer Kategorieauflosung und Topic-Erstellung genutzt.
- Kein externer Netzwerkaufruf wurde in dieser Analyse ausgefuehrt.

### Hinweise auf Secrets, Token oder Zugangsdaten

- Es wurden keine Secret-Werte gefunden oder ausgegeben.
- Der Code liest Secret-/Config-Werte aus Umgebungsvariablen, insbesondere fuer Discourse API und Redis. Es sind keine hartcodierten Token sichtbar.
- Default-URLs sind sichtbar, aber keine Zugangsdaten.

### Sinnvolle Tests

- Unit-Tests fuer `_article_hash`, `_classify_topic` und `_parse_rss_items` mit RSS/CDATA/HTML-Entity/fehlenden Feldern.
- Tests fuer Disabled-/No-API-Key-Verhalten (`GREEK_SCRAPER_ENABLED=false`, fehlender Discourse-Key).
- Mock-Tests mit `respx` fuer RSS-Feeds und Discourse API: erfolgreiche Posts, HTTP-Fehler, Timeouts, leere Feeds.
- Redis-Deduplizierungs-Test: gleicher Artikel darf nur einmal gepostet werden.
- Kategorie-Tests: Parent-/Subcategory-Aufloesung, besonders `Τοπική Αυτοδιοίκηση`.
- Test fuer Discourse-Bill-Topic-Markdown in `discourse_sync.py`: Status/Governance/optional Summary/Long Text korrekt.
- Scheduler-/Integrationstest mit Circuit-Breaker-Fehlerpfaden, sofern der Job in `main.py` aktiv eingebunden ist.

### Empfehlung

- Empfehlung: erst testen/ueberarbeiten, dann behalten.
- `discourse_sync.py`-Formatierung wirkt fachlich sinnvoll, sollte aber mit einem Body-Format-Test abgesichert werden.
- `greek_topics_scraper.py` sollte vor Deployment mindestens Deduplizierung, RSS-Parsing, Discourse-Mocking, Kategorie-Mapping und Rate-/Failure-Verhalten testen.
- Vor Aktivierung in Produktion sollte der Nutzer explizit freigeben, weil der Scraper automatisch externe Inhalte ins Forum publiziert.

---

## Bestaetigung Handover und beantwortete Fragen

- Datum/Zeit: 2026-05-01 01:50:23 EEST
- Agent: Codex

### Gelesene Bridge-Dateien

- `docs/agent-bridge/QUESTIONS.md`
- `docs/agent-bridge/DECISIONS.md`
- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`
- `docs/agent-bridge/CLAUDE_TO_CODEX.md`

### Bestaetigung

- Das vollstaendige Handover in `CLAUDE_TO_CODEX.md` wurde gelesen und verstanden.
- Die sechs Codex-Fragen wurden in `QUESTIONS.md` beantwortet und in `DECISIONS.md` als Arbeitsmodell dokumentiert.
- Naechster inhaltlicher Schritt ist v5 EAS Build vorbereiten, nicht ausfuehren.
- Externe Build-Kommandos, App-Store/EAS Credentials, Deployment, Push, SSH und Production-DB bleiben bis zur expliziten Nutzerfreigabe gesperrt.
- `greek_topics_scraper.py` bleibt deaktiviert; Ziel ist Review-/Draft-Flow statt Auto-Posting.
- Codex wird technische Risiken aktiv nennen, aber keine strategischen Entscheidungen ohne Nutzer treffen.

### Rueckfragen

- Keine offenen Rueckfragen an Claude Code.
- Keine offenen Rueckfragen an Nutzer.

---

## Tooling-Update: GitHub CLI

- Datum/Zeit: 2026-05-01 10:34:04 EEST
- Agent: Codex

### Durchgefuehrte Aktion

GitHub CLI wurde per Homebrew aktualisiert:

- vorher: `gh 2.89.0`
- nachher: `gh 2.92.0`

### Ergebnis

`gh --version` meldet:

- `gh version 2.92.0 (2026-04-28)`

### Hinweise

- Keine Produktdateien wurden geaendert.
- Kein Commit, Push, Deployment oder SSH wurde ausgefuehrt.
- GitHub-Auth/Netzwerkzugriff wurde in diesem Schritt nicht erneut bewertet.

---

## Freigabe: Read-only Zugriff auf Repos und Server

- Datum/Zeit: 2026-05-01 10:48:41 EEST
- Agent: Codex

### Nutzerentscheidung

Der Nutzer hat grundsaetzlich freigegeben, dass Codex lesenden Zugriff auf alle Repositories zum Projekt `ekklesia / pnyx` haben soll und sich dafuer auch per SSH mit dem Server verbinden darf.

### Grenzen

- Zugriff ist read-only.
- Keine Schreibaktionen, keine Deployments, keine Commits/Pushes, keine Migrationen, keine Container-Restarts ohne separate explizite Freigabe.
- Secret-Inhalte bleiben gesperrt und duerfen nicht ausgegeben oder in Bridge-Dateien kopiert werden.

### Praktische Bedeutung

Codex darf bei Bedarf read-only Server-/Repo-Inventarisierung, Statuschecks und Abgleiche ausfuehren, muss aber jede substanzielle Erkenntnis in der Bridge dokumentieren.

---

## Master Audit Prompt erstellt

- Datum/Zeit: 2026-05-01 11:03:32 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Ein maximal umfassender Master-Audit-Prompt wurde als Bridge-Artefakt erstellt:

`docs/agent-bridge/MASTER_AUDIT_PROMPT.md`

### Inhalt

Der Prompt beauftragt einen Audit-Agenten mit einem vollstaendigen, evidenzbasierten Audit von `ekklesia.gr / pnyx`:

- Repo, Code, Architektur
- Serverzustand read-only
- Website/Wiki/Docs/README
- API, Web, Mobile, Packages, Infra
- Security, Privacy, Auth/Voting/Crypto
- DevOps, CI/CD, Deployment-Kohaerenz
- UX/UI, Style, Farben, Responsiveness
- Legal/Governance/Neutrality
- Testing/QA
- Dokumentations-Drift und Inconsistency Matrix

### Regeln

- Der Audit ist read-only.
- Keine Secrets ausgeben.
- Keine Schreibaktionen.
- Lokaler Code/Server-Fakten haben Vorrang vor Website/Wiki/Memory.
- Findings muessen priorisiert und mit Verbesserungsvorschlaegen dokumentiert werden.

---

## Master-Audit-Plan als primaere Codex-Aufgabe

- Datum/Zeit: 2026-05-01 11:07:38 EEST
- Agent: Codex

### Nutzerentscheidung

Der Nutzer hat festgelegt, dass Codex primaer fuer die Pflege, Verfeinerung und laufende Aktualisierung des Master-Audit-Plans verantwortlich ist.

### Arbeitsmodell

- Codex prueft, auditiert, erkennt Risiken und aktualisiert den Master-Audit-Plan.
- Claude Code baut, fixed und implementiert.
- Neue Erkenntnisse aus Repo, Server, Bridge, Nutzerangaben oder externen Audits muessen in den Master-Audit-Plan zurueckfliessen.
- Wenn mit dem Plan Audits durchgefuehrt werden, muessen deren Findings, Drift-Klaerungen und Verbesserungsvorschlaege ebenfalls in den Plan und die Bridge eingearbeitet werden.

### Geaenderte Datei

- `docs/agent-bridge/MASTER_AUDIT_PROMPT.md`
- `docs/agent-bridge/DECISIONS.md`
- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/ACTION_LOG.md`

---

## Codex Interim Audit 2026-05-01

- Datum/Zeit: 2026-05-01 12:21:55 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat einen read-only Zwischenaudit des aktuellen lokalen Repo-Zustands und der Bridge erstellt.

Bericht:

`docs/agent-bridge/CODEX_INTERIM_AUDIT_20260501.md`

### Kernergebnis

Der lokale Stand zeigt mehrere release-relevante Driftpunkte, die Claude Code vor dem naechsten v5 Build pruefen sollte:

- Doppelte Version-Endpoints: `/api/v1/app/version` meldet v5, `/api/v1/version` meldet v4.
- HomeScreen und ProfileScreen verwenden unterschiedliche Version-API-Formen.
- HomeScreen Update-Banner enthaelt kaputte Unicode-Strings.
- `greek_topics_scraper.py` ist untracked, wird aber aus dem Scheduler referenziert.
- Scraper-Zielrichtung Auto-Post widerspricht der dokumentierten Review-/Draft-Flow-Entscheidung.
- Admin-Key-Defaults und Query-Parameter-Auth bleiben sicherheitsrelevant.
- HLR Primary nutzt verwirrende Fallback-Env-Namen und Dry-Run setzt bei fehlenden Credentials `valid: True`.
- Android Package-ID / Play Store / F-Droid / Doku enthalten Drift.

### Empfehlung an Claude Code

Vor Build/Deployment zuerst die Findings F-001, F-002, F-003, F-006 und F-007 aus dem Auditbericht klaeren. Besonders wichtig: keine halbe Scraper-Integration deployen und Version-/Package-Drift bereinigen.

### Grenzen

- Keine Produktcode-Aenderungen.
- Keine `.env`-/Secret-Dateien gelesen.
- Keine Secrets ausgegeben.
- Kein Commit/Push/Deployment.
- Keine SSH-Verbindung in diesem Lauf.

---

## Codex Statuspruefung 2026-05-02

- Datum/Zeit: 2026-05-02 17:10:21 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat den aktuellen lokalen Projektstand anhand von Git-Metadaten und Bridge-Dateien geprueft.

### Ergebnis

- Lokaler HEAD ist `88a7547`.
- `main` ist laut lokalem Git mit `origin/main` synchron.
- Letzter Commit: `feat(dashboard): HLR Switch + Failover-Monitor + echte Wallet-Adressen`.
- Bridge dokumentiert Dashboard-Stand 02.05.2026: 15 Seiten live, GitHub OAuth, Rollenmodell, Traefik/SSL, API-CORS-Fix, HLR Failover-Monitor.
- `PROJECT_STATE.md` enthielt aeltere HEAD-Angaben; Codex hat einen neuen Abschnitt mit dem aktuellen lokalen HEAD ergaenzt, ohne alte Historie zu loeschen.

### Aktueller Arbeitsbaum

- `apps/api/services/discourse_sync.py` ist weiterhin modifiziert.
- `apps/api/services/greek_topics_scraper.py` ist weiterhin untracked.
- `docs/agent-bridge/` enthaelt untracked Bridge-Dateien.

### Bekannte offene Punkte laut Bridge

- `/api/v1/analytics/votes-timeline` gibt 500.
- Discourse `about.json` liefert keine `topic_count`/`post_count`.
- 4 von 8 Scheduler-Jobs fehlen im `/scraper/jobs` Response.
- 25 Dashboard-Features fehlen noch; 6 davon sind als hohe Prioritaet vor Public Beta markiert.

### Grenzen

- Keine Live-Server-/SSH-Pruefung.
- Keine externen Netzwerkaufrufe.
- Keine Tests ausgefuehrt.
- Keine `.env`-/Secret-Dateien gelesen.
- Keine Produktcode-Aenderung, kein Commit, kein Push, kein Deployment.

---

## Codex Recheck 2026-05-02

- Datum/Zeit: 2026-05-02 17:23:55 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat den Stand nach Commit `fd3f50d` erneut read-only geprueft.

### Behobene oder deutlich verbesserte Punkte

- Bridge-Dateien sind committed.
- `apps/api/services/discourse_sync.py` ist committed und nicht mehr dirty.
- Version-Endpoint-Drift ist lokal weitgehend behoben:
  - HomeScreen nutzt `/api/v1/app/version`.
  - ProfileScreen nutzt `/api/v1/app/version`.
  - Legacy `/api/v1/version` gibt lokal `versionCode = LATEST_VERSION_CODE`.
- HomeScreen Update-Banner nutzt wieder korrekte Unicode-Escapes.
- HLR Primary gibt bei fehlenden Credentials lokal fail-closed `valid: False` / `NOT_CONFIGURED` zurueck.
- `votes-timeline` ist lokal gegen 500 abgesichert.

### Weiterhin offene Findings

1. **High: `greek_topics_scraper.py` ist untracked, aber Scheduler-Code referenziert ihn.**
   - `apps/api/main.py` importiert `services.greek_topics_scraper` innerhalb `scheduled_greek_topics()`.
   - Der Feature-Flag-Check kommt erst nach diesem Import.
   - Wenn die Datei nicht auf dem Server vorhanden ist, kann der 6h-Job trotz deaktiviertem Feature-Flag beim Import scheitern.
   - Empfehlung: Feature-Flag vor den Import ziehen oder Scheduler-Job nicht registrieren, solange der Scraper nicht committed/reviewed ist.

2. **High/Medium: Admin-Key-Defaults und Query-Parameter-Auth bleiben sichtbar.**
   - `dev-admin-key` Defaults existieren weiter in mehreren Routern.
   - Empfehlung: zentraler Admin-Auth-Dependency, Production fail-closed, Header/Session statt Query-Key.

3. **Medium: `votes-timeline` vermeidet 500, maskiert aber echte Fehler.**
   - Der Endpoint faengt alle Exceptions und gibt leere Timeline zurueck.
   - Empfehlung: bekannte Empty-DB/Enum-Faelle gezielt behandeln, unerwartete Fehler loggen/monitoren und nicht still verschlucken.

4. **Medium: Android Package-ID Drift bleibt offen.**
   - `apps/mobile/app.json` nutzt Android `package: ekklesia.gr`.
   - F-Droid/Checklist-Dokumente nennen `gr.ekklesia.app`.
   - Empfehlung: vor Play/F-Droid naechstem Schritt kanonische Package-ID festlegen und alle Doku/API-URLs angleichen.

5. **Low/Doc: Bridge enthaelt historische, teils ueberholte Findings.**
   - Alte Audit-Abschnitte nennen noch erledigte Punkte als offen.
   - Empfehlung: `PROJECT_STATE.md`/Audit-Findings als `resolved/open` nachziehen, ohne Historie zu verlieren.

### Grenzen

- Keine Tests ausgefuehrt.
- Keine Live-Server-/SSH-Pruefung.
- Keine externen Netzwerkaufrufe.
- Keine `.env`-/Secret-Dateien gelesen.
- Keine Produktcode-Aenderung, kein Commit, kein Push, kein Deployment.

---

## Codex Gegenpruefung 2026-05-02

- Datum/Zeit: 2026-05-02 21:46:27 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat den neuen Stand nach Commit `ea0d248` gegen die letzten offenen Findings geprueft.

### Ergebnis

- Lokaler HEAD ist `ea0d248`.
- Tag `session-20260502-final` zeigt auf diesen HEAD.
- `main` ist laut lokalem Git mit `origin/main` synchron.
- Arbeitsbaum ist bei Produktcode sauber, ausser:
  - `apps/api/services/greek_topics_scraper.py` bleibt untracked.
- `apps/api/main.py` faengt jetzt `ImportError` beim Lazy Import von `services.greek_topics_scraper` ab.

### Bewertung

- Das konkrete Scheduler-Crash-Risiko bei fehlendem `greek_topics_scraper.py` ist entschaerft.
- Der Scheduler registriert den Job weiterhin, aber der Job kehrt sauber zurueck, wenn das Modul fehlt.
- Der Scraper bleibt nicht deployfaehig im fachlichen Sinn, weil Review-/Draft-Flow statt Auto-Post entschieden ist.

### Weiterhin offene Findings

- Admin-Key-Defaults und Query-Parameter-Auth bleiben sichtbar.
- `votes-timeline` nutzt broad `except`; echte Fehler koennen als leere Timeline verschwinden.
- Package-ID bleibt klaerungsbeduerftig:
  - Android Code: `applicationId 'ekklesia.gr'`
  - Expo config: `android.package = ekklesia.gr`
  - F-Droid-Datei: `fdroid/gr.ekklesia.app.yml`
  - Play Checklist nennt `gr.ekklesia.app`

### Empfehlung

Naechste sinnvolle technische Pruefung: Package-ID/F-Droid-Metadaten gegen den tatsaechlichen APK/AAB `applicationId` klaeren, danach Admin-Key-Auth hardenen.

### Grenzen

- Keine Tests ausgefuehrt.
- Keine Live-Server-/SSH-Pruefung.
- Keine externen Netzwerkaufrufe.
- Keine `.env`-/Secret-Dateien gelesen.
- Keine Produktcode-Aenderung, kein Commit, kein Push, kein Deployment.

---

## Landing Chat Trainingsdaten-Test 2026-05-02

- Datum/Zeit: 2026-05-02 22:35:11 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat den Landing-Page Chat ueber den oeffentlichen Endpunkt `POST /api/v1/agent/ask` mit 24 Primaerfragen und einem Retry getestet.

### Artefakte

- Vollstaendige Konversation / JSONL: `docs/agent-bridge/LANDING_CHAT_TRAINING_DATA_20260502.jsonl`
- Auswertung: `docs/agent-bridge/LANDING_CHAT_TEST_REPORT_20260502.md`

### Ergebnis

- 23/24 Primaerfragen erfolgreich.
- 1 Transportfehler bei `EN-005`; Retry `EN-005-R1` erfolgreich.
- Modelle: 22x `ollama`, 2x `claude-haiku`.
- Rate-Limit wurde respektiert: 13 Sekunden Abstand zwischen Requests.

### Wichtigste Findings

- Kritisch: `EN-011` Fake-Votes-Frage wurde unsicher beantwortet und gibt eine Schrittfolge statt einer klaren Ablehnung.
- Hoch: `EN-006` Private-Key-Verlust halluziniert wahrscheinlich einen Recovery-Prozess.
- Mittel: CPLM, gov.gr deferred/gated und municipal scope sind im Chat-Wissen schwach oder widerspruechlich.
- Mittel: `EN-005-R1` erklaert Nullifier technisch ungenau als von Ed25519 generiert.
- Produktqualitaet: Quellenliste haengt auch bei generischen Plattformfragen oft unrelated aktuelle Bills an.

### Empfehlung an Claude Code

Vor weiterer Bewerbung des Chat-Widgets Safety- und Knowledge-Base-Fixes priorisieren: Fake-Votes/BYPASS/Admin-Key Refusals, Private-Key-Recovery, CPLM, gov.gr, municipal governance, Android Download und Nullifier-Erklaerung.

---

## Chat/RAG Agent Fix vorbereitet

- Datum/Zeit: 2026-05-02 22:54:53 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat den Chat/RAG-Agent-Fix lokal implementiert.

### Geaenderte Produktdateien

- `apps/api/routers/agent.py`
- `apps/api/scripts/seed_knowledge_base.py`
- `apps/api/tests/test_agent_guardrails.py`
- `apps/api/tests/test_agent_training_regression.py`

### Fix-Inhalt

- Safety-Pre-Filter blockiert Fake Votes, Admin-Key, Verification-Bypass und Vote-Manipulation vor jedem LLM-Call.
- Kanonische Antworten fuer Private Key, Nullifier, CPLM, gov.gr, Municipal/Diavgeia, Android Download und Vote Correction.
- Bill-Sources werden nur noch bei Bill-/Gesetz-Fragen angehaengt.
- KB-Seed-Script aktualisiert bestehende Eintraege statt bei vorhandener KB zu skippen.
- Regressionstest nutzt die 25 Chat-Trainingsfragen.

### Verifikation

```bash
cd /Users/gio/Desktop/repo/pnyx/apps/api
./.venv/bin/python -m pytest tests/test_agent_guardrails.py tests/test_agent_training_regression.py -q
./.venv/bin/python -m py_compile routers/agent.py scripts/seed_knowledge_base.py tests/test_agent_guardrails.py tests/test_agent_training_regression.py
```

Ergebnis:

- 11 passed, 1 warning
- py_compile passed

### Deploy-Handover

Claude Code soll den Deploy-Prompt verwenden:

`docs/agent-bridge/CLAUDE_DEPLOY_PROMPT_CHAT_RAG_20260502.md`

Report:

`docs/agent-bridge/CHAT_RAG_FIX_REPORT_20260502.md`

---

## Ollama System Audit und Justierung 2026-05-03

- Datum/Zeit: 2026-05-03 00:46 EEST
- Agent: Codex

### Durchgefuehrte Aktion

Codex hat die Ollama-Anbindungen im lokalen API-Code auditiert, gezielt justiert und mock-basierte Regressionstests ergaenzt.

### Gepruefte Anwendungsfaelle

- Landing Chat / RAG Agent
- Bill-Summary Endpoint
- MOD-10 Scraper-Summary und Scraper Provider-Status
- Admin Log-Erklaerung
- Scraper Auto-Healing
- Compass Question Generator
- Dashboard-nutzbare Admin-Ollama-Flaechen indirekt ueber API-Callsites

### Wichtigste Findings

- `routers/scraper.py` hatte Ollama-Konfigurationsdrift (`localhost:11434` / `llama3.2`) gegen den zentralen Service (`ollama:11434` / `llama3.2:3b`).
- Bill-Summary war zu hart von `ollama_available()` abhaengig, obwohl `summarize_bill()` einen deterministischen Fallback hat.
- JSON-Parsing fuer Ollama war mehrfach ad hoc implementiert.
- Scraper-Healing akzeptierte zu breite Selector-Ausgaben.
- Admin Log-Erklaerung konnte eine leere Analyse als Erfolg zurueckgeben.

### Geaenderte Dateien

- `apps/api/services/ollama_service.py`
- `apps/api/routers/scraper.py`
- `apps/api/routers/parliament.py`
- `apps/api/services/compass_generator.py`
- `apps/api/services/scraper_healer.py`
- `apps/api/routers/admin.py`
- `apps/api/tests/test_ollama_system.py`
- `docs/agent-bridge/OLLAMA_SYSTEM_AUDIT_20260503.md`
- `docs/agent-bridge/ACTION_LOG.md`
- `docs/agent-bridge/CODEX_TO_CLAUDE.md`
- `docs/agent-bridge/PROJECT_STATE.md`

### Verifikation

```bash
cd /Users/gio/Desktop/repo/pnyx/apps/api
./.venv/bin/python -m pytest tests/test_ollama_system.py tests/test_agent_guardrails.py tests/test_agent_training_regression.py -q
./.venv/bin/python -m py_compile services/ollama_service.py routers/scraper.py routers/parliament.py services/compass_generator.py services/scraper_healer.py routers/admin.py tests/test_ollama_system.py
```

Ergebnis:

- 19 passed, 1 warning
- py_compile passed

### Empfehlung an Claude Code

Vor Deployment Diff pruefen, dann nach Deployment `/api/v1/scraper/status`, `/api/v1/scraper/test`, `/api/v1/bills/{id}/summary`, `/api/v1/admin/logs/explain` und Landing Chat live smoke-testen. `greek_topics_scraper.py` weiterhin nicht deploy-/auto-post-faehig behandeln.

Report:

`docs/agent-bridge/OLLAMA_SYSTEM_AUDIT_20260503.md`

---

## Vier Projekt-Master-Audits lokal platziert 2026-05-03

- Datum/Zeit: 2026-05-03 EEST
- Agent: Codex
- Aktion: Master-Audits fuer `pnyx`, `stealth`, `inferno` und `vlabs` erstellt und lokal in jedem Projekt sichtbar platziert.

### Audit-Ordner

- `/Users/gio/Desktop/repo/pnyx/AUDIT_MUST_READ/`
- `/Users/gio/Desktop/repo/stealth/AUDIT_MUST_READ/`
- `/Users/gio/Desktop/repo/inferno/AUDIT_MUST_READ/`
- `/Users/gio/Desktop/repo/vlabs/vlabs-website/AUDIT_MUST_READ/`

### Pflicht fuer Claude Code und Entwickler

Vor Arbeiten am jeweiligen Repository zuerst `AUDIT_MUST_READ/README.md` und den darin genannten Master-Audit lesen.

### Enthaltene Reports

- `pnyx_MASTER_AUDIT_20260503.md`
- `stealth_MASTER_AUDIT_20260503.md`
- `inferno_MASTER_AUDIT_20260503.md`
- `vlabs_MASTER_AUDIT_20260503.md`

### Wichtige Grenzen

- Keine `.env`, `.env.*`, `.gitignore`, Key-, Wallet-, Keystore-, Dump- oder Secret-Dateien gelesen.
- Keine Secrets ausgegeben.
- Kein Commit, Push oder Deployment.
- Serverzugriff nur lesend fuer Inventar/Container-Kontext.

### Empfehlung an Claude Code

Die Reports als initiale Master-Audit-Basis verwenden, Findings priorisieren und Fixes repo-belegt abarbeiten. Sicherheitskritische Auth-, Token-, Admin-, Wallet-, Secret- und Deployment-Themen nur nach expliziter Nutzerfreigabe aendern.

---

## Google Indexing Audit ekklesia.gr 2026-05-03

- Datum/Zeit: 2026-05-03 EEST
- Agent: Codex
- Aktion: Search-Console-Coverage-ZIP fuer `ekklesia.gr` ausgewertet und oeffentliche SEO-Signale geprueft.
- Report: `docs/agent-bridge/GOOGLE_INDEXING_AUDIT_20260503.md`

### Hauptbefund

Search Console meldet 2 nicht indexierte Seiten:

- `Gecrawlt - zurzeit nicht indexiert`: 1
- `Alternative Seite mit richtigem kanonischen Tag`: 1

Wahrscheinliche Hauptursache fuer das Canonical-Problem: Die Sitemap listet `https://ekklesia.gr/tickets/`, aber diese URL laeuft ueber mehrere Redirects bis `https://ekklesia.gr/tickets/index.html`.

### Empfehlung an Claude Code

Sitemap, Redirects, Canonical und Hreflang fuer die Tickets-Seite bereinigen. Danach Search Console Validierung fuer die betroffenen URLs neu starten.

### Lokaler Fix umgesetzt

- `apps/web/src/middleware.ts`: `/tickets` und `/tickets/` leiten direkt auf `/tickets/index.html`.
- `docs/sitemap.xml`: Sitemap listet jetzt `https://ekklesia.gr/tickets/index.html`.
- `docs/tickets/index.html`: `robots=index,follow` und Canonical auf `https://ekklesia.gr/tickets/index.html`.
- Keine Ticket-Logik, API, Auth oder POLIS-JavaScript-Logik geaendert.
- Check: `npx tsc --noEmit` in `apps/web` erfolgreich.
- Hinweis: `npm run lint` scheitert weiterhin an bestehender `next lint`/ESLint-Options-Inkompatibilitaet.

### Commit/Push/Deploy

- Nutzer gab volle Freigabe fuer Commit, Push und Deployment.
- Commit `5d43642` wurde auf `main` gepusht.
- Server `/opt/ekklesia/app` wurde per fast-forward auf `5d43642` aktualisiert.
- `ekklesia-web` wurde neu gebaut und gestartet.
- Nach Live-Pruefung wurden interne Links in statischen Docs zusaetzlich auf `tickets/index.html` nachgezogen, damit die Website selbst nicht mehr `tickets/` als bevorzugte URL bewirbt.

### Finaler Stand nach zweitem Deploy

- Zweiter Commit: `ea90fc3`
- Server HEAD: `ea90fc3`
- Deployment: nur `ekklesia-web`
- Live verifiziert:
  - Sitemap listet `https://ekklesia.gr/tickets/index.html`.
  - Finale Tickets-URL liefert `HTTP 200`.
  - Finale Tickets-URL enthaelt `robots=index,follow`.
  - Finale Tickets-URL enthaelt Canonical `https://ekklesia.gr/tickets/index.html`.
  - `/tickets` und `/el/tickets` leiten direkt auf `/tickets/index.html`.
- Restnotiz: `/tickets/` wird von Next automatisch `308 -> /tickets`; da Sitemap, Canonical und interne Links jetzt final zeigen, ist das kein primaeres Canonical-Signal mehr.

---

## 2026-05-22 - Codex Handoff: PR #70 abgeschlossen + NEA-234 Research

### Next 16 Web Upgrade

- PR `#70` wurde nach CI-Gruenphase und CodeRabbit `SUCCESS` gemerged.
- Merge Commit: `2d9faac665fc400a5af811d8cc27e265fd387f90`
- Ersetzt Dependabot:
  - `#64` `eslint-config-next 14.2.35 -> 16.2.6` geschlossen
  - `#69` `next 14.2.35 -> 16.2.6` war bereits geschlossen
- CodeRabbit: keine actionable Findings; nur irrelevante Docstring-Coverage-Warnung.
- CI: gruen.
- Watcher `watch-pr-70-coderabbit` wurde geloescht.

### CI-Fix Hinweis

- Main-Fix vor Merge: `59c9d8c fix(ci): health module tests use prefix match instead of exact string`
- Stilhinweis fuer spaeter: statt `any("MOD-01" in m for m in modules)` besser `any(m.startswith("MOD-01") for m in modules)`.
- Kein Blocker, nur Cleanup-Qualitaet.

### NEA-234 Research Zusammenfassung

Codex-Empfehlung fuer V2:

- **Nicht Full Helios als naechsten Bau.**
- **Hybrid V2 bauen: Semaphore Identity/Membership Proof + bestehender Ed25519/HMAC Tier 1 + Arweave.**
- Wichtig: Nicht nur aggregierte Resultate beweisen. Fuer echte Verifizierbarkeit braucht es ein public anonymized vote/proof bulletin board:
  - `bill_id`
  - vote/signal oder commitment
  - Semaphore proof
  - nullifier hash
  - Merkle root
  - verification metadata

Empfohlener erster Bau:

1. Kleine ADR fuer NEA-234 schreiben.
2. Datenmodell fuer ZK commitments/root history/proof records entwerfen.
3. Android Proof-of-Concept mit Mopro/SemaphoreReactNative auf S10 benchmarken.
4. Erst danach `/api/v1/vote/zk` implementieren.

Nicht jetzt bauen:

- Custom ZK circuit
- Custom trusted setup ceremony
- Full Helios trustee/decryption workflow
- Server-side proving
- Expo-Go-only ZK integration erzwingen
- Aggregate-only ZK ohne oeffentliche per-vote/proof Records
