# Ekklesia redesign handoff - import record

Status: `REFERENCE_ONLY` - no implementation or production publication approved.

## Provenance

- Original archive: `Seite-Design uberarbeiten.zip`
- Archive timestamp: 2026-09-16
- Imported: 2026-09-19
- SHA-256: `8e41f707ba410cfd2f982ebdb68b31dfc78fafe0c40283a3b373780ba498c742`
- Imported files: 13, preserved unchanged under `source/`
- Secret scan: no credential, private-key or password pattern found in the
  textual source files during intake.

The source is intentionally outside `docs/`. It must not be copied into the
public web root or treated as production code before the redesign gates below
have passed.

## What the handoff contains

- A high-fidelity static reference for four screens: landing, votes, download
  and wiki architecture.
- A design-system bundle, reference assets and a detailed implementation
  handoff covering the current static site and wiki.
- A prototype-only runtime (`support.js`). It exists solely to display the
  reference and is not an application dependency.

## Intake findings

The handoff is useful as a visual and interaction specification, but some of
its content cannot be copied verbatim:

1. It repeats audit-sensitive claims such as `0 Cookies / Trackers`, absolute
   privacy language and donation/feature status that must first be reconciled
   with EKA-25 and EKA-33..55.
2. Its release and distribution text is a dated snapshot. F-Droid, Google Play,
   APK, representative-app and iOS status must come from a newly verified
   canonical release manifest at implementation time.
3. The prototype loads Google Fonts and Lucide from external CDNs. The final
   asset strategy must satisfy privacy, availability and CSP work, including
   EKA-30; no external dependency is approved by this import.
4. The handoff says that all existing text must be retained word-for-word.
   Audit-required factual corrections take precedence. Corrected canonical
   content must be frozen before layout migration, then preserved exactly.
5. The static HTML is not evidence that API data, forms, language switching,
   accessibility, empty/error states or mobile breakpoints work in production.

## Redesign gates

Implementation remains blocked until all of the following are true:

- the current 35-page public surface has a content and behavior inventory;
- EKA content findings have canonical wording or an explicit owner decision;
- live endpoint and release facts have been reverified;
- external font/icon and CSP decisions are documented;
- each phase has desktop/mobile visual baselines and regression tests;
- one bounded phase is approved for execution.

The controlled plan is
[`docs/planning/EKA_REMEDIATION_AND_REDESIGN_PLAN_2026-09-19.md`](../../../docs/planning/EKA_REMEDIATION_AND_REDESIGN_PLAN_2026-09-19.md).

## Owner inputs still needed before implementation

- Keep the supplied Pnyx drawing or provide a higher-resolution image.
- Provide an authoritative SVG logo if one exists; otherwise retain the
  supplied transparent PNG pending visual acceptance.
- Decide whether the existing animated diagrams should be recolored and
  embedded or remain separate reference material.
- Decide whether representative-app screenshots belong on the public pages.
