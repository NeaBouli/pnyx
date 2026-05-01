# Claude Code Integration Prompt — ekklesia.gr Motion Pack v1

You are working inside the ekklesia.gr / pnyx repository.

## Goal

Integrate the provided local animation assets into the existing landing page and selected wiki pages without changing product logic, backend logic, voting logic, API logic, identity logic, privacy wording, legal wording, or security behavior.

## Asset location

The motion pack contains:

```text
public/animations/svg/
public/animations/css/
public/animations/js/
public/animations/lottie/
```

If the repository uses a different public/static path, adapt paths carefully and document the mapping.

## Design rules

1. Keep the visual language calm, civic, serious and privacy-first.
2. Do not introduce gamified effects, confetti, aggressive pulses, party colors, or crypto-hype visuals.
3. Use SVG/CSS first.
4. Use Lottie only if the project already has a local Lottie runtime or explicitly accepts one.
5. Do not add external CDN dependencies.
6. Do not add trackers, cookies, analytics, remote loaders or third-party script calls.
7. Respect `prefers-reduced-motion`.
8. Preserve semantic HTML and accessibility.
9. Existing text must stay readable without JavaScript.
10. Do not change legal disclaimers or privacy claims.

## Target integration points

### Landing page

- Hero section:
  - Add `hero-pnyx-network.svg` as subtle decorative background.
  - Mark decorative image as `aria-hidden="true"` and `alt=""`.

- “Πώς λειτουργεί;” section:
  - Add `voting-flow.svg` after the section intro or beside the 4-step cards.
  - Use meaningful alt text.

- “Ο Κύκλος της Δημοκρατίας” section:
  - Add `bill-lifecycle-ring.svg`.

- Divergence / Βουλή vs Πολίτες section:
  - Add `divergence-balance.svg`.

- CPLM / Πολιτικός Καθρέφτης section:
  - Add `cplm-compass.svg`.

### Wiki pages

- `security.html`:
  - Add `privacy-flow.svg` near the verification/privacy model explanation.

- `privacy.html`:
  - Add `privacy-flow.svg` near “what is stored / not stored”.

- `architecture.html`:
  - Add `voting-flow.svg` near the verification flow.

- `roadmap.html`:
  - Do not add a new animation yet unless layout is stable; use CSS reveal only.

## CSS integration

- Import or copy `public/animations/css/ekklesia-motion.css` into the existing static entrypoint.
- If the site has existing CSS variables, map them to the `--ekk-*` variables.
- Keep class names prefixed with `ekk-`.
- Do not duplicate resets.

Suggested variable bridge:

```css
:root {
  --ekk-bg: var(--background, #0b1020);
  --ekk-surface: var(--surface, #111827);
  --ekk-card: var(--card, #172033);
  --ekk-text: var(--foreground, #f8fafc);
  --ekk-muted: var(--muted, #94a3b8);
  --ekk-accent: var(--accent, #c9a227);
  --ekk-accent-2: var(--accent-secondary, #38bdf8);
}
```

## JavaScript integration

- Add `motion-observer.js` only if the project does not already have an IntersectionObserver reveal helper.
- If an existing reveal helper exists, reuse it and skip this JS file.
- Load with `defer`.
- Ensure content remains visible if JS is disabled.

## Example markup

```html
<section id="how-it-works" class="ekk-fade-up">
  <div class="section-copy">
    <!-- existing content -->
  </div>
  <figure class="ekk-visual-card ekk-visual-frame">
    <img
      src="/animations/svg/voting-flow.svg"
      alt="Ροή ψήφου: SMS, hash, Ed25519 κλειδί στη συσκευή, υπογεγραμμένη ψήφος και δημόσιο αποτέλεσμα"
      loading="lazy"
      decoding="async"
    >
  </figure>
</section>
```

## Deliverables after integration

Report:

1. Modified files.
2. Inserted assets and target sections.
3. Confirm no backend/API/security logic was changed.
4. Confirm no external CDN/tracker/cookie was added.
5. Confirm reduced-motion behavior.
6. Run available build/lint/test commands and paste results.
7. Note any broken paths or unclear structure.

If uncertain, create a short `docs/agent-bridge/DECISIONS.md` note rather than guessing destructively.
