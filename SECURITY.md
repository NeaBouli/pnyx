# Security Policy

## Supported Versions
| Version | Supported |
|---------|-----------|
| Beta    | ✅        |

## Reporting a Vulnerability
Please do NOT report vulnerabilities publicly via GitHub Issues.

Send an email to: kaspartisan@proton.me
Subject: [SECURITY] ekklesia.gr vulnerability

We respond within 48 hours.

## Tracked Vendored Security Backport

Mobile and Representative use the reviewed local `image-size@1.2.2-pnyx.0`
backport for `GHSA-5p2g-fcmc-qvqq` and `GHSA-w3rx-r6r6-pgpr`. Upstream has not
published a patched, Metro-compatible release. The implementation and
retirement rules are documented in `vendor/image-size/PATCHES.md`.

Dependabot alerts `#78` through `#81` remain open by design so future upstream
advisories stay visible. They must not be dismissed, suppressed, or hidden with
an artificial package version. The backport is retired only after a maintained
compatible release contains the equivalent fixes and passes the repository's
normal CI and security checks.

## Scope
- Ed25519 Crypto (packages/crypto/, apps/web/src/lib/crypto.ts)
- Identity Flow (apps/api/routers/identity.py)
- Nullifier Hash Generation
- Vote Signature Verification
- POLIS OAuth Flow (cloudflare-worker/)
