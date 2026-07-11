# Pnyx / ekklesia.gr Bridge

## 2026-07-11 — Payment/Etimologio Ownership and Safety (Codex)

- Codex owns Stripe, PayPal, crypto-payment accounting boundaries and the
  private VLABS Etimologio handoff. Non-payment Pnyx product work remains with
  the project Core-Dev.
- Public contribution links are paused until Gio/Accountant confirms the legal
  recipient, legal form, tax treatment, document policy and whether each flow
  is a donation, support income or sale.
- Important classification: `15 EUR = 2500 HLR Credits` has consideration and
  is a product purchase, not a donation.
- Webhooks now require the explicit `PAYMENTS_INTAKE_GATE`, verified provider
  signature/IPN, EUR, bounded positive amount and explicit payment purpose.
- Stripe additionally requires paid `payment` Checkout mode. PayPal additionally
  binds receiver email and/or merchant ID and uses atomic transaction claiming.
- Failed persistence after accounting mutation is held for manual review instead
  of deleting idempotency state and risking duplicate allocation.
- Public status continues to redact donor identity and processor IDs.
- Focused verification: 9 payment safety tests PASS; Python compile PASS.
- No live payment, refund, invoice, AADE/provider request, runtime secret,
  deployment or public payment reactivation.

### External gates

1. Gio/Accountant: identify the legal recipient and approve donation versus
   taxable support/service/product treatment per flow.
2. Configure separate Stripe/PayPal products with explicit purpose metadata;
   do not reuse PayPalMe amount alone to infer HLR purchases.
3. Decide invoice/receipt, VAT/myDATA and refund treatment, then connect the
   private VLABS finance ingest.
4. Run Stripe and PayPal sandbox/test E2E before restoring public links.
