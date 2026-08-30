# DMARC Observation Gate

This procedure defines the evidence required before proposing a stricter DMARC
policy for `ekklesia.gr`. It does not authorize a DNS change.

## Current State

- DMARC remains in monitoring mode (`p=none`).
- The available aggregate report passes DMARC through aligned Brevo DKIM.
- SPF authentication also passes for the observed Brevo return path, but that
  path is not aligned with `ekklesia.gr`; DKIM is therefore the current DMARC
  authentication anchor.
- API, forum and newsletter mail use Brevo. A local Postfix path is dormant in
  the reviewed evidence window.
- The owner confirmed on 2026-08-30 that the domain is send-only: no domain
  inboxes or forum reply-by-email are intended. Newsletter delivery is outbound
  through Brevo and does not require an inbox on the sending domain.
- The last read-only DNS inventory found no MX record. This is not an explicit
  rejection policy: SMTP senders can fall back to A/AAAA addresses. Do not add
  Null MX as a shortcut: the domain is used in outgoing From addresses, and
  [RFC 7505 section 4.2](https://www.rfc-editor.org/rfc/rfc7505.txt) warns that
  such messages can be rejected. No DNS or SMTP configuration changed here.

## Newsletter and Reply Routing

- Keep the existing `newsletter@ekklesia.gr` sender and Brevo delivery paths.
  Replies use the operator contact already published in the legal/contact
  pages, outside this domain. No `@ekklesia.gr` mailbox is created.
- Brevo transactional mail uses a `replyTo` object; campaign creation uses a
  `replyTo` email string. Apply this to new double-opt-in messages, service
  messages, monthly campaigns and admin-created drafts. Existing provider
  drafts and previously sent messages are not retroactively changed.
- Confirmation is by the HTTPS link sent to the subscriber, not by an email
  reply. Existing consent, scheduling and unsubscribe mechanisms stay intact.
- The contact form keeps an explicit `CONTACT_RECIPIENT` override; its default
  is the external operator address rather than a non-receiving domain address.
  Verify a configured override before rollout; code defaults do not prove the
  production setting. Its Reply-To remains the submitting user's address.
- Bounces/provider return paths and DMARC aggregate reports are distinct from
  human replies. Keep Brevo bounce handling and the external `rua` mailbox;
  send-only intent does not authorize disabling either.
- Before calling subscriber delivery end-to-end complete, verify the handoff
  from confirmed Redis/Listmonk subscriptions into the Brevo campaign list.
  The repository confirmation handler does not call the existing Brevo
  `add_contact` helper. Do not assume an external sync exists or bulk-import
  subscribers, alter consent, or resubscribe suppressed contacts to close this
  gap without a separately reviewed reconciliation plan.
  This follow-up is tracked in
  [GH#261](https://github.com/NeaBouli/pnyx/issues/261), separately from the
  implemented monthly scheduler and future weekly newsletter scope.

## Reply-Routing Release Gate

The code change is API-only preparation, not proof of deployed behavior.
Before a separately authorized rollout:

1. Verify the exact merged commit and green API/security checks. Record the
   current API image digest and a rollback tag; do not alter other services.
2. Read the configured contact-recipient override without exposing secrets or
   personal data in public logs. A stale override needs a separate reviewed
   configuration decision; do not silently override it in code.
3. Keep the sender, Brevo lists, DOI tokens, consent, unsubscribe handling,
   monthly schedule, bounce processing and DMARC `rua` unchanged. Do not edit
   existing provider drafts, import contacts or send a campaign as a smoke test.
4. Verify health and the mocked provider payload contracts. Real delivery
   requires an approved controlled recipient/test and subsequent header/report
   verification; until then, label live mail verification pending.
5. On regression restore the previous API image. No schema/data migration is
   part of this patch. Previously sent messages cannot be recalled by rollback.

References: [transactional API](https://developers.brevo.com/reference/send-transac-email),
[campaign API](https://developers.brevo.com/reference/create-email-campaign).

## Evidence Gate

Do not propose `quarantine` or `reject` until all of the following are true:

1. A complete observation window from 2026-08-01 through 2026-08-31 has been
   catalogued. Review may start on 2026-09-01, but the decision must wait until
   delayed reports covering 2026-08-31 have arrived.
2. Every active sender path has at least one successful alignment record in an
   aggregate report and no unexplained authentication failures across the full
   window. If a path has no report evidence, send controlled messages to two
   independent major mailbox providers and wait for their aggregate reports;
   configuration inspection alone is insufficient.
3. DKIM alignment is consistently passing for API, forum and newsletter mail.
4. Unexpected source paths, authentication failures and forwarding effects have
   been investigated.
5. Owner intent is confirmed as send-only. Verify actual contact/reply routing,
   forum inbound settings and technical bounce handling against that intent.
   No `postmaster`/`abuse` inbox is introduced by this decision; operational
   reporting uses the already published external contact. Any DNS change is a
   separate deliverability-reviewed task, not an automatic consequence.
6. The aggregate-report mailbox is actively monitored and the rollback owner is
   identified.

Absence of a report is not evidence that a sender path is aligned.

## Catalog Rules

Raw XML, source addresses and full provider records stay in the private local
operations catalog. Public status may include only aggregate counts, policy
state, alignment results, review dates and blockers. Never commit report
attachments, credentials or private operational identifiers.

For each report, record at least:

- reporting organization, report ID and UTC interval;
- published policy and percentage;
- message count and disposition;
- header-from domain;
- DKIM and SPF authentication/alignment outcomes;
- classified sender path and investigation status.

## Staged Proposal

After the evidence gate passes, prepare a separately reviewed DNS proposal with
a low-percentage `quarantine` stage, monitoring interval, success criteria and
an exact rollback record. Increasing the percentage or moving to `reject`
requires fresh evidence and separate approval. Do not combine the proposal with
application, server, secret or deployment changes.
