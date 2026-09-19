# Vote-status read and bill-flag signature migration (EKA-03)

Status: implementation and tests; not a production cutoff or app release.

## Scope and threat model

The vote-status GET route accepted a nullifier as a bare query parameter and
the bill-flag POST accepted a bare `X-Nullifier` header. A disclosed nullifier
could therefore expose whether a citizen voted on a specific bill (and how),
and could submit flags in their name. This change adds Ed25519 proof of
possession without changing votes, vote semantics, flag counts, eligibility,
identity storage, public aggregates or database schema.

Signatures bind the exact operation, target, nullifier and timestamp. A flag
signature cannot authorize a vote-status read and vice versa, and neither can
authorize voting, correction, receipts or evaluation. Only ACTIVE identity
keys are accepted. Missing and revoked identities share the same generic
invalid-signature 401 status and body. Invalid or partial signed requests never
fall back to unsigned access.

The flag endpoint has no legacy path: repository history proves no shipped
client ever called it, so the bare-header form is removed outright. The
vote-status GET remains as a bounded legacy transition path only.

## Wire contract

`POST /api/v1/vote/{bill_id}/status` returns the same JSON body as the legacy
`GET /api/v1/vote/{bill_id}/status`. `POST /api/v1/bills/{bill_id}/flag`
keeps its existing success body. Both accept only this JSON body; unknown
fields are rejected:

```json
{"nullifier_hash":"<64 hex>","timestamp_ms":1788000000000,"signature_hex":"<128 hex>"}
```

`timestamp_ms` must be a non-negative JavaScript-safe integer and pass the
bounded `CITIZEN_ACTION_MAX_SKEW_MS` freshness window (default 15 minutes,
configuration bounded to 1-60 minutes). The exact UTF-8 payloads are compact
JSON arrays, identical under Python `ensure_ascii=False` and JavaScript
`JSON.stringify`, with no Unicode normalization:

```
flag:v1:["GR-0490a766","<nullifier>",1788000000000]
vote-status-read:v1:["GR-0490a766","<nullifier>",1788000000000]
```

Personal responses use `Cache-Control: private, no-store`. The vote-status
response header `X-Vote-Read-Integrity: signed|legacy` identifies the server
path. Signatures are not put in URLs, no private key leaves the device, and
new mobile clients send no mirror or unsigned fallback for these reads. If
key material is unavailable on the device, no status request is made at all.
Duplicate flags keep the existing 409; only integrity conflicts map to 409,
while non-integrity database failures are no longer masked as duplicates.

## Residual risk during migration

Unsigned vote-status GETs remain accepted while `VOTE_STATUS_REQUIRE_SIGNED`
is unset or false. Consequently **this source PR alone does NOT close
EKA-03**: an attacker can deliberately use the legacy GET until cutoff.
Captured signed requests remain replayable for the same read within the
freshness window; no one-shot nonce or database writes are introduced for
reads. The pre-existing nullifier query parameter on the legacy GET still
needs appropriate access-log handling. Do not log request bodies, keys,
signatures or nullifiers; the server logs only scope-only PII-free markers for
signed and legacy reads.

The identity lookup and signature-verification paths are not guaranteed to be
timing-identical for an unknown versus an ACTIVE nullifier. This does not alter
the generic HTTP response, and exploitation requires a previously known opaque
64-hex nullifier plus precise timing measurements. It remains a documented
low-risk side channel for future hardening.

## Ordered release gates

1. Review and merge the additive API/mobile changes with all required CI.
2. Through a separately authorized API rollout, verify signed and legacy
   vote-status reads and signed flags against synthetic canaries, with the
   cutoff disabled. An old API may not know the POST route, so verify the
   `X-Vote-Read-Integrity: signed` response header before releasing the app.
   Do not infer API readiness from the app build alone.
3. Build/sign a new versioned Android release through the normal APK/AAB
   workflow; check vote-status prefill, correction windows, flagging, wrong
   device clock and supported distribution channels. Keep existing published
   download/version metadata until the new artifacts are available.
4. Collect adoption evidence for signed vote-status reads. The server logs
   scope-only signed/legacy markers, never nullifiers. No legacy calls in a
   quiet interval is not sufficient proof that older active users have
   upgraded. Reconcile with the release/tester evidence.
5. Only after adoption, separately authorize the reversible production
   setting `VOTE_STATUS_REQUIRE_SIGNED=true`. Legacy GETs then receive 426
   without any database access, while signed POSTs keep working. Verify old
   clients receive 426 and current clients retain status prefill and
   correction flows. Do not switch it during this code task.
6. Remove the legacy GET transition path only after a stable cutoff and a
   follow-up review. The obsolete `X-Nullifier` CORS allowance is already
   removed with the signed flag contract. Keep EKA-03 open until all gates have
   actual evidence.

Rollback: keep the previous API image and recorded prior flag value. If a
later authorized cutoff breaks supported clients, restore the prior flag
under the approved rollback procedure. Reverting to unsigned compatibility
reopens the documented exposure and must be recorded as such. No database
rollback is needed for this patch.

## Verification

HTTP tests cover both routes, golden vectors, valid flows, response parity
between signed POST and legacy GET, target/owner/time/key/operation
tampering, stale and future requests, unknown/revoked identity
indistinguishability, partial and malformed bodies, no-store and integrity
headers, duplicate-flag 409, unmasked database failures and the reversible
426 cutoff without database access. Mobile tests cover payload construction,
golden vectors, signature binding, POST transport without caching, and the
absence of mirror or unsigned fallbacks.
