# R5 Landing Rollback and Repair - 2026-09-21

## Production state

The R5 landing image was rolled back to the last stable Web image at the
owner's request. The live Web container is healthy, has zero restarts and is
serving the rollback image. No API, database, DNS, secret, IAM, Wiki,
Community or other service was changed.

## Verified cause

- The historical blue band used the application logo instead of the supplied
  Pnyx/Acropolis artwork.
- The header was 102 px high and changed to a multi-row/column layout at the
  tablet breakpoint.
- A hard-coded `67%` divergence example was present in production markup.
- The latest citizen-only result was written into the hero comparison even
  though the representation endpoint reported zero analyzed bills and no
  cumulative representation score.

The live result endpoint currently has one citizen vote. That is a valid
citizen result, but it is not evidence for a Parliament-versus-citizens
comparison. The repair therefore keeps the hero and representation metrics in
their dash state until the representation endpoint supplies at least one
analyzed bill and a non-null score.

## Repair candidate

- Restores the exact Pnyx/Acropolis bitmap from the owner handoff and the
  supplied historical-band geometry.
- Keeps the header at 86 px on desktop and 72 px on tablet/mobile, sticky and
  single-row, with internally scrollable navigation where necessary.
- Removes the hard-coded divergence and separates citizen-only results from
  representation metrics.
- Applies the handoff's flat controls to the touched Forum, newsletter and
  chat surfaces.
- Adds regression coverage for the artwork checksum, truthful empty states,
  responsive header and flat touched controls.

## Verification

- `python3 -m unittest discover -s scripts/redesign -p 'test_*.py'`:
  151 tests passed.
- `python3 scripts/redesign/r2_landing_check.py --json`: no violations.
- `python3 -m compileall -q scripts/redesign`: passed.
- `git diff --check`: passed.
- Redacted Gitleaks scan of the binary diff: no leaks.
- Browser checks at 1440 x 1000, 820 x 1180 and 390 x 844: no document
  overflow; sticky single-row header; exact 86/72 px heights; Acropolis asset
  loaded; comparison values remain dashes; no browser errors.

The repaired candidate has not been deployed. The stable rollback remains
live pending normal review and an explicit release decision.
