# R3 wiki — full source migration report

Date: 2026-09-20

Status: `SOURCE_VALIDATED`

Branch: `feat/redesign-r3-wiki-all-20260920`

Base commit: `3e485a4c4c68172052e4559d1a624e9293961737`
(merge of pilot PR #334)

Scope: Complete R3 source migration of the 13 remaining wiki pages.
The pilot (`docs/wiki/index.html`) was unchanged.
No production deploy, server, database, DNS, IAM, secret, provider,
payment, mobile-store or other runtime mutation occurred.

## Changed files

### HTML pages (13)

- `docs/wiki/api.html`
- `docs/wiki/architecture.html`
- `docs/wiki/broadcasting.html`
- `docs/wiki/contributing.html`
- `docs/wiki/database.html`
- `docs/wiki/delete-account.html`
- `docs/wiki/faq.html`
- `docs/wiki/modules.html`
- `docs/wiki/privacy.html`
- `docs/wiki/roadmap.html`
- `docs/wiki/security.html`
- `docs/wiki/whitepaper.html`
- `docs/wiki/zk-voting.html`

### Shared assets (2)

- `docs/assets/redesign-v2/r3-wiki.css` — extended with table, badge, inline
  code, info/warn/success box, FAQ accordion, roadmap accordion,
  zk-voting `.content` container, `.card-icon`, and animation-frame mobile
  safety rules.  All new rules use local tokens only; no external URLs,
  fonts, icons or CDN assets were introduced.
- `docs/assets/redesign-v2/r3-faq-accessibility.js` — local progressive
  enhancement that gives the 57 existing FAQ questions focusable button
  semantics, linked answers, synchronized expanded state and Enter/Space
  activation while preserving the existing click handler.

### Validator and tests (3)

- `scripts/redesign/r3_wiki_pilot_check.py` — extended with:
  - `WIKI_RELS` tuple (all 14 wiki paths)
  - `WIKI_PAGES_WITH_HERO` frozenset (all except `zk-voting.html`)
  - `check_nonwiki_parity()` — parity gate for non-wiki pages (full-wiki gate)
  - `check_wiki_page_preservation()` — generic per-page preservation check
  - `check_r3_wiki_page()` — per-page preservation + structure runner
  - `check_r3_all()` — full-wiki gate entry point
  - `check_structure()` gains `requires_hero: bool` parameter
  - `check_pilot_preservation()` now delegates to the generic function
  - `main()` runs the full-wiki gate by default, retains `--all` for explicit
    CI commands, and exposes the historical pilot-only gate through `--pilot`
  - Pilot-only `check_r3()` and `check_nonpilot_parity()` remain unchanged

- `scripts/redesign/test_r3_wiki_pilot_check.py` — added:
  - `RealTreeTest.test_real_tree_all_wiki_passes` — full-wiki gate real-tree
  - `RealTreeTest.test_real_tree_pilot_page_passes` — pilot preservation check
  - `AllWikiPreservationTest` — 13 per-page preservation tests
  - `StructureTest.test_no_hero_page_passes_without_hero`
  - `StructureTest.test_no_hero_page_fails_if_hero_present`
  - `StructureTest.test_hero_required_page_fails_without_hero`
  - `ParityTest.test_nonwiki_parity_allows_all_wiki_pages`
  - `ParityTest.test_nonwiki_parity_rejects_changed_non_wiki_page`

- `scripts/redesign/test_r0_inventory.py` — updated allowed change set from
  `{docs/index.html, docs/wiki/index.html}` to
  `{docs/index.html} ∪ all 14 wiki pages`.

## Markup contract applied to all 13 pages

Each page received exactly:

1. Three local stylesheet links inserted after `</style>` in the exact order:
   ```html
   <link rel="stylesheet" href="../assets/redesign-v2/tokens.css"/>
   <link rel="stylesheet" href="../assets/redesign-v2/foundation.css"/>
   <link rel="stylesheet" href="../assets/redesign-v2/r3-wiki.css"/>
   ```
   Pre-existing external stylesheets (e.g. `../animations/css/ekklesia-motion.css`
   on `architecture.html` and `security.html`) were preserved.

2. One bilingual skip link immediately before `<nav>`:
   ```html
   <a href="#main" class="pnx2-skip" data-el="Μετάβαση στο κύριο περιεχόμενο" data-en="Skip to main content">Μετάβαση στο κύριο περιεχόμενο</a>
   ```

3. `class="pnx2-header"` added to the existing `<nav>` element.

4. `<main id="main">` inserted immediately after `</nav>`.

5. `</main>` inserted immediately before `<footer>`.

6. `class="pnx2-footer"` added to the existing `<footer>` element.

All pre-existing text, bilingual pairs, link destinations, metadata, scripts,
event handlers, inline styles, forms, API contracts, JSON-LD, analytics and
external hosts were preserved exactly.  No editorial changes were made.

## Hero handling

`zk-voting.html` has no `.hero` element in its R0 baseline.  The structural
check passes for it with `requires_hero=False`.  All other 13 wiki pages have
a `.hero` inside `main#main` and pass with `requires_hero=True`.

## Verification — exact commands and real results

```
python3 scripts/redesign/r3_wiki_pilot_check.py --all
→  OK  r3_wiki_all_check: all checks passed

python3 -m unittest discover -s scripts/redesign -p 'test_*.py'
→  Ran 117 tests  OK

python3 scripts/redesign/r1_foundation_check.py
→  R1 foundation check passed (design/redesign-v2/foundation)

python3 -m py_compile scripts/redesign/r3_wiki_pilot_check.py \
        scripts/redesign/test_r3_wiki_pilot_check.py \
        scripts/redesign/test_r0_inventory.py
→  (exit 0)

git diff --check
→  (exit 0)
```

## Sol integration verification

- All 14 wiki pages were loaded in real headless Chromium at 1440x1000 and
  360x800. The 28 page/viewport combinations had no document-level horizontal
  overflow, missing landmarks, broken local images, table-containment failure,
  language-toggle failure or migration-attributable JavaScript exception.
- A browser check found two pre-existing 28px copy buttons on Broadcasting;
  the shared R3 stylesheet now enforces the 44px target for main-content
  buttons. It also keeps very tall mobile table wrappers visible where the
  pre-existing 10% IntersectionObserver threshold cannot be reached.
- The local-origin browser run produced the expected CORS rejection for the
  pre-existing Modules health request to `api.ekklesia.gr`; this is a local
  test-origin condition and no request URL or API contract changed.
- Static local links, resources and form actions resolve across all 14 pages.
- Gitleaks found no secret in the complete worktree.
- CodeRabbit identified two valid bounded findings. The structural parser now
  rejects a footer nested inside `main#main`, with a regression test. The FAQ
  controls now have browser-verified keyboard semantics and synchronized ARIA
  state through the local adapter described above.

## Open gates

- The 13 pages have not been deployed to production.
- Canonical wording packages H and I remain separate; this migration preserves
  current wording without editorial changes.
- Production visual and live-route acceptance require a separately authorized
  rollout after normal protected-branch integration.
- The historical pilot gate (`check_r3()` / `--pilot`) correctly reports 13
  parity failures because those pages legitimately changed. The default CLI,
  `check_r3_all()` and `--all` use the authoritative full-wiki gate.
- Final verified evidence is appended to `BRIDGE.md` by Sol after integration.
