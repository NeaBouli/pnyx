# R3 wiki-shell pilot report

Date: 2026-09-20

Status: `SOURCE_VALIDATED`

Base commit: `c29d48050412c7a132a7bf2d543d2bf06df457ec`

Scope: R3 applies the checked-in redesign foundation to
`docs/wiki/index.html` only. It adds one local phase stylesheet and the R3
validation harness. The other 13 wiki pages and every non-wiki public page are
outside this pilot and remain unchanged. This report does not authorize or
record a production deploy.

## Result

- Applied the visible-grid wiki shell with square corners, no gradients,
  shadows or blur, restrained color use, explicit section borders and the
  existing dark footer.
- Added a bilingual skip link and semantic `main` target without changing any
  pre-existing copy, link destination, metadata, script, event handler or
  inline style.
- Kept all new assets local and introduced no external font, icon, script,
  import or host.
- Preserved the accepted R2 landing contracts and kept the other 33 public HTML
  pages byte-identical to their accepted phase state.
- Kept the legacy inline presentation in place for exact source parity; the R3
  stylesheet neutralizes conflicting gradients, shadows and rounded surfaces.

## Fail-closed preservation gate

`scripts/redesign/r3_wiki_pilot_check.py` compares the current parsed pilot
against the frozen R0 inventory. It requires exact preservation of:

- document language, title, metadata, analytics and scripts;
- all pre-existing text, Greek/English pairs and link destinations;
- event handlers, inline styles, external hosts and parser state;
- the previously accepted R2 landing contracts;
- every public HTML page outside the R2 landing and R3 pilot.

The only accepted pilot deltas are the bilingual skip link, its semantic main
target and three local redesign stylesheet links. The validator also rejects
fake structure in comments, external CSS imports or URLs, gradients, active
shadows, blur filters, negative letter spacing and viewport-scaled font sizes.

## Verification

- `python3 scripts/redesign/r3_wiki_pilot_check.py`: passed.
- `python3 -m unittest discover -s scripts/redesign -p 'test_*.py'`:
  94 tests passed.
- `python3 scripts/redesign/r1_foundation_check.py`: passed.
- Static link resolution: all 17 local pilot links resolve; the preserved
  `/el/bills` and `/el/results` destinations remain application routes.
- `python3 -m py_compile scripts/redesign/r3_wiki_pilot_check.py
  scripts/redesign/test_r3_wiki_pilot_check.py`: passed.
- `git diff --check`: passed.
- `gitleaks dir --no-banner --redact --exit-code 1 .`: no leaks found.
- Headless Chrome at 1440 x 1000 and 360 x 800: no document-level horizontal
  overflow; semantic main and hero placement verified.
- EL to EN language switching: verified on desktop and mobile.
- Visible interactive targets: no target below 44 px on either viewport.
- Legal modal at 360 px: contained within the viewport (`left=16`, `right=344`,
  `width=328`).
- Scroll-triggered sections: all eight fade-in elements became visible after
  normal wheel scrolling; the full Wiki, Quick Start, Bill Lifecycle, Stats
  and footer content remained visible and unclipped.

Protected-branch CI evidence is added at the integration gate rather than
anticipated in this source report.

## Open gates

- The remaining 13 wiki pages have not been migrated. Their migration may start
  only after this pilot passes protected review and the same content, link,
  accessibility and visual gates are retained.
- This source has not been deployed to production.
- Canonical wording packages H and I remain separate; this pilot deliberately
  preserves the current wording rather than making editorial changes.
- Production visual and live-route acceptance require a separately authorized
  rollout after normal protected-branch integration.

## Agent handoff

Claude Code was assigned the bounded implementation but was externally
token-limited before changing files. Kimi was attempted as the documented
fallback and was also externally token-limited. Sol implemented, reviewed and
verified the pilot without duplicate delegated changes and retains sole
integration authority.
