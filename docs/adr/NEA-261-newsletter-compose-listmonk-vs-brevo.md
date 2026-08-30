# ADR: NEA-261 — Newsletter Compose (Listmonk vs Brevo)

- **Date:** 2026-05-23
- **Status:** Historical proposal; implementation/evidence update below
- **Linear:** NEA-261

## 2026-08-30 Reconciliation

The following May proposal is retained as history, not the current inventory.
Dashboard compose and admin preview/draft/send now exist and use Brevo;
the monthly scheduler also uses Brevo. This does not prove subscriber delivery.
The August read-only inventory found a consent-to-audience gap and an unreachable
configured Listmonk endpoint. Listmonk's database is not empty (two subscribers,
one list, two memberships). No migration or provider decision was made.

Current evidence, consent/suppression gates and repair proposal:
[GH#261 delivery audit](../operations/newsletter-delivery-audit.md).
GitHub #261 is distinct from this historical Linear NEA-261 identifier.

## Historical State (2026-05-23)

- **Subscriptions:** Brevo API (`apps/api/routers/newsletter.py`) — confirmation emails, double opt-in
- **Monthly Auto-Report:** APScheduler → `send_monthly_report()` via Brevo
- **Listmonk Container:** Running (`listmonk:9000`), reachable internally + externally (`newsletter.ekklesia.gr`)
- **Listmonk Content:** 0 lists, 0 subscribers, 0 campaigns — completely empty
- **Dashboard:** No newsletter compose page exists

## Decision Needed

| Option | Pros | Cons |
|--------|------|------|
| **A) Stay with Brevo** | Already working, subscribers exist, double opt-in active | Brevo is external service, API limits, no self-hosted control |
| **B) Migrate to Listmonk** | Self-hosted, full control, templates, automation | Empty instance, needs full setup, subscriber import, SMTP config |

## Recommendation

Do not build Dashboard compose UI until source-of-truth is decided.

### If Listmonk (Option B):
1. Create lists (e.g., "Εβδομαδιαίο", "Μηνιαίο", "Ανακοινώσεις")
2. Configure templates (Greek + English)
3. Import existing Brevo subscribers (with consent verification)
4. Configure unsubscribe flow (GDPR)
5. Test with single subscriber before production
6. Then build Dashboard compose

### If Brevo (Option A):
1. Use Brevo Campaigns API for compose
2. Dashboard proxy targets Brevo API (not Listmonk)
3. Simpler but external dependency

## Security Constraints

- Listmonk/Brevo credentials: server-only, never in frontend
- Dashboard newsletter routes: admin-only (verify_admin_key or session auth)
- No subscriber email export in UI — aggregate counts only
- Draft/preview first, send requires explicit confirmation dialog
- Unsubscribe link mandatory in every email (GDPR)

## Acceptance Criteria (Before Build)

1. Source-of-truth decision: Brevo or Listmonk
2. At least one configured list with subscribers
3. Test subscriber verified
4. Unsubscribe flow working
5. Draft campaign creation tested
6. Explicit send confirmation in UI

## Next Steps

- Gio decides: Brevo or Listmonk
- If Listmonk: configure instance, create lists, import subscribers
- Only then: Dashboard compose page
