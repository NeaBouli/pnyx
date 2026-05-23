# AUDIT BLOCK A — Website & Navigation
## Date: 2026-05-23

## A1: HTML Pages Inventory (31 files)

| File | canonical | og_title | og_desc | og_image | JSON-LD |
|------|-----------|----------|---------|----------|---------|
| community.html | ✅ | ✅ | ✅ | ✅ | ✅ |
| index.html | ✅ | ✅ | ✅ | ✅ | ✅ |
| govgr-dimos.html | ✅ | ✅ | ✅ | ✅ | ❌ |
| representative.html | ✅ | ✅ | ✅ | ✅ | ❌ |
| wiki/faq.html | ✅ | ✅ | ✅ | ✅ | ✅ |
| wiki/*.html (12 pages) | ✅ | ✅ | ✅ | ✅ | ❌ |
| tickets/index.html | ✅ | ❌ | ❌ | ❌ | ❌ |
| votes/*.html (3 pages) | ✅ | ❌ | ❌ | ❌ | ❌ |
| demo/*.html (3 pages) | ❌ | ❌ | ❌ | ❌ | ❌ |
| embed/*.html (3 pages) | ❌ | ❌ | ❌ | ❌ | ❌ |
| internal (mirror/sso/callback) | ❌ | ❌ | ❌ | ❌ | ❌ |

**Summary:** Public pages have canonical + OG. Embed/demo/internal pages correctly have no SEO. JSON-LD only on index + community + faq.

## A2: Broken Internal Links

**97 "broken" links found** — but most are false positives:
- `/el/bills`, `/el/results` → Next.js app routes (served by web container, not static files) — NOT broken
- `/pnx.png`, `/manifest.json`, `/favicon.ico` → served by web container — NOT broken
- `download/ekprosopos-latest.apk` → served by server download path — NOT broken
- `representative/index.html` → relative path issue in representative.html — **ACTUAL broken link**

**Real broken links: 1**
- `representative.html → representative/index.html` — should be `/representative/index.html` or removed

## A3: Sitemap vs Files

- **Sitemap URLs:** 24
- **Public HTML files:** 22
- **Missing from sitemap:** None (all public pages covered)
- **Extra in sitemap:** 2 Next.js routes (`/el/bills`, `/el/results`) — correct, not static files

## A4: Content Coherence

- **modules.html:** 33 MOD-references (25 modules, some appear in multiple rows) — OK
- **Roadmap Helios refs:** 0 — all replaced with Semaphore ✅
- **FAQ Helios:** Only in explanatory "Γιατί όχι Helios" section — correct ✅
- **Community fetch:** 41 fetch calls — all live data, no hardcoded values ✅

## A5: Live HTTP Status

| Status | URL |
|--------|-----|
| 200 | ekklesia.gr/ |
| 200 | ekklesia.gr/community.html |
| 308 | ekklesia.gr/wiki/ (redirect to wiki/index.html) |
| 200 | ekklesia.gr/wiki/faq.html |
| 200 | ekklesia.gr/wiki/roadmap.html |
| 200 | ekklesia.gr/wiki/modules.html |
| 200 | ekklesia.gr/wiki/zk-voting.html |
| 200 | ekklesia.gr/representative.html |
| 200 | ekklesia.gr/sitemap.xml |
| 200 | ekklesia.gr/robots.txt |
| 200 | api.ekklesia.gr/health |
| 200 | api.ekklesia.gr/api/v1/public/stats |

**All public URLs: 200 OK** (wiki/ redirect 308 is expected)

## A6: Mobile Screens vs API

**16 Screens**, **27 unique API endpoints called**.
All endpoints exist in API routers — no orphaned calls found.

## Findings Summary

| Severity | Finding |
|----------|---------|
| LOW | `representative.html` has broken relative link to `representative/index.html` |
| LOW | `tickets/index.html` + `votes/*.html` missing OG tags (embed widgets, low SEO priority) |
| LOW | `wiki/broadcasting.html` missing `og:description` |
| INFO | `wiki/` returns 308 redirect (expected, not broken) |
| INFO | demo/embed/internal pages correctly have no SEO tags |
| INFO | JSON-LD only on 3 pages (index, community, faq) — sufficient for core pages |
