# ekklesia.gr / pnyx — Integration & Surfaces Audit

**Auditor:** Collateral Web3 Open Audits
**Client:** NeaBouli / ekklesia.gr (pnyx)
**Date:** 2026-09-15
**Baselines:** repo `NeaBouli/pnyx` @ `c0efac7b0ee7669d91402c50eb5dcf4db7819fe3` · live probes 2026-09-15, anonymous GET/HEAD only (`evidence/live/`) · CI records via GitHub API
**Companion documents:** full-scope security audit (EKA-01…20) · crypto deep audit (EKA-21…25) · content coherence + AI readiness (register continues EKA-32+)
**Report version:** 1.0

This audit answers: **is the system actually wired together and does the deployed surface
match the repo?** Every check is an anonymous read-only probe or a repo/runtime comparison;
no authenticated or state-changing calls were made.

**Verdict: WORKS — with hygiene findings.** All twelve core wirings verified live. The
deployment is byte-fresh with the pinned commit, the APK supply chain is hash-pinned end
to end, and security headers are enforced globally at the edge. Findings cluster around
subdomain hygiene and edge-policy tightening.

**Findings: 0 Critical · 0 High · 0 Medium · 4 Low · 2 Informational (EKA-26 … EKA-31)**

| # | Severity | Title | Status |
|---|----------|-------|--------|
| EKA-26 | Low | Unrelated third-party app served on `vr.ekklesia.gr` | Open |
| EKA-27 | Low | Dead/dangling subdomains (`checkout`, `flw`) + exposed `test` | Open |
| EKA-28 | Low | Listmonk admin and Plausible login panels publicly reachable | Open |
| EKA-29 | Informational | Patch backlog: 5 open Dependabot alerts, ~10 open dependency PRs incl. majors | Open |
| EKA-30 | Low | CSP `script-src 'unsafe-inline'` on all static/wiki pages weakens the XSS containment that EKA-14 needs | Open |
| EKA-31 | Informational | Verified-wiring register (12/12 pass) | Recorded |

---

## 1. Verified wirings (EKA-31 — all live-verified 2026-09-15)

| # | Wiring | Evidence |
|---|--------|----------|
| W1 | Web ↔ API: bills feed serves real scraped parliament data | `GET /api/v1/bills?limit=5` → 200, Greek titles, ids `GR-*` (`evidence/live/bills-feed.json`) |
| W2 | App-version contract ↔ mobile rollout | `GET /api/v1/app/version` → `1.0.32 / 61 / min 1` — matches BRIDGE rollout record |
| W3 | APK supply chain end-to-end | streamed SHA-256 of `/download/ekklesia-latest.apk` = `67e051c5…ec56` = `docs/download/ekklesia-latest.apk.sha256` = GitHub Release v1.0.32 digest |
| W4 | Wiki deployment freshness | 4/4 sampled pages byte-identical live ↔ repo @ c0efac7b (index, security, privacy, architecture) |
| W5 | Dashboard auth gate | `GET dashboard.ekklesia.gr/` → 307 → `/login?callbackUrl=%2F` (NextAuth edge gate active) |
| W6 | Forum (Discourse) up with strict CSP | pnyx.ekklesia.gr 200; `script-src nonce-… 'strict-dynamic'`, `object-src 'none'`, `frame-ancestors 'self'` |
| W7 | HLR credits transparency endpoint | `GET /api/v1/identity/hlr/credits` → 200 (see EKA-06 for the abuse trade-off) |
| W8 | Module registry consistent with code | `GET /health` lists 25 modules; MOD-23 "disabled" (matches defensive import), MOD-09 "deferred" (matches 9-gate stub) |
| W9 | API docs hidden in production | `/docs` and `/openapi.json` → 404 (matches `main.py:723-731`) |
| W10 | TLS + HSTS | Let's Encrypt certs valid (apex 2026-08-18→11-16); `strict-transport-security: max-age=31536000; includeSubDomains; preload` on API + web |
| W11 | Global edge security headers | Traefik middlewares deliver CSP + `x-content-type-options: nosniff` + `x-frame-options: DENY` on every probed ekklesia.gr route |
| W12 | CI/CD gates green at pinned commit | `ci.yml` + `security-audit.yml` success @ c0efac7b (2026-09-13/14); security-audit runs Gitleaks full-history, npm audit (high), pip-audit weekly |

Not anonymously verifiable (declared, not failed): Stripe webhook delivery, Ollama/Claude
agent answers, Discourse SSO handshake, push send path, live HLR queries, production ZK
flag state, database/Redis internals, backup script operation.

## 2. Subdomain inventory (CT logs + probes)

| Host | Status | Assessment |
|---|---|---|
| ekklesia.gr / www | 200 / 301 | apex app, headers per W11 |
| api | 200 | uvicorn direct header; edge headers present |
| dashboard | 307→login | NextAuth gate (W5) |
| pnyx | 200 | Discourse (W6) |
| analytics | 200 (Cowboy) | Plausible app — see EKA-28 |
| newsletter | 200 | Listmonk — see EKA-28 |
| vr | 200 (nginx) | **unrelated app "MiroFisch" — EKA-26** |
| test | 401 | protected, but exposed — EKA-27 |
| checkout / flw | no response (000) | DNS/certs live, service down — EKA-27 |
| webmail | (CT only) | not probed further (mail infra) |

## 3. Findings

### EKA-26 — Unrelated third-party app on `vr.ekklesia.gr`
- **Severity:** Low · **Status:** Open
The subdomain serves an unrelated single-page product ("MiroFisch") on the civic
platform's domain. Risks: brand confusion for citizens, shared `*.ekklesia.gr` cookie
scope, and a phishing lever (any content on an official-looking subdomain inherits
trust). Likely an operator-side sibling project behind the same Traefik. **Fix:** move it
to its own domain, or at minimum isolate cookies and label the separation.

### EKA-27 — Dead/dangling subdomains
- **Severity:** Low · **Status:** Open
`checkout.ekklesia.gr` and `flw.ekklesia.gr` resolve and hold certificates but serve
nothing (connection failure); `test.ekklesia.gr` answers 401. Dangling hosts enlarge the
attack surface (forgotten vhosts, stale Traefik routes) and confuse CT-log monitoring.
**Fix:** decommission DNS+certs for retired services; keep `test` behind the same
catch-all hygiene or VPN.

### EKA-28 — Admin panels of Listmonk and Plausible publicly reachable
- **Severity:** Low · **Status:** Open
`newsletter.ekklesia.gr/admin` → 307 to the Listmonk login; `analytics.ekklesia.gr`
serves the Plausible app login. Both are authentication-gated (no bypass observed;
read-only limits), but public admin panels are brute-force targets for the two services
that hold subscriber PII and stats. **Fix:** IP allowlist or Traefik basic-auth layer in
front of `/admin`; consider Plausible's self-hosted "disable registration" and share-link
hardening review.

### EKA-29 — Patch backlog (Info)
5 open Dependabot alerts (per SECURITY.md four are intentionally kept for the vendored
image-size backport) plus ~10 open dependency PRs including `next 16.3.4` and a major
`arweave 2.0.1`. CI is green, so this is flow management, not exposure — but the arweave
major and Next patch should land before the next mobile release cut. Confirm alert #78-81
policy still matches `vendor/image-size/PATCHES.md`.

### EKA-30 — CSP allows `'unsafe-inline'` scripts on static/wiki pages
- **Severity:** Low · **Status:** Open
The edge CSP on apex/wiki/tickets is `script-src 'self' 'unsafe-inline'`. Every EKA-14
sink (and any future stored-XSS in static content) is directly executable under this
policy — the CSP currently filters origins but not injection. The project's own Discourse
deployment demonstrates the stronger pattern (`nonce-*` + `'strict-dynamic'`). Static
pages could adopt hashed/nonce scripts or externalize the inline blocks. **Fix:**
incremental — move inline JS to files, then drop `'unsafe-inline'`.

### EKA-31 — Verified-wiring register (Info)
Section 1 is the register; 12/12 pass. Re-probe after each deploy to catch drift (the
byte-identity check W4 and APK hash check W3 are the two cheapest canaries).

---

*— End of integration & surfaces audit. Register continues EKA-32+.*
