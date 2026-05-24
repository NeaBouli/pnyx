# CODEX FINDINGS — NEA-242 / NEA-186 / NEA-240

Datum: 2026-05-23
Agent: Codex
Scope: Final-Recheck Audit-B-Fixes NEA-252 bis NEA-255, read-only Produktcode. Keine Produktcode-Aenderungen durch Codex.

## Audit B Security Fixes Batch 2 — ACCEPTED

### NEA-252: Municipal vote without Ed25519 signature — RESOLVED in `1bc3b39`

Severity: HIGH

`POST /municipal/vote` verlangt jetzt `signature_hex` in `DecisionVoteRequest`. Der kanonische Payload ist `municipal:{ada}:{VOTE}:{nullifier_hash}`. Die API laedt die Identity ueber `nullifier_hash`, prueft `verify_signature(identity.public_key_hex, payload, req.signature_hex)` vor Duplikat-Check und DB-Write, gibt bei ungueltiger Signatur 401 und bei fehlender Signatur Pydantic 422 zurueck. Kein aktiver Mobile/Web-Caller gefunden. Finding geschlossen.

### NEA-253: Relevance signal without signature — RESOLVED in `4ce07e6`

Severity: MEDIUM

`RelevanceRequest` verlangt jetzt `signature_hex`. Der kanonische Payload ist `relevance:{bill_id}:{signal}:{nullifier_hash}`. Die API verifiziert die Ed25519-Signatur vor dem Upsert. Ungueltige Signatur fuehrt zu 401, fehlende Signatur zu 422. Der aktive Web-Caller `RelevanceButtons.tsx` signiert jetzt via `signPayload()`. Mobile nutzt diesen Endpoint nicht direkt. Finding geschlossen.

### NEA-254: Receipt/personal compass used nullifier as bearer secret — RESOLVED in `73952cc`

Severity: MEDIUM

Die alten GET-Endpunkte fuer Receipt und `compass/personal` geben jetzt 410 deprecated zurueck. Neue signed POST-Endpunkte verwenden `receipt:{bill_id}:{nullifier_hash}` bzw. `compass_personal:{nullifier_hash}` als Payload und pruefen Ed25519 vor Rueckgabe persoenlicher Daten. Receipt gibt keinen vollen `nullifier_hash` mehr zurueck, sondern nur `nullifier_prefix`. Keine aktiven Mobile/Web-Caller gefunden. Finding geschlossen.

### NEA-255: Finance admin detail endpoints lacked admin auth — RESOLVED in `1ff0394`

Severity: MEDIUM

`/payments/admin/finance/server`, `/payments/admin/finance/btc` und `/payments/admin/finance/ltc` sind jetzt mit `verify_admin_key` geschuetzt. Public/community-safe Endpunkte (`/payments/status`, `/payments/public/finance`) bleiben unveraendert. Dashboard nutzt diese drei Detail-Endpunkte nicht, daher war kein Caller-Update noetig. Finding geschlossen.

Restliche Audit-B-Items:

- Alembic history cannot reproduce production schema: offen, separater Schema-Baseline/ADR-Task.
- Security-audit CI soft-fails dependency audits: offen.
- Public API key generation lacks explicit endpoint-level rate limit: LOW, offen.
- README/CLAUDE.md stale: INFO, offen.

---

Datum: 2026-05-23
Agent: Codex
Scope: Final-Recheck NEA-251 Commit `272f73a`, read-only Produktcode. Keine Produktcode-Aenderungen durch Codex.

## NEA-251 Finding: Discourse SSO callback lacked private-key possession proof — RESOLVED in `272f73a`

Severity: HIGH

Audit B hatte festgestellt, dass `POST /api/v1/sso/discourse/callback` mit `nonce + public_key_hex` auskam. Damit konnte ein Angreifer, der eine gueltige `public_key_hex` kannte, einen aktiven Discourse-SSO-Nonce fuer diese Identitaet einloesen, ohne den privaten Schluessel zu besitzen.

Recheck 2026-05-23: `272f73a` macht `signature_hex` verpflichtend und prueft vor dem Identity-Lookup eine Ed25519-Signatur ueber `discourse_sso:{nonce}:{public_key_hex}`. Invalid signature fuehrt zu 401. Die bestehende Discourse-HMAC-Pruefung im Initiate-Flow bleibt unveraendert. Der Discourse `external_id` wird nicht mehr aus dem rohen `nullifier_hash` gebaut, sondern aus `HMAC(FORUM_SSO_SALT, nullifier_hash)`. Next.js `sso-verify` signiert die Challenge clientseitig via `signPayload()`, die statische HTML-Seite leitet auf die Next.js-Route um.

Verifikation:

- `python3 -m py_compile apps/api/routers/sso.py` OK.
- `@noble/curves` Ed25519 Signaturformat lokal geprueft: Public Key 64 Hex-Zeichen, Signature 128 Hex-Zeichen, Verify true.
- Keine Produktcode-Blocker im Recheck.

Low Hygiene Note: `FORUM_SSO_SALT` faellt aktuell auf `SERVER_SALT` und danach auf leeren String zurueck. Produktion sollte explizit `FORUM_SSO_SALT` oder mindestens `SERVER_SALT` gesetzt haben; fail-closed Startup-Check waere ein sauberer Follow-up, aber kein Blocker fuer NEA-251.

---

Datum: 2026-05-23
Agent: Codex
Scope: Final-Recheck NEA-242 commits `e0fc7b3`, `3684ec6`, `41bc682`, read-only Produktcode. Keine Produktcode-Aenderungen durch Codex.

## NEA-242 Finding 1: audit_log schema not reproducible — RESOLVED in `3684ec6`

Severity: HIGH

Initial commit `e0fc7b3` wrote to `audit_log`, but the repo did not define/create that table. Fresh local/dev deploys could fail on `POST /admin/test-account` if the table existed only by manual server SQL.

Recheck 2026-05-23: `3684ec6` adds `AuditLog` ORM model and switches `admin_account.py` from raw SQL insert to `db.add(AuditLog(...))`. Finding geschlossen.

## NEA-242 Finding 2: AuditLog UUID default type mismatch — RESOLVED in `41bc682`

Severity: MEDIUM/HIGH

`3684ec6` initially declared `AuditLog.id` as `String(36)` while using `server_default=text("gen_random_uuid()")`, which can fail on fresh PostgreSQL DDL because the default expression is UUID, not VARCHAR.

Recheck 2026-05-23: `41bc682` imports PostgreSQL `UUID` and changes `id` to `Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))`. Finding geschlossen.

## NEA-242 Accepted State

- `identity_records.source` exists with default `SMS`.
- Admin-created test accounts set `source="ADMIN_TEST"`.
- Audit row is written in the same transaction path as the identity record.
- JSONB metadata is bound through SQLAlchemy ORM.
- No private key, token, phone number, or full nullifier is written to audit metadata.
- Dashboard display of `source` remains optional follow-up, not blocker.

---

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

---

# CODEX FINDINGS — Next 16 Web Upgrade / PR #70
Datum: 2026-05-22
Agent: Codex
Scope: GitHub PR #70 Audit, CI/CodeRabbit Recheck. Keine Produktcode-Aenderungen durch Codex.

## Ergebnis

- PR #70 ersetzt Dependabot PRs #64 und #69.
- CI nach Rebase auf `59c9d8c` gruen.
- CodeRabbit: keine actionable Findings.
- Merge: abgeschlossen mit Commit `2d9faac665fc400a5af811d8cc27e265fd387f90`.
- #64 geschlossen; #69 war bereits geschlossen.

## Residual Notes

- CodeRabbit ignorierte `apps/web/package-lock.json` wegen Path-Filter; lokaler/CI Build war deshalb entscheidend.
- CI-Test-Fix auf main nutzt `any("MOD-01" in m ...)`; besser waere bei spaeterem Cleanup `m.startswith("MOD-01")`. Kein Blocker.

---

# CODEX FINDINGS — NEA-234 ZK Voting Protocol Research
Datum: 2026-05-22
Agent: Codex
Scope: Architektur-Recherche Semaphore vs Helios vs Hybrid. Keine Produktcode-Aenderungen.

## Ergebnis

Empfehlung: Hybrid V2.

- Semaphore als optionaler Membership-/Nullifier-Proof Layer ist fuer CX43 + Mobile realistisch.
- Helios ist technisch stark, aber als naechster Bau fuer ekklesia zu schwer und trustee-operativ riskant.
- Hybrid muss ein public per-vote/proof bulletin board enthalten; aggregate-only Arweave beweist nicht genug.

## Wichtige Grenzen

- Keine custom trusted setup ceremony fuer MVP.
- Keine server-side proving pipeline.
- Kein Full-Helios-Trustee-System jetzt.
- Mobile Proof Generation zuerst benchmarken, bevorzugt Mopro/SemaphoreReactNative statt plain `snarkjs`.
---

# CODEX FINDINGS — NEA-268 org_label Forum Titles
Datum: 2026-05-24
Agent: Codex
Scope: Recheck Commits `49d5780` und `417b72d`; Produktcode nur gelesen, keine Produktcode-Aenderungen.

## Finding 1: unknown org labels werden in parliament_bills und Forum-Titel uebernommen — RESOLVED in `3e965de`

Severity: MEDIUM

Der NEA-268 Prompt verlangte explizit, dass keine unknown-Werte als echte Labels gespeichert oder im Titel genutzt werden. Der aktuelle Commit uebernimmt solche Werte aber weiterhin:

- `apps/api/alembic/versions/m601a2b3c4d5_bill_org_label.py:23` backfillt alle `dd.organization_label IS NOT NULL`; Werte wie `[unknown:...]` oder `unknown` werden nicht ausgeschlossen.
- `apps/api/services/diavgeia_scraper.py:255` setzt `org_label=org_label or None`; der Scraper erzeugt aber weiter `[unknown:...]` aus `get_org_label()` und speichert es damit fuer neue Bills.
- `apps/api/services/discourse_sync.py:143` nutzt jedes truthy `bill.org_label`; daraus entstehen Forum-Titel wie `[Φορέας [unknown:XXXXX]] ...`.

Fix fuer CC:

- Einen kleinen Helper fuer saubere Org-Labels einfuehren, z. B. `None` fuer leer, whitespace, `unknown`, `[unknown:...]`.
- Helper beim Diavgeia→Bill-Import verwenden.
- Helper in `_build_topic_title()` verwenden; bei unsauberem Label fallback auf `Φορέας`.
- Migration-Backfill SQL um `NOT ILIKE 'unknown'` / `NOT LIKE '[unknown:%'` / `btrim(...) <> ''` erweitern.
- Tests ergaenzen: `[unknown:ORG]`, `unknown`, whitespace muessen `[Φορέας]` ergeben und nicht `[Φορέας unknown]`.

Recheck 2026-05-24: `3e965de` fuehrt `_clean_org_label()` ein, filtert bad labels im Diavgeia→Bill-Import, filtert defensiv im Forum-Titel und erweitert das Migration-Backfill-SQL um blank/unknown/[unknown:%]-Guards. Neue Tests decken Helper und Forum-Fallback fuer bad labels ab. Finding geschlossen.

## Recheck Notes

- `49d5780` NEA-265 Commit-Scope passt: nur `apps/api/services/discourse_sync.py` und `apps/api/tests/services/test_discourse_sync.py`.
- `417b72d` Migration-Kette passt syntaktisch (`down_revision = l501a2b3c4d5`).
- `diavgeia_decisions.organization_label` ist die korrekte Quellspalte.
- Checks lokal:
  - `/tmp/pnyx-discourse-test-venv/bin/python -m pytest apps/api/tests/services/test_discourse_sync.py -q` → `15 passed, 1 warning`
  - `/tmp/pnyx-discourse-test-venv/bin/python -m py_compile apps/api/models.py apps/api/services/diavgeia_scraper.py apps/api/services/discourse_sync.py apps/api/tests/services/test_discourse_sync.py` → OK
  - `/tmp/pnyx-discourse-test-venv/bin/python -m py_compile apps/api/alembic/versions/m601a2b3c4d5_bill_org_label.py` → OK
  - Migration sanity fuer `down_revision`, `TRIM`, blank/unknown/[unknown:%]-Filter → OK

---

Datum: 2026-05-22
Agent: Codex
Scope: Audit-Recheck Commit `435f3bd` (NEA-186 rep role-based bill visibility), read-only Produktcode. Keine Produktcode-Aenderungen.
