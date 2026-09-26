id: T-406
verdict: ok
- EKA-01: Root cause bestätigt (alter Router rief validate_vote mit nicht existierenden kwargs, `except Exception` → nur Warnung). Neu: kanonische VotePayload, Enforcement sobald irgendein Tier-1-Feld gesendet wird, Teil-Payload → 400, INVALID_SIGNATURE → 401, DUPLICATE → 409, Backendfehler → 503, jeweils vor dem Write.
- EKA-12: beide keypair-Module (packages/crypto = Runtime, apps/api = Mirror) geben False nur für BadSignature/ValueError/Nicht-str; sonst typisierte SignatureVerificationError, Logging nur Exception-Typ (kein Key/PII). nullifier.validate_vote: CRYPTO_ERROR-Maskierung ersetzt durch Tier1CryptoBackendError.
- Commits getrennt (2890987 EKA-01, bf6d72d EKA-12). Kein Schema/Migration/Config/Mobile/Web. Bestehende Clients: tier1_signature_hex optional, Legacy-Pfad unverändert (Test vorhanden). Identity-Signatur bleibt Pflicht.
- Tests: Negativtest für alten kwarg-Mismatch + Swallow-Pfad vorhanden; Tampered/Wrong-PK/Other-Bill/Other-Choice/Expired/Malformed/Incomplete/Duplicate/Backend-503/no-row abgedeckt. Reviewer-Lauf: 53 passed (0.95s).
- Nicht-blockierend:
  1. Full-API-Suite-Nachweis nur per Exit-Marker, ohne Zahlensumme; 3 ZK-Canary-Tests deselektiert — vor Merge in CI mit Summary bestätigen.
  2. Tier-1-Duplikatprüfung vergleicht vote_nullifier als String; Groß-/Kleinschreibung desselben Hex umgeht `used_nullifiers` (Signatur gilt für Bytes). Durch Identity-Nullifier-Gate abgefedert; Normalisierung `.lower()` als Follow-up.
  3. SignatureVerificationError wird in übrigen Routern (sso, identity, zk, municipal, …) nicht abgefangen → HTTP 500 statt 503; fail-closed, aber uneinheitlich.
  4. Außerhalb Scope weiter verschluckend: routers/polis_qr.py verify_challenge (`except Exception: return False`), crypto/polis.py CRYPTO_ERROR (2×). Eigenes Ticket empfohlen.
- Status: nicht gepusht/gemergt/deployt — korrekt berichtet.
