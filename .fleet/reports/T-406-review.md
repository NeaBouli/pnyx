id: T-406
verdict: ok
- EKA-01 (2890987): Root cause belegt (alter Aufruf mit falschen kwargs + `except Exception` → nur Warnung). Jetzt: kanonische VotePayload, sobald ein Tier-1-Feld gesetzt ist → Enforcement; Teil-Payload 400, INVALID_SIGNATURE 401, DUPLICATE 409, Backendfehler 503. Alles vor jedem DB-Write, Identity-Signatur bleibt Pflicht.
- EKA-12 (bf6d72d): Beide keypair-Module geben False nur bei BadSignature/ValueError/Nicht-str zurück, sonst SignatureVerificationError. nullifier.validate_vote wirft Tier1CryptoBackendError statt CRYPTO_ERROR. Geloggt wird nur der Exception-Typ, kein Key/Payload/PII.
- Review-Fix 9bf02d7: Duplikat-Lookup per `func.lower(vote_nullifier) == input.lower()` erledigt Befund 2 der Vorreview. Eigene Zeile desselben Bürgers/Bills ist ausgenommen (Stimmänderung). Test für Groß-/Kleinschreibung vorhanden.
- Commits getrennt. Kein Schema/Migration/Config/Mobile/Web. `tier1_signature_hex` ist optional, der Legacy-Clientpfad bleibt unverändert → kein API-Break.
- Re-Lauf Reviewer: fokussiert 54 passed. Breite Gruppe `-k vote|tier|zk|signature|nullifier|keypair`: 455 passed, 4 xfailed, 3 failed.
  Die 3 Fehler sind die bekannten S10-ZK-Canary-Fixture-Tests (test_zk_verify_api ×2, test_zk_groth16_verifier ×1). Der Diff berührt keine ZK-Dateien → Vorbestand, kein Regress.
- Nicht-blockierend / Follow-up:
  1. Stimmänderungspfad (existing_vote) validiert Tier-1, schreibt aber pk_eph/vote_nullifier/linkage_tag/timestamp_ms nicht neu. Gespeicherte Tier-1-Daten können dann zur alten Wahl gehören. Vorbestand, nicht verschärft.
  2. `func.lower()` auf vote_nullifier umgeht einen etwaigen Index → besser Nullifier beim Schreiben normalisieren (eigenes Ticket, braucht ggf. Datenmigration).
  3. Tier-1-Signatur bindet nullifier_hash nicht; die Duplikatprüfung ist check-then-insert ohne UNIQUE auf vote_nullifier (TOCTOU). ADR-022-Designfrage, out of scope.
  4. SignatureVerificationError wird außerhalb voting nicht gemappt → 500 statt 503 (fail-closed). polis_qr/polis.py verschlucken weiterhin; eigenes Ticket.
- Status korrekt: nicht gepusht/gemergt/deployt. Worktree sauber bis auf diesen Report.
