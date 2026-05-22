# CODEX FINDINGS — NEA-186 / NEA-240
Datum: 2026-05-22
Agent: Codex
Scope: Audit-Recheck Commit `2226eac` (NEA-247 + NEA-248), read-only Produktcode. Keine Produktcode-Aenderungen.

## NEA-247 Finding 1: Mobile ResultScreen still shows false "vote recorded" message

Severity: MEDIUM

Web Bill Detail ist in `2226eac` gefixt: `apps/web/src/app/[locale]/bills/[id]/page.tsx` zeigt "Η ψήφος σας καταγράφηκε" nur noch bei `voteStatus === "voted"` oder `"already"`.

Mobile hat aber noch denselben Pattern: `apps/mobile/src/screens/ResultScreen.tsx` setzt `isHidden = data.results_hidden || (data.status === "ACTIVE" && data.total_votes === 0)` und rendert dann "Η ψήφος σας καταγράφηκε". Dieser Screen ist ohne erfolgreichen Vote erreichbar: `apps/mobile/src/screens/VoteScreen.tsx` zeigt fuer alle nicht-ANNOUNCED Bills den Link "Δείτε τα τρέχοντα αποτελέσματα →" und navigiert direkt zu `Result`.

Fix fuer CC: Mobile Hidden-Card-Text entkoppeln. Wenn `data.results_hidden`/ACTIVE+0 ohne lokalen Vote-Kontext angezeigt wird, neutral formulieren ("Τα αποτελέσματα δεν είναι ακόμη διαθέσιμα"). "Η ψήφος σας καταγράφηκε" nur nach erfolgreichem Vote/Correction-Kontext anzeigen, z.B. via route param from `VoteScreen` after submit/correction or eigener local state.

## NEA-248 Notes

- `docs/tickets/index.html` ESC-Handler schliesst `qrOverlay` via `closeQRLogin()` und `phaseBModal` via `display='none'`.
- Auto-close nach QR Auth war bereits vorhanden (`setTimeout(..., 1500)`).
- Keine neue NEA-248 Blocker im statischen Recheck gefunden.

---

Datum: 2026-05-22
Agent: Codex
Scope: Audit-Recheck Commit `435f3bd` (NEA-186 rep role-based bill visibility), read-only Produktcode. Keine Produktcode-Aenderungen.

## NEA-186 Finding 1: Results endpoint bypasses role visibility — RESOLVED in `eceb806`

Severity: HIGH

`GET /api/v1/rep/bills` filtert die Liste nach Rolle, aber `GET /api/v1/rep/results/{bill_id}` laedt Bills nur per ID und Status. Ein Vertreter mit gueltigem Token kann dadurch Ergebnisse fuer einen Bill abrufen, der in seiner rollenbasierten Bills-Liste nicht sichtbar waere, wenn die `bill_id` bekannt/erratbar ist.

Betroffene Stelle: `apps/api/routers/representative.py:get_rep_results()` prueft nur `bill.status in ALLOWED_STATUSES`; es verwendet die neue Rollen-Sichtbarkeitslogik nicht.

Fix fuer CC: Sichtbarkeitslogik in einen gemeinsamen Helper extrahieren und fuer `/rep/bills`, `/rep/results/{bill_id}` und optional `/rep/divergence/{bill_id}` verwenden. Tests: unknown role darf Results fuer DIAVGEIA regional/municipal nicht abrufen; Δήμαρχος darf keine REGIONAL Results direkt per ID abrufen; Περιφερειάρχης ohne Region nur PARLIAMENT.

Recheck 2026-05-22: `eceb806` extrahiert `is_bill_visible_for_token()` und wendet es in `/rep/results/{bill_id}` an. Finding geschlossen.

## NEA-186 Finding 2: Περιφερειάρχης region is checked for presence but not applied — RESOLVED in `eceb806`

Severity: MEDIUM

Der Plan sagte `REGIONAL AND region ILIKE token.region`. Die Implementierung nutzt `region` nur als truthy guard und gibt dann alle `DIAVGEIA + REGIONAL` Bills frei. Da `parliament_bills` aktuell keine Text-Region-Spalte hat, ist echtes Region-Matching ohne `periferia_id` Mapping nicht vorhanden.

Betroffene Stelle: `apps/api/routers/representative.py:get_rep_bills()` Branch `role == "Περιφερειάρχης" and region`.

Fix fuer CC: Entweder als Known Limitation analog Δήμαρχος dokumentieren ("Περιφερειάρχης sieht alle REGIONAL Bills bis periferia_id Mapping") oder konservativer auf PARLIAMENT-only fallbacken, bis `periferia_id` Mapping existiert. Wenn bereits `periferia_id` auf Bills und Token-Seite eingefuehrt wird, dann strikt per ID filtern.

Recheck 2026-05-22: `eceb806` entfernt den Περιφερειάρχης-Regional-Branch aus `/rep/bills`; Περιφερειάρχης faellt damit konservativ auf PARLIAMENT-only zurueck. Finding geschlossen.

## NEA-186 Finding 3: `/rep/divergence/{bill_id}` lacks status gate — RESOLVED in `e2b6652`

Severity: MEDIUM

`/rep/divergence/{bill_id}` verwendet jetzt zwar `is_bill_visible_for_token()`, prueft aber weiterhin nicht `bill.status in ALLOWED_STATUSES`. Damit kann ein Vertreter fuer sichtbare PARLIAMENT-Bills Divergence-Daten direkt abrufen, auch wenn der Bill noch nicht in `WINDOW_24H`, `PARLIAMENT_VOTED` oder `OPEN_END` ist. Der Router-Header und `/rep/bills` definieren den Vertreterzugang aber explizit nur fuer diese Status.

Betroffene Stelle: `apps/api/routers/representative.py:get_rep_divergence()` nach dem Bill-Lookup; anders als `get_rep_results()` fehlt der Status-Check.

Fix fuer CC: In `/rep/divergence/{bill_id}` denselben Status-Gate wie in `/rep/results/{bill_id}` setzen, bevor Counts/Divergence berechnet werden. Test: ACTIVE/PENDING/ANNOUNCED PARLIAMENT Bill darf fuer MP/unknown nicht via `/rep/divergence` abrufbar sein.

Recheck 2026-05-22: `e2b6652` ergaenzt den Status-Gate in `/rep/divergence/{bill_id}` und aktualisiert den `/rep/bills` Docstring fuer Περιφερειάρχης PARLIAMENT-only. Finding geschlossen.

## NEA-186 Notes

- `python3 -m py_compile apps/api/routers/representative.py` ist lokal gruen.
- `X-Rep-Role` ist ASCII-safe (`MP/REGIONAL/MUNICIPAL/UNKNOWN`).
- Token-UPSERT schreibt `municipality` und erhaelt `evaluation_enabled`.
- Dashboard `municipality` ist im aktuellen Tree vorhanden, wurde aber nicht durch Commit `435f3bd` geaendert.
- App zeigt aktuell nur fuer `DIAVGEIA` ein Source-Badge; ein explizites `ΒΟΥΛΗ` Badge fuer `PARLIAMENT` ist nicht umgesetzt.

---

# CODEX FINDINGS — NEA-240
Datum: 2026-05-21
Agent: Codex
Scope: Root Cause Analyse 5 Bugs, read-only Produktcode/Server. Keine Produktcode-Aenderungen.

## Bug 1: region_locked

Root Cause: Nicht DB-seitig reproduziert. Live-DB hat aktuell keine `identity_records` mit `region_locked = TRUE`. Der Code setzt `region_locked` nur in `apps/api/routers/identity.py:update_profile_location()` und nur wenn nach dem Update `identity.periferia_id` oder `identity.dimos_id` gesetzt ist. Der wahrscheinliche UI-Root-Cause fuer "region_locked=TRUE ohne Region" ist Client-State-Drift: `ProfileScreen` liest `region_locked` vom Server, uebernimmt aber `st.periferia_id` / `st.dimos_id` nicht in `selectedPeriferia` / `selectedDimos`. Nach Account-Import fehlen lokale `user_periferia_id` / `user_dimos_id`, weil `ImportAccountScreen` nur Key, Nullifier, Pubkey und Onboarding/Profile-Flags speichert. Ergebnis: Server kann korrekt locked+Region haben, die App zeigt aber locked ohne lokale Region-Auswahl.

Fix fuer CC: In `ProfileScreen` beim Status-Load neben `region_locked` auch `periferia_id` und `dimos_id` aus `/identity/status` in State und SecureStore uebernehmen. In `ImportAccountScreen` optional Region-Parameter im Deep-Link unterstuetzen oder nach Import Profil-Region vom Server laden statt `user_profile_completed=true` blind zu setzen. Backend-seitig zusaetzlich eine Guard-Regel behalten: `region_locked` nie setzen, wenn beide IDs leer/0 sind.

## Bug 2: /politicians/ leer

Root Cause: Aktuell nicht mehr reproduzierbar. Live `GET https://api.ekklesia.gr/api/v1/politicians/` liefert `DEMO-123`. SQL zeigt genau einen Datensatz mit `evaluation_enabled = TRUE`: `DEMO-123 | Βουλευτής | t | Αττικής`. Der Router filtert strikt `WHERE rt.evaluation_enabled = TRUE`; wenn die Liste leer war, lag der Root Cause im Datenzustand/Opt-in, nicht im Router: keine `representative_tokens` mit gesetztem `evaluation_enabled`, abgelaufener/erneuerter DEMO-Token ohne Flag, oder Deploy vor Aktivierung.

Fix fuer CC: Demo-/Seed-/Admin-Flow idempotent machen: fuer `DEMO-123` nach Token-Erstellung/Erneuerung `evaluation_enabled=TRUE` setzen, oder im Dashboard/Rep-App sichtbar machen, ob Evaluation aktiviert ist. Optional `/politicians/` mit Debug-Metadaten fuer Admins ergaenzen: `enabled_count`, `total_tokens`, `expired_enabled_count`.

## Bug 3+4: Scraper

Root Cause: APScheduler Jobs sind nur in-process im API-Container definiert (`AsyncIOScheduler`, `IntervalTrigger`). Persistiert wird nur Ausfuehrungszustand in Redis (`scraper:{name}:last_run`, `last_success`, `error_count`) ueber `services/scraper_state.py`; es gibt keinen persistenten APScheduler JobStore und keinen Catch-up beim API-Start. Bei Container-Restart starten die Intervalle neu ab Prozessstart. Dadurch laufen `parliament_scrape` erst nach 12h und `diavgeia_municipal` erst nach 48h, auch wenn `last_run` bereits alt ist. Live `/api/v1/scraper/jobs` bestaetigt Drift: `parliament` last_run 2026-05-18, `diavgeia_municipal` last_run 2026-05-12, waehrend andere Jobs nach Restart laufen.

Fix fuer CC: Beim API-Startup Catch-up aus Redis implementieren: wenn `now - last_run >= interval`, Job sofort einmal triggern oder zeitnah `next_run_time=now` setzen. Alternativ APScheduler mit persistentem Redis/SQLAlchemy JobStore oder externe Cron/worker fuer Parliament/Diavgeia. Monitor Rule sollte nicht nur alerten, sondern klar zwischen "scheduler due but not run" und "scraper failed" unterscheiden.

## Bug 5: Forum

Root Cause: Discourse erlaubt keine Subkategorie unter einer Subkategorie. Die 3 fehlenden Bills sind `DIAVGEIA` + `MUNICIPAL` + `OPEN_END` mit `forum_topic_id IS NULL`. `_resolve_category()` routet MUNICIPAL zu `Τοπική Αυτοδιοίκηση -> Περιφέρεια X -> Δήμος Y` und versucht damit eine dritte Kategorie-Ebene. Live-Logs zeigen exakt: `Δεν μπορείτε να βάλετε μια υποκατηγορία κάτω από άλλη` fuer `Οιχαλίας`, `Σιντικής`, `Αγρινίου`. Zusaetzlicher Monitoring-Root-Cause: `sync_new_bills_to_forum()` catcht Fehler pro Bill und raised nicht weiter; `scheduled_forum_sync()` ruft danach trotzdem `record_success()`, wodurch `error_count` wieder 0 wird und der Fehler als erfolgreicher Forum-Sync erscheint.

Fix fuer CC: Discourse-Kategorie-Strategie fuer MUNICIPAL flach machen: entweder `Τοπική Αυτοδιοίκηση -> Δήμος X` direkt, oder `Περιφέρεια X` als Tag statt Parent, oder alle municipal Diavgeia unter eine erlaubte zweite Ebene posten. Danach die 3 Bills resyncen. Ausserdem `sync_new_bills_to_forum()` soll failed count zurueckgeben oder bei Fehlern raisen, damit `record_failure("forum_sync", ...)` nicht von `record_success()` ueberschrieben wird.
