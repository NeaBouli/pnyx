# Personal evaluation read migration (GH #253)

Status: implementation and tests; not a production cutoff or app release.

## Scope and threat model

The existing personal score and history GET routes accept a nullifier alone.
A disclosed nullifier can therefore expose a citizen's individual evaluations;
public aggregate k-anonymity does not protect those routes. This change adds
Ed25519 proof of possession without changing scores, regional eligibility,
identity storage, public aggregates or database schema.

Signatures bind the exact target, nullifier and timestamp. A signature for a
single representative cannot authorize another representative or a bulk read,
and evaluation-write signatures cannot authorize reads. Only ACTIVE identity
keys are accepted. Invalid or partial signatures never fall back to unsigned
access. Missing and revoked identities share the invalid-signature response.

## Wire contract

Both existing GET URLs and JSON response bodies are preserved:

- `/api/v1/politicians/{ada_number}/my-evaluation?nullifier_hash=...`
- `/api/v1/politicians/my-evaluations/bulk?nullifier_hash=...`

New clients always send `X-Evaluation-Read-Timestamp` (integer milliseconds) and
`X-Evaluation-Read-Signature` (128 hexadecimal characters) as headers. The exact
UTF-8 payload is `evaluation-read:v1:` followed by compact JSON:

```json
["ADA-EXAMPLE","nullifier",1788000000000]
```

Bulk uses JSON `null` in place of the ADA string. No Unicode normalization is
performed. Python `ensure_ascii=False` and JavaScript `JSON.stringify` produce
the same golden vectors. Timestamps must be non-negative JavaScript-safe
integers and pass the existing bounded `EVALUATION_V2_MAX_SKEW_MS` window
(default 15 minutes, configuration bounded to 1-60 minutes).

Personal responses use `Cache-Control: private, no-store`. Signatures are not
put in URLs, no private key leaves the device, and personal reads do not use
the public mirror fallback. New mobile clients never retry unsigned after an
authentication or transport error. The response header
`X-Evaluation-Read-Integrity: signed|legacy` identifies the server path.

## Residual risk during migration

Unsigned requests remain accepted while `EVALUATION_REQUIRE_V2` is unset or
false. Consequently this PR alone does NOT close the nullifier-only access
exposure: an attacker can deliberately omit both headers until cutoff.
Captured signed requests remain replayable for the same read within the
freshness window; no one-shot nonce or database writes are introduced.
The pre-existing nullifier query parameter still needs appropriate access-log
handling. Do not log request headers, keys, signatures or nullifiers.

## Ordered release gates

1. Review and merge the additive API/mobile changes with all required CI.
2. Through a separately authorized API rollout, verify signed and legacy reads
   and writes against synthetic canaries, with the cutoff disabled. An old API
   may ignore the new headers, so verify the response integrity header before
   releasing the app. Do not infer API readiness from the app build alone.
3. Build/sign a new versioned Android release through the normal APK/AAB
   workflow; check prefill, history badges, evaluation submission, restart,
   wrong device clock and supported distribution channels. Keep existing
   published download/version metadata until the new artifacts are available.
4. Collect adoption evidence for BOTH signed reads and score-bound v2 writes.
   The server logs scope-only signed/legacy reads and accepted write payload
   versions. No legacy calls in a quiet interval is not sufficient proof that
   older active users have upgraded. Reconcile with the release/tester evidence.
5. Only after adoption, separately authorize the reversible production setting
   `EVALUATION_REQUIRE_V2=true`. It requires BOTH score-bound writes and signed
   personal reads. Verify old clients receive 426 and current clients retain
   prefill/history and submission. Do not switch it during this code task.
6. Remove the unused legacy mobile signer only after a stable cutoff and its
   follow-up review. Keep GH #253 open until all gates have actual evidence.

Rollback: keep the previous API image and recorded prior flag value. If a
later authorized cutoff breaks supported clients, restore the prior flag under
the approved rollback procedure. Reverting to unsigned compatibility reopens
the documented exposure and must be recorded as such. No database rollback is
needed for this patch.

## Verification and separate finding

HTTP tests cover both routes, Unicode payloads, signature/owner/target/time
tampering, stale/future requests, inactive keys, partial/malformed headers,
no-store responses, exact prefill/history shapes, legacy compatibility and
reversible 426 cutoff. Mobile tests cover payload construction, signatures,
header transport, prefill/history JSON and no unsigned/mirror retries.

Kimi's analysis also identified a similar nullifier-only vote-status read.
It is outside this evaluation patch and requires a separate scoped assessment;
do not modify voting/authentication flows as a side effect of GH #253.
