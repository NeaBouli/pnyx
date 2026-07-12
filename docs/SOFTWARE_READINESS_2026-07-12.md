# Ekklesia Software Readiness — 2026-07-12

This public report contains no runtime values, account identifiers, wallet
ownership, customer data or tax identity. Operational finance details remain in
private `NeaBouli/vlabs`.

## Verified Products

| Surface | Verification | Result |
|---|---|---|
| Public web app | ESLint, TypeScript, 29 crypto tests, Next production build | PASS |
| Admin dashboard | ESLint, TypeScript, Next production build | PASS |
| Citizen mobile app | TypeScript, 105 tests, real Expo Android export | PASS |
| Representative app | TypeScript, real Expo Android export | PASS |
| Shared crypto package | TypeScript, 48 tests including real Argon2id execution | PASS |
| API payment boundary | 14 focused donation/privacy/refund/dispute tests | PASS |
| RAG/monitor agents | 48 guardrail/recovery/redaction tests; 4 local-data skips | PASS |
| Public community page | Desktop/mobile browser check, no overflow or payment leak | PASS |

## Corrections Made

- Web vote-message tests now match the canonical API/mobile signature payload.
- Shared Argon2id options match the current `hash-wasm` API and execute in test.
- Mobile Noble dependencies use one compatible major line and export cleanly.
- Dashboard lint works under Next.js 16; Web uses the `proxy` convention.
- All client/package checks are mandatory in pull-request CI.
- Donation records and finance events contain technical references only, never
  payer email, payer hash or billing identity.
- Stripe and PayPal captures, refunds, reversals and disputes are signature/IPN
  verified and represented as PII-free finance events.
- Ekklesia accepts only voluntary donation purposes. HLR provider credits are a
  private operating expense and are not sold through the donation intake.
- Public donation links and wallet/account identifiers remain removed/paused.

## External Release Gates

- Confirm legal recipient, donation/document/tax treatment and refund policy.
- Configure private Stripe/PayPal runtime values and private finance ingestion.
- Execute provider sandbox/test-mode donation, refund and dispute E2E.
- Run signed EAS builds and physical-device HLR/voting canaries.
- Configure production infrastructure and perform controlled deployment.

No live payment, donation, invoice, HLR lookup, provider request or deployment
was performed during this verification.

## Tracked Upstream Risk

`arweave-python-client==1.0.19` transitively installs an `ecdsa` advisory with no
fixed upstream release. Ekklesia uses the client's RSA Arweave path only. CI
keeps one explicit advisory exception until the dependency can be replaced.
