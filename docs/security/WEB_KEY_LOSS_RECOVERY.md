# Web identity key loss and recovery

T-9139 · 2026-10-17 · Design after #599/#614.
Status: Accepted in part — holder proof and legacy takeover-risk policy,
support for users without the app, multi-device authority/revocation and
privacy/retention remain open.
Evidence is local; browser policy links were not fetched (offline task).

## Decision record 2026-10-17

Owner: gio-1c (technical), under Gio standing yes.

Accepted: the mobile app provides primary key custody; web uses QR login, shows
a clear “Key not found on this browser” notice after confirmed key absence,
and offers no key export. The remaining recovery decisions stay open as listed
below.

## What can fail, and how realistic is it?

IndexedDB holds a non-extractable Ed25519 key and an independent,
non-extractable Compass AES key. Persistence is best effort, not a backup
(`apps/web/src/lib/keystore.ts:62`, `:136`, `:443`, `:571`).
There are no loss-rate measurements here; these are qualitative assessments.

| Failure | Realistic exposure |
| --- | --- |
| Safari ITP | Material risk for occasional visitors: script-writable storage, including IndexedDB/localStorage, can be deleted after seven days **of Safari use without site interaction**, not seven calendar days. Home Screen web apps have separate treatment; do not promise installation or `persist()` prevents deletion. |
| Private browsing | Storage normally disappears when the private session ends; some configurations reject it altogether. Unsuitable for primary custody. |
| Quota / storage pressure | Keys are tiny, but the whole origin can be evicted under pressure. Quota write failures differ from eviction. Granted persistence reduces pressure eviction where supported, without guaranteeing survival. |
| Clear site data / remove profile | Predictable loss when site storage is deleted. Clearing only the HTTP cache need not delete IndexedDB. |
| Device loss / reinstall / another browser | No automatic key transfer. Frequency depends on the user; access is lost if no usable copy remains. |

Policy references: [WebKit ITP storage cap](https://webkit.org/blog/10218/full-third-party-cookie-blocking-and-more/)
and [WebKit storage policy](https://webkit.org/blog/14403/updates-to-storage-policy/).
Local acknowledgement: `docs/security/WEB_KEY_ROTATION.md:22`.

## What the user loses

- **Voting from this browser**, personal vote-status reads, and corrections
  require the current signature, another authorised device or successful recovery
  (`apps/web/src/lib/api.ts:27`, `apps/api/routers/voting.py:730`, `:898`, `:994`).
  Submitted votes remain stored. Preserve the compatibility nullifier,
  duplicate-vote checks, correction count and deadline; recovery delays may
  exhaust the correction window
  (`apps/api/routers/identity.py:444`, `apps/api/routers/voting.py:828`, `:947`, `:978`).
  Legacy unsigned status access is a residual exposure, not a recovery method
  (`docs/security/VOTE_STATUS_READ_MIGRATION.md:61`).
- **Compass answers, signals, preferences and local vote history** are lost
  with deleted ciphertext or a lost AES key. A new identity key cannot restore them
  (`apps/web/src/lib/compass/types.ts:51`, `apps/web/src/lib/compass/storage.ts:221`,
  `apps/web/src/lib/keystore.ts:564`). Re-verification does not restore Compass;
  the current registration flow also deletes server VAA survey responses
  (`apps/api/routers/identity.py:502`).

## Options

**(a) Re-verification and detection.** First retry pending rotation. Read
IndexedDB under the keystore lock; distinguish absent, unreadable/corrupt,
and present-but-unusable keys. Today
`loadIdentityRecord` turns read errors into `null`, and the synchronous custody
marker is only a hint (`apps/web/src/lib/keystore.ts:165`, `:236`, `:493`, `:545`).
Only a successful empty read means “key not found”; errors get retry guidance
without overwriting records. Local markers suggest prior use, but complete
clearing is indistinguishable from a first visit.

The server recognises identities by their anchor. Avoid an account-existence
oracle: before independent holder proof, give existing/unknown identities the
same status, body and bounded timing behaviour; rate-limit before lookups or
paid checks. Existing unsigned status and v2's `IDENTITY_ACTIVE` preflight
already distinguish identities; recovery needs server-side generic responses,
not merely hidden UI (`apps/api/routers/identity.py:394`, `:405`, `:600`).
After approved holder proof, bind a short-lived, single-use authorisation to
the new key, confirm replacement, preserve the anchor and invalidate the old
key/sessions. Exclude phones, anchors and key material from logs/analytics.

**Critical limit — EVA-001 / EVA-010:** legacy verification generates a new
key and replaces an ACTIVE identity without the old signature
(`apps/api/routers/identity.py:439`, `:449`, `:464`). HLR checks number status,
not SIM possession or identity (`docs/memo/MASTER_MEMO.md:94`). Calling that
flow “recovery” preserves the takeover risk. V2 is flag-gated, rejects ACTIVE
re-registration, and rotation requires both old and new signatures
(`apps/api/routers/identity.py:836`, `:889`, `:431`, `:975`). Total key loss
therefore has **no safe v2 recovery route today**. Do not fall back to v1 or
use phone-based revoke then v2 registration to bypass this protection
(`apps/api/routers/identity.py:554`, `:582`). SMS proves SIM access only, with
SIM-swap/recycled-number risks; owners must choose acceptable holder proof.

**(b) Encrypted backup file or passkey-wrapped key.** A portable file could
contain identity credentials and, optionally, Compass recovery material/data,
using authenticated encryption and a strong passphrase with a costly, salted
password KDF. Version/authenticate metadata. Risks include forgotten passwords,
offline guessing and XSS stealing bytes during export/restore. Validate restored
possession and the current server key; stale backups must not reactivate old keys.

WebAuthn PRF could derive a wrapping key after user verification. Retain the
encrypted payload outside the browser: a passkey alone backs up none of these
keys/data. Test browser, authenticator and cross-device PRF support; provider
or passkey loss adds a dependency. Neither `exportKey` nor `wrapKey` can export an
existing non-extractable key. Both approaches require a deliberate custody
exception at creation/rotation, or a separately enrolled recovery authority;
they cannot retrofit export after loss (`apps/web/src/lib/keystore.ts:443`, `:571`).
Compass can separately export an encrypted profile snapshot while decryptable,
without exporting its AES key. Do not promise identity backup restores Compass.

**(c) Mobile as primary custody — recommended now.** Prefer SecureStore and
browser QR actions while the app retains the current key. Phone loss/uninstall
still needs a plan. Mobile reads key bytes into application memory; do not
claim hardware signing or equivalent non-extractability
(`apps/mobile/src/lib/crypto-native.ts:189`, `:222`, `:239`). QR already verifies
the app signature and rejects sessions for replaced keys; corrections require
the app (`apps/api/routers/polis_qr.py:268`, `:339`, `:386`). Installing the app
after losing a browser-only key does not restore it.

**(d) Multi-device.** Independent keys enrolled by a current holder need device
listing, revocation and recovery rules. This requires a new server model:
today each identity has one current public key, and rotation
replaces it (`apps/api/models.py:57`, `apps/api/routers/identity.py:992`). Copying
one key weakens non-extractable custody and prevents individual revocation;
QR delegation avoids copying but depends on the phone. A second device helps
only if enrolled before loss. Compass sync is a separate, opt-in encrypted-data
design.

## ADR interaction, recommendation and owner decisions

The full ADR-006/007 texts are absent from this checkout; reconcile these
implementation references with the originals before approving a recovery design.

- **ADR-006:** do not reconstruct secrets from a phone number; D1 forbids
  phone-derived roots (`apps/mobile/src/lib/crypto-native.ts:119`, `:198`).
  D6 keeps the identity signature mandatory; Tier-1 metadata cannot authorise
  recovery (`apps/api/routers/voting.py:459`). Preserve non-extractable web
  custody and old-key-authorised rotation unless an explicit exception is agreed.
- **ADR-007:** recovery must retain pseudonymous ordinary-vote wording (S1),
  never expose personal status through public aggregates (S2), and never imply
  encrypted server backups restore browser secrets (S3)
  (`scripts/redesign/approved_analytics_delta.py:55`,
  `docs/operations/PUBLIC_RESULTS_PRIVACY.md:3`, `scripts/lib/backup-encrypt.sh:2`).
  Recovery metadata and any hosted encrypted payload need retention/privacy review.

Use mobile custody plus QR login on web, clear browser-loss detection and honest
Compass loss disclosure first; no key export. Keep multi-device as a separate
design. The FAQ's automatic passkey-sync promise needs correction in a later
task (`docs/wiki/faq.html:334`).

Gio/product and security owners still must decide: (1) acceptable holder proof and
legacy takeover-risk policy before offering replacement; (2) support for users
without the app; (3) single-key versus multiple-device authority, revocation and
privacy/retention.
No production flags or recovery guarantees follow from this decision record.

## Proposed UX copy (EL / EN)

Show after confirmed absence; it asserts only this browser's local state.

| | EL | EN |
| --- | --- | --- |
| Title | Δεν βρέθηκε κλειδί σε αυτόν τον browser. | Key not found on this browser. |
| Body | Για να ψηφίσετε, να δείτε την ψήφο σας ή να τη διορθώσετε, χρησιμοποιήστε την εφαρμογή όπου έχετε ήδη την ταυτότητά σας. Αν δεν έχετε πρόσβαση σε αυτήν, δείτε τις επιλογές ανάκτησης. Οι ήδη καταχωρημένες ψήφοι σας παραμένουν. | To vote, view your vote or correct it, use the app where you already have your identity. If you cannot access it, view recovery options. Your submitted votes remain recorded. |
| Actions | Χρήση εφαρμογής · Επιλογές ανάκτησης | Use the app · Recovery options |
| Recovery disclosure | Η εκ νέου επαλήθευση δεν επαναφέρει τα χαμένα δεδομένα του Compass. Η αντικατάσταση κλειδιού απαιτεί διαθέσιμη, εγκεκριμένη διαδικασία ανάκτησης. | Re-verification does not restore lost Compass data. Replacing a key requires an available, approved recovery process. |
| Storage read error | Δεν ήταν δυνατή η πρόσβαση στο κλειδί. Ελέγξτε τις ρυθμίσεις αποθήκευσης του browser και δοκιμάστε ξανά. | Your key could not be accessed. Check your browser's storage settings and try again. |

Offer “Verify again” / “Επαλήθευση ξανά” only when the approved flow is
available. Until then, recovery options explain the limitation; they must not
silently invoke legacy re-registration or promise that an identity exists.
