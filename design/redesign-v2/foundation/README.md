# redesign-v2 foundation (R1) — isolated static foundation

Status: `ISOLATED_FOUNDATION` — reference implementation of the redesign
shell primitives. **Not public, not deployed, not linked from any page under
`docs/`.** It changes no existing file and no production or live-website
behavior.

## Contents

- `tokens.css` — locally scoped design tokens copied from the reference-only
  handoff `design/handoffs/ekklesia-redesign-2026-09-16/source/README.md`
  ("Design-Tokens"). All custom properties carry the `--pnx2-` prefix so the
  later integration cannot collide with the legacy `:root` variables used by
  the current public pages.
- `foundation.css` — base shell: sticky header with 2px ink border,
  wrapping nav, footer, section/grid primitives, buttons, base
  loading/error/empty states, keyboard-focus style, 360px-safe responsive
  rules.
- `index.html` — semantic header/footer/page-shell demo showing the states
  and focus behavior. All copy on the page is placeholder demo text; it is
  not canonical wording.

## Isolation

- The directory lives outside `docs/`; nothing here is served by the public
  site.
- No file outside this directory imports or references these assets.
- The R0 allowlist (`docs/planning/r0/PUBLIC_HTML_ALLOWLIST.txt`) freezes the
  public surface, so this demo can never silently enter the public inventory.
- The demo is pure HTML/CSS: no `<script>`, inline styles, inline event
  handlers, runtime API calls or `support.js` (the handoff's prototype runtime
  is explicitly excluded), no telemetry, no `http(s)` references of any kind.

## Later integration contract (for R2+, not active now)

1. A page that adopts the foundation links `tokens.css` then
   `foundation.css`, or receives an equivalent inlined subset approved in
   that phase.
2. Page content is rebuilt against the shell classes (`pnx2-*`) while the
   canonical bilingual text and behavior proven in the R0 inventory
   (`docs/planning/r0/R0_DOCS_SURFACE_INVENTORY.json`, per-page category
   hashes) is preserved verbatim.
3. Parity is proven per page against the R0 category hashes before any
   deployment proposal. Migration phases follow the frozen order in
   `docs/planning/EKA_REMEDIATION_AND_REDESIGN_PLAN_2026-09-19.md` and each
   needs its own explicit approval.

## CSP / privacy posture

- Zero external requests: the foundation is compatible with a strict
  `default-src 'self'` policy and adds no new host to the public surface.
- The handoff's Google Fonts and unpkg Lucide loads were **not** adopted.
  No font, icon, script or image was downloaded or embedded.
- No cookies, storage access, fingerprinting surface or analytics hooks are
  introduced.
- The final font/icon and CSP decision remains with the owner/Sol
  (EKA-30 family); this foundation does not preempt it.

## Documented fallbacks

- **Fonts:** the handoff specifies Archivo (weights 400–900). No locally
  licensed Archivo build exists in this repository, so `tokens.css` defines
  `--pnx2-font-sans` as a system-font stack. When the owner approves a
  license-safe local Archivo (or an alternative), only the token value
  changes.
- **Icons:** the handoff uses Lucide from a CDN, which is not permitted
  here. The foundation ships no icons (text-only controls). A locally
  vendored, license-cleared icon set is a separate gate.

## Unresolved gates (owner/Sol decisions — not decided here)

1. Archivo font: source, license, hosting and CSP allowance.
2. Lucide (or other) icon set: local vendoring and license check.
3. Final CSP policy for the redesigned surface (EKA-30 family).
4. Canonical bilingual content freeze (packages H/I) — no page text is
   approved by this foundation.
5. Owner visual inputs listed in the handoff: Pnyx graphic, SVG logo,
   animated-diagram recoloring, representative-app screenshots.
6. Any adoption of this shell by real pages (R2+), each separately approved.

## Automated checks

Stdlib-only, same validator family as R0:

```bash
python3 scripts/redesign/r1_foundation_check.py          # validate foundation
python3 -m unittest discover -s scripts/redesign -p 'test_*.py'   # all R0+R1 tests
```

The check fails on: external `http(s)` references, any script or inline
event handler, missing viewport/lang/focus hooks, missing loading/error/empty
state hooks, fixed pixel widths above 360px, nonzero border-radius,
gradients, shadows, sub-44px interaction targets and missing required token
values.
