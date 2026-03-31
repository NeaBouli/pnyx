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

## Scope
- Ed25519 Crypto (packages/crypto/, apps/web/src/lib/crypto.ts)
- Identity Flow (apps/api/routers/identity.py)
- Nullifier Hash Generation
- Vote Signature Verification
- POLIS OAuth Flow (cloudflare-worker/)
