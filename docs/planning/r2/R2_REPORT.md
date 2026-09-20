# R2 landing-page redesign report

Date: 2026-09-20

Status: `SOURCE_VALIDATED`

Base commit: `8f3148cd95ea8381dee336c620166e0adb8e67a6`

Scope: R2 changes only `docs/index.html`, three local stylesheets under
`docs/assets/redesign-v2/`, and the R2 validation harness. No other public HTML
page is changed. This report does not authorize or record a production deploy.

## Result

- Applied the checked-in R1 token and foundation layers to the landing page.
- Added the R2 landing override with the handoff's visible-grid treatment,
  square corners, no shadows, no gradients, one accent color, left-aligned
  section hierarchy, explicit dividers, responsive controls and dark footer.
- Added a bilingual skip link and semantic `main` target without changing any
  existing text, link, form, API call, storage access or JavaScript behavior.
- Preserved the complete pre-redesign landing content and its current order.
- Kept all assets local. No new external font, icon, script or host was added.

## Fail-closed preservation gate

`scripts/redesign/r2_landing_check.py` compares the current parsed landing
against the frozen R0 inventory. The following contracts must remain exact:

- document language/title, metadata, SEO and JSON-LD;
- forms, API contracts, storage use, media and scripts;
- event handlers, timers, message listeners and public UI states;
- external hosts and parser errors;
- all pre-existing bilingual pairs, links, text chunks, navigation targets,
  resources and inline styles.

The only accepted deltas are the bilingual skip link, its `main` target and the
three local redesign stylesheets. The other 34 allowlisted public HTML pages
must remain byte-identical to R0.

## Verification

- `python3 scripts/redesign/r2_landing_check.py`: passed.
- `python3 -m unittest discover -s scripts/redesign -p 'test_*.py'`:
  73 tests passed.
- `python3 scripts/redesign/r1_foundation_check.py`: passed.
- `git diff --check`: passed.
- `gitleaks dir --no-banner --redact --exit-code 1 .`: no leaks found.
- Headless Chrome at 1440 x 1000 and 360 x 800: no document-level horizontal
  overflow or clipped page element after normal scroll activation.
- EL to EN language toggle: verified on desktop and mobile.
- Visible buttons, text inputs and selects: minimum 44 px target verified;
  newsletter option labels provide 44 px targets.
- Chat panel at 360 px: verified fully inside the viewport (`left=8`,
  `right=336`, `width=328`).
- Legal modal at 360 px: verified fully inside the viewport.
- CodeRabbit's three valid review findings were fixed: the page now exposes a
  semantic `main` landmark around the primary content, structural checks parse
  live HTML relationships, and CSS checks cover quoted/protocol-relative
  imports plus `vw` inside `calc()` and `clamp()` declarations.

Local preview requests to `api.ekklesia.gr` were blocked by the production CORS
policy because the preview origin was `127.0.0.1`. This is expected for the
isolated local preview and is not treated as live-API acceptance. R2 changes no
API code or endpoint and the R0 API-contract inventory remains exact.

## Open gates

- This source has not been deployed to production.
- The handoff's Archivo and Lucide CDN proposals remain deliberately excluded
  pending their existing CSP/licensing decisions; the checked-in local system
  font and existing icons remain in use.
- Canonical wording packages H and I remain open. R2 preserves the current
  wording byte-for-byte rather than making an editorial decision.
- R3 and later redesign phases are not started by this task.
- Production visual and live-API acceptance require a separate authorized
  deployment task after normal protected-branch integration.

## Agent handoff

Claude Code implemented the initial bounded HTML/CSS and validator draft, then
became token-limited before reporting. Sol reviewed every change, replaced the
regex-based preservation checks with the R0 parser-backed gate, corrected the
mobile chat viewport defect, ran the complete verification above and retained
integration authority.
