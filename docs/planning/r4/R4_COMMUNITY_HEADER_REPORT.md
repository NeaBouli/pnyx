# R4 Community And Responsive Header Report

Date: 2026-09-20
Status: validated source candidate, not deployed

## Scope

R4 keeps the approved R2 landing content intact and changes only these bounded
surfaces:

- adds the local redesign shell to `docs/community.html` without changing its
  copy, links, forms, API/storage contracts, payment tiles or scripts;
- consolidates the five public-data links into the existing Next.js
  `NavHeader`, removing only the duplicate per-page navigation instances;
- makes the static and dynamic public headers one-line and horizontally
  scrollable at narrow widths;
- corrects the verified 360 px landing chat overflow without overriding the
  JavaScript-controlled open/closed state.

No Wiki, API, database, DNS, secret, IAM, provider, payment behavior or other
service is changed by this candidate.

## Preservation Evidence

`scripts/redesign/r4_community_header_check.py` compares the live Community
page against the frozen R0 inventory. It preserves the exact document,
metadata, SEO, JSON-LD, forms, API contracts, storage, media, interactions,
scripts, external hosts, states and errors. It permits only the local CSS
resources, skip link and `main` landmark introduced by the redesign shell.

The existing `PublicDataNav.tsx` source remains in place. The five pages that
previously rendered it now rely on the single global `NavHeader` instead.

## Browser Acceptance

Local browser checks used the built candidate and the static `docs/` tree.

| Surface | Viewport | Result |
| --- | --- | --- |
| Landing | 360 x 800 | 62 px one-line header, no document overflow, chat panel fully contained (`left=16`, `right=329`) |
| Community | 360 x 800 | 62 px one-line header, no document overflow, one-column narrow cards, no broken loaded images |
| Dynamic results | 360 x 800 | 68 px one-line header, one global nav, no document overflow |
| Landing | 1280 x 720 | 86 px one-line header, no document overflow, no broken loaded images |
| Community | 1280 x 720 | 60 px one-line header, no document overflow, no broken loaded images |

The Community EL/EN control visibly changed the page content and returned to
Greek. Local API-backed Community values remained subject to normal local-origin
availability; no API contract or production runtime was changed.

## Verification

- R4 parser-backed gate: passed.
- Redesign unit suite: 124 passed.
- R1 foundation gate: passed.
- Web ESLint: passed.
- Web TypeScript: passed.
- Web Vitest: 70 passed across 6 files using the supported bundled Node 24
  runtime. The host Node 22.11 run was rejected by dependency engine/ESM
  compatibility and was not treated as product evidence.
- Next.js production build: passed.
- `npm audit --audit-level=high`: 0 vulnerabilities.
- `git diff --check`: passed.
- Gitleaks full redacted scan: no leaks found.
- Claude Code read-only review: no blocker; one intentional visual typography
  note and informational cleanup notes only.

## Production Rollout Note

The exact merged PR #333 landing image was built and passed isolated and
server-side checks. Real 360 px browser acceptance exposed the chat panel at
`left=-7`, so the Web-only switch was rolled back immediately to the dedicated
pre-rollout image. The rollback restored the previous landing while retaining
the already deployed Wiki release; API and all non-Web services remained
unchanged and healthy.

This R4 candidate contains the bounded chat correction. It requires normal PR
integration and a new, exact production authorization before any rollout.
