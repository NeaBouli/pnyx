# ADR: NEA-260 — Seamless Forum SSO

- **Date:** 2026-05-23
- **Status:** Proposed / Not yet implemented
- **Linear:** NEA-260

## Problem

Mobile app opens forum links via `Linking.openURL("https://pnyx.ekklesia.gr/t/{id}")`. User lands on Discourse as guest. No automatic SSO login. User must manually trigger login → Discourse redirects to ekklesia SSO → browser signs challenge → redirects back. This is 3+ redirects and poor UX.

## Current Flow (Post NEA-251)

```
1. User taps 💬 in BillsScreen
2. Linking.openURL("https://pnyx.ekklesia.gr/t/{topic_id}")
3. External browser opens Discourse
4. User sees topic as guest
5. User clicks "Login" on Discourse
6. Discourse generates sso+sig payload → redirects to /sso/discourse/initiate
7. ekklesia verifies Discourse HMAC → stores nonce → redirects to /el/sso-verify
8. sso-verify page reads localStorage keys → signs "discourse_sso:{nonce}:{pubkey}"
9. POST /sso/discourse/callback with signature_hex
10. Server verifies Ed25519 → builds Discourse payload → returns redirect_url
11. Browser opens redirect_url → logged in on Discourse
```

**Steps 5-11 are secure (NEA-251) but inconvenient.**

## Constraint: Discourse Initiates SSO

DiscourseConnect protocol requires Discourse to generate the initial `sso` + `sig` HMAC payload. The ekklesia server cannot forge this — it would require knowing DISCOURSE_SSO_SECRET to generate valid `sig`, but the verification flows in both directions.

**Key constraint:** Mobile cannot call `/sso/discourse/initiate` directly because it needs Discourse-generated `sso+sig` as input.

## Options

### V1: Improved Browser UX (Recommended First Step)

Keep current flow but optimize:
- App opens Discourse topic URL as before
- If user is not logged in, Discourse shows "Login" button prominently
- After SSO completes, user returns to the topic they wanted

**What to improve:**
- Discourse can be configured to auto-redirect to SSO for anonymous users on specific pages
- `sso-verify` page auto-completes if keys exist in localStorage (already implemented)
- Consider In-App Browser (WebView) instead of external browser for session persistence

**Pros:** No new auth surface, no backend changes
**Cons:** Still multi-step, external browser loses session between app launches

### V2: Server-Initiated SSO (Requires Investigation)

Server calls Discourse to generate SSO payload, passes nonce to mobile, mobile signs, server completes callback.

**Unknown:** Does Discourse have a stable API endpoint for generating SSO initiation payloads? Standard DiscourseConnect is redirect-based, not API-based. If Discourse only supports redirect-based initiation, V2 requires either:
- HTML scraping of Discourse SSO redirect (fragile, not recommended)
- Custom Discourse plugin (heavy, not recommended for MVP)

**Pros:** True seamless from mobile
**Cons:** New attack surface, Discourse API dependency unknown

### V3: Pre-Auth URL (REJECTED)

App generates a signed token and appends to forum URL. Server validates and creates session.

**Why rejected:** Bypasses Discourse SSO HMAC verification. Creates a parallel auth path outside DiscourseConnect. Violates the trust model where Discourse initiates SSO.

## Threat Model

| Threat | Mitigation |
|--------|-----------|
| SSO challenge must be fresh | Nonce TTL 300s in Redis, deleted after use |
| Private key must not leave device | Only signature transmitted, never key |
| Discourse HMAC must be verified | `_verify_sig()` on initiate (unchanged) |
| V2 server-initiated: MITM | Must use HTTPS for Discourse API call |
| V3 pre-auth: bypass | REJECTED — not implemented |

## Decision

1. **V1 first:** Optimize current browser-based flow (In-App Browser, auto-SSO config on Discourse)
2. **V2 investigate:** Check Discourse API for programmatic SSO initiation before building
3. **V3 rejected:** No pre-auth URL bypass

## Open Questions

1. Does Discourse support API-based SSO initiation? (`POST /session/sso` or similar)
2. Can Discourse be configured to auto-redirect anonymous users to SSO?
3. Would React Native WebView with cookie persistence solve the session problem?
4. Is Discourse Hub app integration an option? (separate app, may handle SSO natively)

## Next Steps

- Check Discourse admin settings for "Force SSO" / anonymous redirect options
- Test In-App Browser (expo-web-browser) with cookie persistence
- Only after V1 assessment: investigate V2 feasibility
- No product code until plan is accepted
