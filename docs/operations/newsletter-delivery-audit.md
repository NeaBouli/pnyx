# Newsletter Delivery Audit and Repair Gate

Date: 2026-08-30. Tracking: [GH#261](https://github.com/NeaBouli/pnyx/issues/261).
Scope: read-only evidence, existing-consent tests and repair design. No live
imports, campaigns, configuration changes or subscriber reactivation.

## Decision

**NO-GO for automatic contact reconciliation or an end-to-end delivery claim.**
The confirmation-to-campaign-list gap is confirmed, not merely suspected.
The existing reply-routing rollout is complete and is a separate concern.
The scheduler was not paused, changed or manually invoked by this audit.

## 2026-08-31 Consent Guard (Code Only)

Fresh read-only inventory at 06:57 UTC: **5** local confirmations, **0** pending,
**2** Brevo list members, **2** matches, **3** provider-404 contacts, **0** list-only
contacts. All five existing records lack `confirmed_at`; three request weekly,
two monthly, four Greek and one English. Listmonk remains unreachable from the
API. This supersedes the counts below, not their historical timestamp.

The owner received and confirmed the separately authorized DOI and received the
single operator-only test newsletter on August 30. Both one-message budgets are
consumed. That proves this controlled delivery, not general audience handoff,
complete authentication headers or unsubscribe behavior. An all-topics-off test
record is not permission for recurring marketing, even if already in a list.

The bounded repair adds, without a production rollout:

- Server-generated request/confirmation times for future DOI confirmations in
  the existing Redis record. Existing confirmations are not backfilled; old
  pending links can still confirm but retain legacy evidence classification.
- Atomic compare + `HSETNX` + token consumption: concurrent clicks have one
  winner, a second token cannot replace earlier preferences, and a failed
  confirmation write retains the pending proof. Only the winning new record
  reaches the existing optional Listmonk call. No new Brevo enrollment call.
- Admin-authenticated `GET /api/v1/admin/newsletter/readiness`: a bounded,
  read-only Redis snapshot (maximum 100 confirmed records), then provider GETs
  (at most five concurrent, 25-second total provider-read budget). No raw
  addresses, tokens or provider responses are returned; httpx contact-URL INFO
  logs are filtered. Over-limit snapshots and timeouts never produce an apply
  manifest. Redis must support `EVAL_RO` (Redis 7+, tested on Redis 8.10).
- Deterministic aggregate KEEP/HOLD/EXCLUDE reasons. KEEP means leave unchanged,
  not validated consent. EXCLUDE means no eligibility for future handoff, not
  removal of current membership. Pending keys and provider-only contacts are
  outside this endpoint's explicitly local-confirmations-only scope.

**Every readiness result has `delivery_ready: false` and `proposed_writes: 0`.**
This is intentionally not a synchronizer, rollout or complete repair of GH#261.
The `complete` flag describes local snapshot coverage, not provider success or
proof that the full newsletter system is ready. Reason counts can overlap.

Suppression wins; missing `emailBlacklisted`/`listUnsubscribed` data is unknown,
and a provider 404 is not consent to recreate a contact. A technically matching
monthly/Greek/citizen/all-topic profile still stays HOLD: manual campaigns share
the monthly list but do not enforce frequency, topic or language preferences.
Kimi's prospective-create proposal was rejected for this reason. Its GETDEL-only
proposal was also rejected because a later failed write could lose the token.

### Remaining Release and Consent Gates

1. Approve and enforce audience/content preference rules for both existing
   campaign senders before implementing any provider writer. Weekly/English
   requests must not silently become Greek monthly subscriptions.
2. Corroborate legacy consent and provider suppression/history. Do not tell
   existing users to re-submit the form as a repair: the current form returns
   "Already subscribed" and intentionally preserves the existing record.
3. Separately authorize any exact contact/list mutation and controlled canary.
   Existing operator test authorization does not permit another email.
4. Separately approve an API-only rollout of these consent guards, after CI and
   review. This task does not deploy, alter configuration, run a scheduler or
   write to production Redis/provider state. Code rollback restores the earlier
   image; additive evidence fields are retained, not deleted or used to restore
   withdrawn subscriptions. The old code ignores those additional JSON fields.

## Historical Live Evidence (2026-08-30, 12:37 UTC)

| Check | Result | Interpretation |
|---|---|---|
| Redis confirmed entries | 4 | Stored local confirmations, not proof of current marketing consent |
| Redis pending entries | 0 | No pending addresses copied or activated |
| Brevo campaign list members | 2 | Complete paginated GET inventory |
| Redis/Brevo exact matches | 1 | Case-insensitive comparison also gives 1, so not a casing-only discrepancy |
| Confirmed entries absent from Brevo | 3 | Individual GETs return 404; no account-wide contact found |
| Brevo-list member without Redis confirmation | 1 | Origin/consent unknown here, not proof of an unauthorized contact |
| Listed members marked `emailBlacklisted` | 0 | Not proof of absence of all provider/list/transactional suppressions |
| Stored language preferences | 3 Greek, 1 English | Campaign content is currently Greek |
| Stored frequencies | 3 weekly, 1 monthly | Only the monthly scheduler is implemented |
| Confirmed entries with explicit confirmation timestamp | 0 | Existing records lack `confirmed_at`; historical evidence needs review |
| Listmonk request from API | `ConnectError` | Configured endpoint unavailable; no config change made |
| Listmonk database, separate read-only count | 2 subscribers, 1 list, 2 memberships | Database is not empty; reachability and synchronization are different questions |
| Brevo campaigns | 1, status `sent` | Historical status, not this audit's delivery/header evidence |
| Brevo webhook inventory | HTTP 400 | Unknown, not a successful zero-webhook inventory |
| Local event counters | 0 for selected delivery/unsubscribe/bounce events | Does not establish that no unsubscribe or bounce occurred |
| Admin list vs monthly list | Both 2 | No live list-ID drift in this snapshot |

Runtime hashes of the three newsletter modules and `mail_policy.py` match the
PR #262 overlay; `main.py` matches the retained production baseline. Brevo and
Listmonk credentials were used only inside the existing runtime, never printed
or exported. Raw addresses, provider responses and subscriber content were not
written to files or tickets. Redis reads and provider GETs do not change consent.

No sync references were found in tracked application/scheduler code, host cron,
systemd unit files or the application scripts directory reviewed. This bounded
inventory cannot disprove every out-of-band provider automation, but the actual
membership mismatch demonstrates that the current handoff is not complete.

## Data Flow and Findings

1. `apps/api/routers/newsletter.py:subscribe` stores a 24-hour pending token and
   sends a Brevo transactional double-opt-in link. It is not list enrollment.
2. `confirm_subscription` copies the original preferences into Redis and deletes
   the pending token. Optional Listmonk registration omits list membership and
   swallows transport failures. No tracked caller invokes Brevo `add_contact`.
3. `apps/api/services/newsletter_service.py:send_monthly_report` sends campaigns
   to hardcoded list 2. The admin router separately reads `BREVO_LIST_ID`.
4. `brevo_webhook` counts events only; it does not maintain per-contact consent,
   preference changes or suppression state in Redis/Listmonk. It must not become
   a consent-authority endpoint without authenticated, replay-safe processing.
5. Frequency, language and topic preferences are stored but not used to select
   campaign recipients. Adding every confirmed address to list 2 would change
   effective delivery without proving those preferences are honored.

Provider-side suppression can still protect recipients. The audit does **not**
claim Brevo ignores unsubscribes, nor that the unmatched list member lacks consent.
Application templates lack an explicit unsubscribe control, but actual provider
insertion and the received-message unsubscribe flow were not verified. A DOI
token deletion protects a sequential replay; the current read/write sequence
does not establish atomic consumption against concurrent confirmations.

## No-Write Reconciliation Manifest

| Population | Proposed current action | Reason |
|---|---|---|
| 3 locally confirmed, absent from provider | HOLD | Need corroborated consent, preferences and suppression/history checks |
| 1 local/list match | LEAVE UNCHANGED | Existing membership is not authorization to modify or reactivate |
| 1 list-only member | LEAVE UNCHANGED; REVIEW | Preserve list ownership; do not delete or infer local consent |
| Any pending/expired/invalid/ambiguous record | EXCLUDE | Never promote to confirmed through reconciliation |
| Any blocked/unsubscribed/complaining contact | EXCLUDE | Suppression wins; never reset blacklist or manufacture re-consent |
| Any incomplete/failed provider lookup | HOLD | Unknown is not permission to create/update |

**Current proposed provider writes: 0.** No apply mode, mass import, contact
export job, identity join or new permanent subscriber store was introduced.
Missing records and absent local unsubscribe counters must never be interpreted
as permission to subscribe. Identical evidence yields the same hold manifest;
repeating the audit cannot send mail or change membership.

## Original Bounded Repair Plan (Writer Not Executed)

1. Establish consent provenance for the three missing contacts and origin for
   the list-only member, using private operator evidence. No public address list.
   Missing timestamps must not be fabricated from deployment or Redis TTL data.
2. Specify suppression precedence and preference mapping before coding a writer:
   pending/invalid excluded; authenticated unsubscribe/complaint/bounce state
   wins; missing provider state blocks. Decide how language, topic and frequency
   choices map to the existing monthly audience without changing its ownership.
3. Add a separately reviewed, idempotent handoff after confirmed consent, with
   bounded retries and durable success/failure evidence. A repeat confirmation
   must not reactivate a provider-blocked contact or send duplicate welcome mail.
   Failure must remain observable without discarding original consent.
4. Dry-run against fresh private evidence. Require an exact approved contact
   manifest and proposed list-only mutations; the current manifest allows none.
   Do not call `add_contact(updateEnabled=True)` blindly or introduce bulk import.
5. Only after explicit approval: one named, consenting controlled test recipient,
   exact list/scope, message limit and observation window. Verify DOI, list
   membership, received Reply-To/authentication/unsubscribe headers and an actual
   unsubscribe followed by a retry that does not reactivate the contact.
6. Before a wider rollout, test pending, invalid, duplicate, provider-404/error,
   suppression, preference, concurrency and timeout cases with mocked providers.
   Retain a rollback image and record exact list additions. Rollback must never
   restore subscriptions withdrawn during the test; sent email is irreversible.

No server-address correction, replacement of Listmonk/Brevo, new weekly schedule,
DNS/secret change, provider webhook registration or campaign send is bundled here.
The scheduled monthly cycle is approaching; its existing audience remains the
two provider-list members, not all four local confirmations. Any request to pause
or alter that cycle is a separate explicit operational decision.

## Verification and Side Findings

- Kimi independently identified the missing call/list assignment and preference
  and suppression gaps. Its local test attempt lacked matching dependencies;
  Sol reran the tests in the project test environment.
- 11 new mocked consent tests plus the existing eight mail payload tests pass:
  original preference preservation, expired token rejection, sequential replay,
  storage failure retaining the pending token, optional Listmonk failure,
  existing-subscription no-send, invalid preferences and admin send confirmation.
- No test claims current end-to-end delivery or makes a real provider call.
- Side findings retained for follow-up: subscription-specific abuse protection,
  plaintext addresses in existing log calls, webhook authentication before any
  future per-contact mutation, and monthly send-success reporting that currently
  does not check the result of `sendNow`. No neighboring runtime fixes here.

Official API references: [Brevo list contacts](https://developers.brevo.com/reference/get-contacts-from-list),
[contact details](https://developers.brevo.com/reference/get-contact-info),
[webhook inventory](https://developers.brevo.com/reference/get-webhooks),
[Listmonk subscribers](https://listmonk.app/docs/apis/subscribers/).
