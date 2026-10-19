# DRAFT — mobile key custody and web QR login

T-9154 / #635 · 2026-10-19. For product/security review; only the notice slice
below is implemented. Basis: 2026-10-17 decision in
`origin/agent/claude/T-9139:docs/security/WEB_KEY_LOSS_RECOVERY.md` (#617), read
locally with `git show`: mobile is the primary identity-key home; web uses QR;
show confirmed browser key absence; no key export. Recovery/holder proof,
users without the app, device authority and retention remain open.

## Current flows and gaps (checkout file:line)

| Flow | Evidence and gap |
| --- | --- |
| QR issuance/auth | `apps/api/routers/polis_qr.py:134` issues a random session/challenge, purpose and optional bill binding; pending TTL 300s. `:224` checks ACTIVE identity/current key and verifies the app signature over **only the challenge**; `:53` atomically authenticates and sets TTL to 60s. No origin, display code, browser-only redemption secret or signed scope envelope. |
| App custody/scan | `apps/mobile/src/lib/crypto-native.ts:222` stores bytes in SecureStore; `apps/mobile/src/screens/PolisLoginScreen.tsx:49` automatically signs on deep-link entry (`:80`). Add explicit approval of authoritative origin, code, scopes and target. SecureStore custody does not imply hardware-only signing. |
| Existing web QR | `apps/web/src/components/QRCodeVoteStub.tsx:50` creates purpose-specific sessions and `:90` polls. `docs/assets/js/qr-login.js:17` powers `/embed/qr-login.html`; `:79` returns identity/session data to a same-origin iframe parent. Static files are copied by `apps/web/Dockerfile.prod:17`. These are action grants, not a general web login. |
| Vote/status | Normal Next web voting needs a local signer (`apps/web/src/app/[locale]/bills/[id]/page.tsx:96`, `apps/web/src/lib/api.ts:27`, `:52`). Existing `/polis/qr-vote` accepts a bill-bound QR session (`apps/api/routers/polis_qr.py:303`), checks the current key (`:339`) and atomically consumes the grant (`:393`). Consensus has its own QR grant (`:433`). These do not replace the normal signed API path. |
| Correction | Local web signing selects `/correct` (`apps/web/src/lib/api.ts:49`); server signature/window/one-change checks remain mandatory (`apps/api/routers/voting.py:947`, `:979`, `:994`). QR currently rejects changed votes and directs users to the app (`apps/api/routers/polis_qr.py:386`). |
| Evaluation | API writes require the identity signature and v2 binds scores/time (`apps/api/routers/evaluation.py:285`); personal reads use signed proof, with a legacy unsigned migration window (`:79`). No QR evaluation grant or Next web submission UI exists; the current submitting client signs in the app (`apps/mobile/src/screens/EvaluatePoliticianScreen.tsx:137`). A future web client cannot use today's QR session in place of these signatures. |
| SSO | Local-key path signs `discourse_sso` (`apps/web/src/app/[locale]/sso-verify/page.tsx:41`); no-key path already creates `forum_login` QR (`:68`) and completes it (`:139`). Server checks nonce, purpose and current key and consumes nonce/session (`apps/api/routers/sso.py:236`). The QR authorisation is not yet signed over the SSO nonce/origin. Legacy static SSO still gates on localStorage (`docs/assets/js/sso-verify.js:36`). |

## Proposed delegation (future protocol; all values/scopes are draft)

1. Add a versioned `web_session` QR purpose alongside existing purposes. A
   same-origin web backend creates a 256-bit browser redemption secret in a
   Secure, HttpOnly, SameSite=Strict cookie; only its hash/binding goes in the
   server session. QR/poll IDs alone must not redeem or reveal identity data.
   Pending challenge expires after **5 minutes**; redemption expires **60s after
   approval**, capped at that original deadline.
2. The app fetches session details from its fixed API, rather than trusting
   QR-supplied labels/URLs. It displays the exact allowlisted HTTPS web origin,
   a matching six-digit display code, requested scopes/targets and expiry;
   approval requires an explicit tap. The server derives origin from the
   validated creator request; it never accepts an arbitrary QR origin/return URL.
3. The current identity key signs canonical, versioned JSON with a domain
   separator `ekklesia:web-session:v1`, session ID, random nonce, web origin,
   API audience, browser-binding hash, display code, scopes/resource IDs and
   expiry. Specify identical mobile/server encodings and golden vectors before
   implementation. Server checks signature, current ACTIVE key and all stored
   fields, then atomically permits **one** browser-bound redemption.
4. Redemption issues an opaque 256-bit scoped session token, bound server-side
   to that signed grant, identity/current key and revocation epoch. Store only
   its hash in Redis; put the token in a Secure, HttpOnly web-origin cookie,
   never URL, localStorage or QR. Absolute lifetime **10 minutes**, no refresh
   or scope widening; re-scan for renewal. The same-origin backend forwards it to API
   authorisation, validates Origin and CSRF on mutations; public reads stay public.

| Web authority | Proposed scope and boundary |
| --- | --- |
| Initial vote + own status; consensus | Explicit `vote:create`, `vote:read`, `consensus:write`, each bound to a bill. Reuse the same visibility, geography, current-key, uniqueness, correction and ZK cross-tier checks as signed actions. Atomic idempotency IDs prevent double submission; a create grant cannot correct a vote. |
| Correction; evaluation/personal evaluation reads | Later, separately enabled scopes. Require a fresh app-approved **single-use action grant** binding exact bill/choice or representative/scores (canonical digest), timestamp and expiry. Preserve correction count/deadline and evaluation v2/read signature semantics; the general session alone cannot perform these actions. Until implemented, use the app. |
| Forum SSO | Separate single-use `sso:forum` grant binds the Discourse nonce and allowlisted return origin; reuse nonce consumption/current-key checks. A general session does not silently log into the forum. |
| Identity management | No registration, key export, rotation/recovery, device enrolment or region changes using a web session. POLIS ticket authority stays on its existing path until separately reviewed. |

Recheck ACTIVE/current key and revocation epoch on **every** protected action.
Browser logout deletes its server token; the app signs revocation of one session
or all sessions. Identity revoke/rotation invalidates all prior grants immediately.
Retain consumed-nonce/idempotency tombstones through grant expiry to reject
replays and concurrent redemption; never extend TTL on polling. Forum cookies
outlive the QR grant today: Discourse logout/revocation needs a separate integration.

Origin/audience binding, the display code and explicit scope confirmation reduce
phishing; they do not eliminate a relayed QR for a real site. Warn in the app to
approve only a browser the user is operating, and require the extra action grant
for corrections/evaluations. Rate-limit create/auth/redeem/poll and reject stale,
wrong-origin, wrong-purpose and wrong-browser requests before any mutation.

## Data, migration and rollout

- Identity private keys remain in the app; web receives limited authority. The
  proposed backend cookie/session adds temporary identity↔browser linkage:
  store only token hash, identity reference/key version, origin, scopes and
  expiry, plus replay state. Expire grant/session data by their TTLs; no phones,
  anchors, keys, tokens, display codes or vote/score payloads in logs/analytics.
  Existing QR polling exposes public key/nullifier and auth logs include session
  fragments (`apps/api/routers/polis_qr.py:206`, `:281`); the new path must avoid
  both. Cookie/privacy wording and operational retention require owner review.
- Preserve browser-only users' existing signer and independent Compass AES/data.
  Offer a future explicit pairing: app generates a fresh key, proves possession;
  existing web key authorises replacement bound to that app key, then the server
  atomically rotates and revokes old sessions. Confirm app operation before
  deleting the browser identity key; preserve Compass decryption separately.
  Never export/copy the web key. Interrupted pairing needs a recoverable journal.
  This requires a reviewed cross-device flow; current browser rotation alone
  does not provision the app. Installing the app after web-key loss restores
  neither identity nor Compass. No automatic re-registration/v1 recovery fallback;
  no-app and total-loss support await the recovery decisions above.
- **Slice in this draft:** runtime `WEB_QR_LOGIN_NOTICE_ENABLED`, enabled only by
  literal `true`, default `false` (template + production Compose passthrough).
  `BrowserKeyNotice` appears below navigation in Next locale pages, with EL/EN
  copy linking to `/embed/qr-login.html`. Strict local reads under the keystore
  lock check active and pending keys plus legacy storage; stale custody hints
  cannot prove presence, and read errors/corruption cannot prove absence.
  Recheck on navigation, foreground and storage events. No keys are created,
  replaced or exported by the check; it makes no network requests. Existing
  migration continues independently. Static docs pages are outside this slice.
  The linked existing embed defaults to POLIS `ticket` auth: it does **not**
  establish the proposed general web session yet.
- Later (proposed, not added): `WEB_QR_DELEGATION_ENABLED` API gate + web entry
  gate, both off; separate correction/evaluation scope gates off. Ship app
  consent/version support first, then a small opt-in web cohort. Never downgrade
  new grants to unsigned/legacy auth. Rollback disables issuance, revokes new
  sessions and leaves existing local signing/action-specific QR available.

## Targeted validation

- Slice: notice off does no reads; pending check has no false absence; EL/EN
  link/copy; local/legacy/pending keys suppress notice; missing storage confirms
  absence even with stale hints; blocked/corrupt storage suppresses it; lock
  ordering, foreground/navigation refresh, stale results and cleanup. Run only
  `src/components/BrowserKeyNotice.test.tsx` and `src/lib/keystore.test.ts` from
  `apps/web` with Vitest `--maxWorkers=1 --no-file-parallelism` (offline cache).
- Future protocol: canonical signature vectors; origin/code/audience/scope and
  browser-binding tampering; approval/expiry boundaries; concurrent auth/redeem,
  replay and idempotent retries; rate limits; revocation/key rotation; no scope
  escalation; vote duplicate/correction deadline/count and ZK locks; evaluation
  score/read binding; SSO nonce/return-origin binding; interrupted pairing and
  Compass preservation; redacted logs and TTL cleanup. API/mobile unit tests
  first; staged cross-device smoke tests only after design approval.
