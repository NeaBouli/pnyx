# Newsletter Delivery Audit and Repair Gate

Date: 2026-08-30. Tracking: [GH#261](https://github.com/NeaBouli/pnyx/issues/261).
Scope: read-only evidence, existing-consent tests and repair design. No live
imports, campaigns, configuration changes or subscriber reactivation.

## Decision

**NO-GO for automatic contact reconciliation or an end-to-end delivery claim.**
The confirmation-to-campaign-list gap is confirmed, not merely suspected.
The existing reply-routing rollout is complete and is a separate concern.
The scheduler was not paused, changed or manually invoked by this audit.

## Live Evidence (12:37 UTC)

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

## Bounded Repair Plan (Not Executed)

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
