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
