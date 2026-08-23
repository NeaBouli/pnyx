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
- The domain currently publishes no MX record. Whether the domain is strictly
  send-only must be confirmed before proposing an explicit inbound-mail policy.

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
5. The owner has confirmed whether inbound mail, forum reply-by-email, and the
   conventional `postmaster` and `abuse` addresses are expected.
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
