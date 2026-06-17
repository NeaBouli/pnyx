# GH#111 Nullifier v2 Operator Checklist

Status: ready checklist, not activated.
Last updated: 2026-06-17.

Use this short checklist only together with
`docs/agent-bridge/GH111_NULLIFIER_V2_CANARY_RUNBOOK.md`.

## What This Window Proves

GH#111 is complete only when production v2 KDF is temporarily activated and a
real S10 app verification through the HLR path proves one of these outcomes:

1. An existing v1 identity migrates to v2 in the same DB row.
2. A new real identity is created with both v1 and v2 anchors.

Admin-test identities and DB-only checks are not sufficient.

## Do Not Start Unless

- Gio is present for the whole window.
- S10 is connected, unlocked, charged, and has network.
- The installed app can open `Profile -> Verification / New key`.
- A real Greek mobile number can be verified through HLR.
- No unrelated deploy/release/test is running.
- There is enough time to finish activation, app verification, post-verify
  compare, and either keep-v2 or rollback-v1.

## Strict No-Go Conditions

Abort before activation if any item is true:

- Monitor is not clean.
- `package_check.json` is missing or has `"ok": false`.
- API health is unstable.
- Latest prep script fails.
- The S10 app cannot reach `VerifyScreen`.
- Gio cannot complete real HLR verification.
- There is uncertainty whether this is GH#111 or GH#112 work. They must not be
  mixed.

## Safe Start Sequence

Optional read-only status check:

```bash
cd /opt/ekklesia/app
scripts/gh111-status-nullifier-v2-window.sh
```

This command must not be treated as activation. It only reports current KDF,
API health, latest package status, and live preflight counters.

Run on the production host:

```bash
cd /opt/ekklesia/app
scripts/gh111-prepare-nullifier-v2-window.sh
```

Copy the printed value:

```text
GH111_BACKUP_DIR=/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_...
```

Then activate only with the guarded helper:

```bash
cd /opt/ekklesia/app
BACKUP_DIR=/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_... \
GH111_OPERATOR_CONFIRM=GH111-ACTIVATE-V2 \
  scripts/gh111-activate-nullifier-v2-window.sh activate-v2
```

The helper must report healthy API and clean monitor before Gio touches the app.

## Gio App Step

After activation succeeds:

1. Open the app on S10.
2. Go to `Profile -> Verification / New key`.
3. Complete real HLR verification with the intended phone number.
4. Do not repeat the verification unless the operator explicitly says so.

Never paste or log the phone number into terminal, GitHub, Bridge, or chat.

## Post-Verify Sequence

Run exactly one post-verify mode:

```bash
cd /opt/ekklesia/app
BACKUP_DIR=/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_... \
  scripts/gh111-postverify-nullifier-v2-window.sh existing-reregistration
```

or:

```bash
cd /opt/ekklesia/app
BACKUP_DIR=/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_... \
  scripts/gh111-postverify-nullifier-v2-window.sh new-registration
```

Use `existing-reregistration` only when the phone already had an active v1
identity. Use `new-registration` only for a phone without an existing identity.

## Success Criteria

GH#111 can be marked complete only if all are true:

- Production KDF was activated through the guarded helper.
- Real S10 HLR verification completed.
- Post-verify helper produced a compare report.
- Compare report has no blockers.
- v2 invariants are clean:
  - no malformed v2 hash
  - no `nullifier_version='v2'` row without `nullifier_hash_v2`
  - no `nullifier_hash_v2` row without matching version
  - no unexpected active/revoked identity drift
- Operator decision is recorded: keep v2 active or rollback to v1.
- Bridge + GitHub #111 are updated with the result.

## Rollback

If health, monitor, or compare fails, rollback immediately:

```bash
cd /opt/ekklesia/app
BACKUP_DIR=/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_... \
GH111_OPERATOR_CONFIRM=GH111-ROLLBACK-V1 \
  scripts/gh111-activate-nullifier-v2-window.sh rollback-v1
```

After rollback, run monitor once and record the result in the Bridge.

## Current Safe State

As of the latest audit:

- Production KDF: `v1`.
- Latest known preflight package:
  `/opt/ekklesia/backups/pre_gh111_nullifier_v2_canary_20260617_064644`.
- That package has `package_check.json` `ok=true`, no blockers/warnings.
- GH#111 remains prepared, not complete.
