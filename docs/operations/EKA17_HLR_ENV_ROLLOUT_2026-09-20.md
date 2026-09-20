# EKA-17 HLR environment rollout receipt

Date: 2026-09-20

## Scope

This was the separately authorized EKA-17 production gate after PR #331 merged
as `c18b75ffb616655a4b308bf7f314dc2f48472628`. The operation was limited to:

- overlaying the reviewed `packages/crypto/hlr.py` on the exact running API
  image;
- copying the complete legacy primary credential pair to the canonical
  `HLRLOOKUP_*` names without exposing values;
- recreating only `ekklesia-api`; and
- verifying health, credential selection, logs, usage and non-target
  invariants without performing an HLR provider request.

No database, DNS, IAM, Web, Dashboard, forum, store, payment, provider setting
or other service was changed.

## Preflight

- No shared-server build process was active and sufficient disk space existed.
- The production environment contained one complete legacy primary pair and
  one complete actual-fallback pair. The canonical pair was absent.
- Every host-file value was byte-identical to its running-container value; the
  previously documented drift risk did not reproduce.
- The source file from PR #331 and the staged server file both had SHA-256
  `74f982b192356bdae65d55be389a6708c7be183adab673e04492b7054fccf5b5`.
- Synthetic network-disabled tests passed for absent, legacy-only,
  canonical-preferred and partial-canonical fail-closed states.

## Rollout

- Candidate image:
  `ekklesia-api:eka17-c18b75f-20260920T133207Z`
- Retained rollback image:
  `ekklesia-api:rollback-pre-eka17-20260920T133207Z`
- Protected release directory:
  `/opt/ekklesia/releases/eka17-20260920T133207Z`
- The original environment file is preserved there with its metadata. The
  replacement was atomic and retained mode and ownership.
- Deprecated primary aliases remain temporarily. The actual fallback pair was
  not changed.
- The existing production Compose override chain was retained and extended by
  one image-only API override. Only `api` was force-recreated with `--no-deps`
  and `--no-build`.

## Acceptance

- Five repeated public health probes passed after startup.
- The live API file hash matches the reviewed PR #331 file.
- Canonical, legacy and fallback pairs are complete and byte-identical between
  the host environment and running container. Live primary resolution selects
  the canonical pair and matches the retained legacy pair.
- Public HLR status reports primary and fallback healthy.
- HLR usage counters were unchanged before and after the operation; no real
  telephone number or provider request was used.
- Credential, authentication, traceback and unhandled-error log scans were
  empty.
- `ekklesia-api` is running with restart count zero and was not OOM-killed.
- Every non-API container retained the same ID, image and status.

## Rollback

The exact previous image, original environment file and image-only rollback
Compose override are retained in the protected release directory. Rollback is
limited to atomically restoring that environment file and recreating only the
API with the rollback override, followed by the same health and log checks.

No rollback was required.
