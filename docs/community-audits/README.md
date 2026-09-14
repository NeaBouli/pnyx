# Community Audits — ekklesia.gr / pnyx

Independent audit reports by **Collateral Web3 Open Audits**. Publication of the full
series — including security findings — was explicitly authorized by the repository owner
on 2026-09-15, overriding the private-disclosure preference in `SECURITY.md` for this
series. Findings are tracked as a single register in the umbrella issue
(register prefix `EKA-`).

## 2026-09-15 — Full audit series (EKA-01 … EKA-64)

Baseline: `c0efac7b0ee7669d91402c50eb5dcf4db7819fe3` (main HEAD at audit start).
Live probes: 2026-09-15, anonymous GET/HEAD only. No state-changing requests, no secret
files read, report-only.

| Document | Register | Findings | SHA-256 |
|---|---|---|---|
| [Full-Scope Security Audit](EKA_PNYX_Full_Scope_Audit_2026-09-15.md) | EKA-01 … EKA-20 | 0 C · 1 H · 7 M · 7 L · 5 I | `fcc9003aa0691278b1f34ce7c83b83210d211e22d5ae39a5cae6fe82c71c7559` |
| [Cryptography Deep Audit](EKA_PNYX_Crypto_Deep_Audit_2026-09-15.md) | EKA-21 … EKA-25 | 0 C · 0 H · 1 M · 1 L · 3 I | `28349eca4d3366af4c9649259dc45214fc6355c88de61e91ff827770b5b21eaa` |
| [Integration & Surfaces Audit](EKA_PNYX_Integration_Surfaces_Audit_2026-09-15.md) | EKA-26 … EKA-31 | 0 C · 0 H · 0 M · 4 L · 2 I | `289430992a5b28683486d7e55b8cc0f364e4e46f7b76b6293b57718a47972c78` |
| [Content Coherence Audit](EKA_PNYX_Content_Coherence_Audit_2026-09-15.md) | EKA-32 … EKA-56 | 0 C · 0 H · 10 M · 11 L · 4 I | `818292edbd0d66f99bcf7f9e8903b99ecd779e091e4da0ac17357e4350c6087d` |
| [AI Readiness Audit](EKA_PNYX_AI_Readiness_Audit_2026-09-15.md) | EKA-57 … EKA-64 | 0 C · 0 H · 3 M · 4 L · 1 I | `2d40f6d8e4bbf0c26568b80303eb998393369cf4d86ab4035054bdd94b3d6328` |

**Series totals: 64 findings — 0 Critical · 1 High · 21 Medium · 27 Low · 15 Informational.**

Of the single High finding (EKA-02, representative WebView stored-XSS surface): likelihood
is conditional on malicious content entering via scraper/admin input; impact is bounded by
the representative role's read/toggle-only scope and 24 h token TTL.

Headline results:

- The two CRITICAL findings of the 2026-05-03 internal audit are verifiably **fixed**
  (admin keys out of URLs; dashboard server-side proxy; web admin page is a redirect).
- Core vote integrity holds: Ed25519 gates on every citizen write, DB-unique double-vote
  anchors on every path, fail-closed ZK/Stripe/destructive-admin design.
- Main work areas: representative WebView output encoding (EKA-02), auxiliary-endpoint
  authentication (EKA-03…06), missing global rate-limit middleware (EKA-32),
  client-KDF drift across three implementations (EKA-21), and a substantial
  documentation-drift cluster (EKA-33…52) on the platform's most sensitive public promises.

Reports are immutable once pinned; follow-up audits get new dates and continue the
register (next: `EKA-65`).
