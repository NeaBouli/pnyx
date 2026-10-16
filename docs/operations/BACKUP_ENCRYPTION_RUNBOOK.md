# Runbook: encrypt off-site backups (ADR-007 S3)

Status: prepared (code merged, **not active**). Activation is a Gio gate: the private key is a secret and stays with Gio only.

## Why
The daily off-site backup (`scripts/backup-offsite.sh`, cron 04:00 UTC) uploads a full `pg_dump` + Redis snapshot. Without encryption, anyone with access to the backup host can read every identity ↔ vote link (EVA-006).

## How it works
- `age` encrypts the archive **on the server** for a public key (`age1…`) **before** the upload. The server only holds the public key; it can encrypt but never decrypt.
- Uploaded files end in `.tar.gz.age`.
- `BACKUP_REQUIRE_ENCRYPTION=true`: without a valid key, or without `age` installed, the backup aborts **before** the upload. Nothing unencrypted leaves the server.
- Local copies on the prod server (`/opt/backups/ekklesia`) stay unencrypted. They sit on the same host as the database itself and give no extra exposure.

## 1. Generate the key (Gio, offline)
On a trusted computer (ideally offline):
```bash
age-keygen -o ekklesia-backup-2026.key      # private key, NEVER on the server, in a chat, or in the repo
grep "public key" ekklesia-backup-2026.key   # → age1…  (this public key is not a secret)
```
Storage (at least two separate places):
1. offline (USB stick / paper copy of the key line) at Gio's;
2. a copy on the Synology inside an encrypted folder/container.

Losing the private key = all encrypted backups are worthless. Test the restore (step 4) before relying on it.

## 2. Activate (server, after Gio's yes; the public key comes from Gio)
```bash
apt-get install -y age && age --version
# in /etc/ekklesia-offsite-backup.env (root-only, mode 600):
BACKUP_AGE_RECIPIENT=age1…            # public key from step 1
BACKUP_REQUIRE_ENCRYPTION=true
```
Then run once manually: `/usr/local/sbin/ekklesia-run-offsite-backup`. The log should show `Uploading ekklesia-backup-…tar.gz.age`.

## 3. Adjust the follow-on scripts (same gate)
- `/usr/local/sbin/ekklesia-offsite-retention`: extend the name pattern and the "newest backup > 1 MB" guard to `ekklesia-backup-*.tar.gz.age`.
- Restore check: decrypt first (step 4); it can't run on the server any more without the private key. That's intentional.

## 4. Restore test (Gio, offline machine)
```bash
sftp -P 22 <backup-user>@<backup-host>:backups/ekklesia/daily/ekklesia-backup-<ts>.tar.gz.age .
age --decrypt -i ekklesia-backup-2026.key -o restore.tar.gz ekklesia-backup-<ts>.tar.gz.age
tar -xzf restore.tar.gz            # db-<ts>.dump, redis-<ts>.rdb, alembic-<ts>.txt
# import into a temporary PostgreSQL (not prod), compare counts
```

## 5. Old unencrypted backups
The unencrypted archives on the backup host stay readable until they're deleted. Recommendation: once at least 7 encrypted dailies **and** a successful restore test (step 4) exist, delete the unencrypted files in `daily/weekly/monthly`. That's a separate Gio gate (deletion), with a list check like the retention cleanup.

## Rollback
Remove `BACKUP_AGE_RECIPIENT` / `BACKUP_REQUIRE_ENCRYPTION` from the env file. The next backup is unencrypted again (log warning). Encrypted backups stay readable with the offline key.

## Evidence (16.10.)
`scripts/tests/test_backup_encryption.py` (runs where `age` is installed; here in a `python:3.12-alpine` container with `age`):
- encrypted upload, decryption with a test key gives an identical archive, no plaintext in the encrypted file;
- with `REQUIRE` and no key: no upload;
- invalid key: no upload;
- `age` missing: no upload;
- default unencrypted, with a warning.

A mutation (encryption skipped) fails 3 tests.
