# CODEX FINDINGS — NEA-221 Review

Datum: 2026-05-19T21:27:11Z
Agent: Codex
Scope: NEA-221 Gegenpruefung — Tab-Layout, Konsensierung Crash, Web/App Sync
Repo: `/Users/gio/Desktop/repo/pnyx`
HEAD: `37c6707` (`chore(bridge): vC16 fixes deployed — 97 orgs resolved, S10+Server+AAB`)

## Recheck-Status 2026-05-20 00:51 EEST

Quelle: Gio/CC-Live-Teststand aus aktiver NEA-221 Session.

- C-01 Public API Felder: VERIFIED_FIXED laut bereits erfolgter Live-Verifikation.
- C-04 BillDetail Felder: VERIFIED_FIXED laut bereits erfolgter Live-Verifikation.
- C-03 Konsensierung Signatur: RECHECK_IN_PROGRESS.
  - S10 ist auf vC16: `versionCode=16 minSdk=24 targetSdk=36`.
  - Test-Account wurde per Deep-Link importiert.
  - Nullifier fuer Test-Account: dokumentiert nur als gekuerzter Prefix `ca7e108d...` wegen Secret-/Identifier-Hygiene.
  - Manueller Test offen: Bills-Tab oeffnen, Diavgeia `OPEN_END` Bill oeffnen, pruefen dass nur Konsensierung-Slider erscheint, Slider bewerten und `Υποβολή Βαθμολογίας` absenden.
- C-02 Konsensierungspfad: DOCUMENTED, kein Code-Bug. Kanonischer Pfad bleibt `/api/v1/vote/{bill_id}/consensus`.
- Web-Paritaet: DEFERRED Phase 2 (`DIAVGEIA` Badge, Web-Konsensierung, Web `results_hidden`).

Hinweis: C-03 darf erst auf VERIFIED_FIXED gesetzt werden, wenn der S10-Test erfolgreich abgeschlossen und die Backend-Antwort/Live-Aggregation plausibel ist.

## Kritische Findings

### C-01 — Public Bills API ist nicht NEA-221-komplett

Status: STILL_OPEN
Severity: HIGH

Live-Check:

```bash
curl -sS "https://api.ekklesia.gr/api/v1/public/bills?limit=3"
```

`/api/v1/public/bills` liefert weiterhin nur Basisfelder:

- `id`
- `title_el`
- `title_en`
- `pill_el`
- `pill_en`
- `categories`
- `status`
- `vote_date`
- `arweave_tx`
- `arweave_url`

Fehlende NEA-221-Felder im Public-Endpoint:

- `source`
- `results_visibility`
- `consensus_score`
- `consensus_count`
- `flag_count`
- `governance_level`
- `diavgeia_ada`

Code-Beleg: `apps/api/routers/public_api.py:156` bis `apps/api/routers/public_api.py:168`.

Hinweis: `/api/v1/bills?limit=3` liefert die erweiterten Felder live korrekt. Die Inkonsistenz betrifft den Public-API-Vertrag.

### C-02 — Konsensierungspfad im Task ist falsch; App nutzt anderen Pfad

Status: PARTIAL
Severity: HIGH

Live-Check laut Task:

```bash
curl -sS "https://api.ekklesia.gr/api/v1/votes/consensus/GR-5293" -X POST ...
```

Antwort:

```json
{"detail":"Not Found"}
```

Tatsaechlicher Backend-Pfad ist:

```text
POST /api/v1/vote/{bill_id}/consensus
```

Code-Beleg:

- `apps/api/routers/voting.py:620`
- `apps/mobile/src/screens/VoteScreen.tsx:293`

Der mobile Code ist auf den tatsaechlichen Pfad ausgerichtet. Der Review-/Spezifikationspfad `/api/v1/votes/consensus/{id}` ist aber falsch und wuerde jeden externen Client brechen, der nach Task-Spezifikation implementiert.

### C-03 — Konsensierung uebergibt `nullifier_hash`, aber keine echte Signatur

Status: STILL_OPEN
Severity: HIGH

Mobile sendet:

```ts
body: JSON.stringify({ score: consensusScore, nullifier_hash: nullifier, signature_hex: "consensus" })
```

Code-Beleg: `apps/mobile/src/screens/VoteScreen.tsx:296`.

Backend verlangt formal `signature_hex` mit `min_length=64`, verifiziert diese Signatur aber im Konsensierungs-Endpoint nicht.

Code-Beleg:

- Schema: `apps/api/routers/voting.py:620` ff.
- Identitaetscheck nur ueber `nullifier_hash`: `apps/api/routers/voting.py:639` bis `apps/api/routers/voting.py:647`
- Kein Ed25519-/Payload-Verify vor Upsert: `apps/api/routers/voting.py:649` bis `apps/api/routers/voting.py:655`

Risiko: Jeder Client, der einen aktiven `nullifier_hash` kennt, kann Konsenswerte setzen oder ueberschreiben. Fuer Voting/Konsens ist das ein Authentizitaetsproblem.

### C-04 — Bill Detail API enthaelt zentrale NEA-221-Felder nicht

Status: STILL_OPEN
Severity: MEDIUM

`GET /api/v1/bills/{bill_id}` liefert live fuer `GR-5293` keine Felder:

- `source`
- `results_visibility`
- `consensus_score`
- `consensus_count`
- `flag_count`
- `diavgeia_ada`

Code-Beleg:

- `BillDetail` Schema endet ohne diese Felder: `apps/api/routers/parliament.py:55` bis `apps/api/routers/parliament.py:73`
- Return setzt sie ebenfalls nicht: `apps/api/routers/parliament.py:221` bis `apps/api/routers/parliament.py:240`

Folge: `VoteScreen` versucht `d.source` zu lesen und faellt sonst auf `PARLIAMENT` zurueck (`apps/mobile/src/screens/VoteScreen.tsx:55` bis `apps/mobile/src/screens/VoteScreen.tsx:58`). DIAVGEIA-Detailansichten koennen dadurch als Parliament behandelt werden.

## API Felder fehlend

### `/api/v1/public/bills`

Fehlen live:

- `source`
- `results_visibility`
- `consensus_score`
- `consensus_count`
- `flag_count`
- `governance_level`
- `diavgeia_ada`

### `/api/v1/bills`

Live vollstaendiger fuer NEA-221:

- `source`: vorhanden
- `results_visibility`: vorhanden
- `consensus_score`: vorhanden
- `consensus_count`: vorhanden
- `flag_count`: vorhanden
- `governance_level`: vorhanden
- `diavgeia_ada`: vorhanden

### `/api/v1/bills/{bill_id}`

Fehlen live/code-seitig:

- `source`
- `results_visibility`
- `consensus_score`
- `consensus_count`
- `flag_count`
- `diavgeia_ada`

## App/Web Inkonsistenzen

### A-01 — Mobile Tab-Filter sind clientseitig, nicht API-parametrisiert

Status: INFO

Mobile ruft `fetchBills()` ohne Filterparameter auf und filtert danach lokal:

- `apps/mobile/src/lib/api.ts:54`
- `apps/mobile/src/screens/BillsScreen.tsx:40` bis `apps/mobile/src/screens/BillsScreen.tsx:46`

Das ist funktional fuer kleine Listen, aber nicht konsistent mit einem API-parametrisierten Tab-Layout. Bei Pagination/Limit/Offset wuerden DIAVGEIA/MUNICIPAL/REGIONAL Tabs unvollstaendige Ergebnisse zeigen.

### A-02 — Mobile zeigt Results-Link trotz `results_visibility`

Status: PARTIAL

`ResultScreen` respektiert `results_hidden` aus `/api/v1/vote/{id}/results`. `VoteScreen` zeigt den Link aber fuer alle nicht-ANNOUNCED Bills:

- `apps/mobile/src/screens/VoteScreen.tsx:318` bis `apps/mobile/src/screens/VoteScreen.tsx:324`

Das ist kein Datenleck, weil der Results-Endpoint maskiert. UX ist aber inkonsistent: User werden zu Ergebnisansichten geleitet, die fuer ACTIVE/HIDDEN absichtlich keine Ergebnisse zeigen.

### W-01 — Web Bills-Liste hat keinen DIAVGEIA-Filter und kein DIAVGEIA-Badge

Status: STILL_OPEN
Severity: MEDIUM

Web hat nur Governance-Level-Filter:

- `apps/web/src/app/[locale]/bills/page.tsx:19` bis `apps/web/src/app/[locale]/bills/page.tsx:24`
- Filterlogik nur `governance_level`: `apps/web/src/app/[locale]/bills/page.tsx:55` bis `apps/web/src/app/[locale]/bills/page.tsx:60`

In der Kartenanzeige wird kein `source === "DIAVGEIA"` Badge gerendert:

- `apps/web/src/app/[locale]/bills/page.tsx:195` bis `apps/web/src/app/[locale]/bills/page.tsx:247`

Mobile hat beides:

- DIAVGEIA-Filter: `apps/mobile/src/screens/BillsScreen.tsx:42`
- DIAVGEIA-Badge: `apps/mobile/src/screens/BillsScreen.tsx:87` bis `apps/mobile/src/screens/BillsScreen.tsx:89`

### W-02 — Web Detail hat keine OPEN_END-Konsensierung

Status: STILL_OPEN
Severity: MEDIUM

Web Detail behandelt `OPEN_END` als votable:

- `apps/web/src/app/[locale]/bills/[id]/page.tsx:164`
- Vote UI: `apps/web/src/app/[locale]/bills/[id]/page.tsx:281` bis `apps/web/src/app/[locale]/bills/[id]/page.tsx:367`

Es gibt aber keine Konsens-Skala und keinen POST auf `/api/v1/vote/{bill_id}/consensus`.

Mobile hat Konsens-Skala:

- `apps/mobile/src/screens/VoteScreen.tsx:256` bis `apps/mobile/src/screens/VoteScreen.tsx:308`

### W-03 — Web Detail zeigt Ergebnisse nur bei `total_votes > 0`, aber keine `results_hidden`-Message

Status: PARTIAL
Severity: LOW

Web Detail laedt `results`, rendert aber nur:

```tsx
{results && results.total_votes > 0 && (...)}
```

Code-Beleg: `apps/web/src/app/[locale]/bills/[id]/page.tsx:385` bis `apps/web/src/app/[locale]/bills/[id]/page.tsx:403`.

Wenn der API-Endpoint wegen `results_visibility=HIDDEN` maskiert, gibt es keinen erklaerenden Hinweis im Web Detail. Mobile `ResultScreen` hat mindestens `results_hidden`-Handling.

### W-04 — `docs/votes/active.html` ist nur Redirect

Status: INFO

Der im Review-Task genannte Web-Pfad ist kein eigentlicher Vote-UI-Code:

```html
<meta http-equiv="refresh" content="0;url=/el/bills"/>
```

Code-Beleg: `docs/votes/active.html`.

Tatsaechliche Web-UI liegt unter:

- `apps/web/src/app/[locale]/bills/page.tsx`
- `apps/web/src/app/[locale]/bills/[id]/page.tsx`

## Fragen an CC

1. Soll `/api/v1/public/bills` denselben NEA-221-Feldumfang wie `/api/v1/bills` bekommen, oder bleibt Public API absichtlich reduziert?
2. Ist `/api/v1/votes/consensus/{bill_id}` eine alte/falsche Spezifikation, oder soll ein Compatibility-Alias auf den bestehenden `/api/v1/vote/{bill_id}/consensus` gelegt werden?
3. Soll Konsensierung Ed25519-signiert werden wie normale Votes? Falls ja: welches kanonische Payload-Format soll gelten, z.B. `{ bill_id, nullifier_hash, score }`?
4. Soll `GET /api/v1/bills/{bill_id}` die Detailfelder `source`, `results_visibility`, `consensus_score`, `consensus_count`, `flag_count`, `diavgeia_ada` liefern?
5. Soll Web Feature-Paritaet mit Mobile fuer DIAVGEIA-Badge, DIAVGEIA-Filter und OPEN_END-Konsens-Skala erreichen?

## Empfehlungen

1. API zuerst konsolidieren:
   - Public-Bills-Felder ergaenzen oder bewusst dokumentieren, dass Public API reduziert ist.
   - BillDetail Schema/Return um NEA-221-Felder erweitern.
2. Konsensierung absichern:
   - echte Signatur statt `signature_hex: "consensus"` verwenden.
   - Backend-Signaturpruefung fuer ConsensusRequest einfuehren.
3. Web/App Sync:
   - Web Bills-Liste um DIAVGEIA-Filter und Badge ergaenzen.
   - Web Detail um OPEN_END-Konsens-Skala ergaenzen oder OPEN_END nicht als normale Vote behandeln.
   - Results-Hidden-Zustand im Web explizit anzeigen.
4. Spezifikation bereinigen:
   - Pfad `/api/v1/vote/{bill_id}/consensus` als kanonisch dokumentieren oder Alias fuer `/api/v1/votes/consensus/{bill_id}` implementieren.

## Review Summary

- API Felder vollstaendig: NO
  - `/api/v1/bills`: YES fuer Liste
  - `/api/v1/public/bills`: NO
  - `/api/v1/bills/{id}`: NO
- Konsensierung `nullifier_hash`: korrekt uebergeben, aber Signatur falsch/nicht verifiziert
- Tab-Filter API-Parameter: NO, Mobile und Web filtern clientseitig; Web hat keinen DIAVGEIA-Filter
- `results_visibility` ueberall: NO
- Web DIAVGEIA Badge: NO
- Kritische/merge-blockierende Findings: 4
