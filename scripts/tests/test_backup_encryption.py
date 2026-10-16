"""ADR-007 S3: off-site backups are encrypted with age before upload.

Runs scripts/backup-offsite.sh with shims for docker/sftp/du in a temp dir.
Skipped when the `age` binary is not installed.
"""
import hashlib
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "backup-offsite.sh"
HAVE_AGE = shutil.which("age") and shutil.which("age-keygen")
if os.getenv("BACKUP_TEST_REQUIRE_AGE") == "1" and not HAVE_AGE:
    raise RuntimeError("age/age-keygen required for this test run (CI)")


@unittest.skipUnless(HAVE_AGE, "age not installed")
class BackupEncryptionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.backups = self.tmp / "backups"
        self.uploads = self.tmp / "sftp.log"
        key = subprocess.run(["age-keygen"], capture_output=True, text=True, check=True).stdout
        self.identity = self.tmp / "test-identity.txt"
        self.identity.write_text(key)
        self.recipient = next(l.split(": ")[1] for l in key.splitlines() if l.startswith("# public key: "))
        (self.bin / "docker").write_text(textwrap.dedent("""\
            #!/bin/bash
            case "$*" in
              *pg_dump*) echo "SYNTHETIC-DUMP-$(date +%s%N)" ;;
              *redis-cli*) exit 0 ;;
              *psql*) echo "y803a2b3c4d5" ;;
              cp*) exit 1 ;;
            esac
            """))
        (self.bin / "sftp").write_text(f"#!/bin/bash\ncat >> {self.uploads}\n")
        for f in ("docker", "sftp"):
            os.chmod(self.bin / f, 0o755)
        # Script writes to /opt/backups/ekklesia; run a copy pointing at the temp dir.
        self.script = self.tmp / "backup-offsite.sh"
        self.script.write_text(SCRIPT.read_text().replace('LOCAL_BACKUP_DIR="/opt/backups/ekklesia"', f'LOCAL_BACKUP_DIR="{self.backups}"'))
        (self.tmp / "lib").mkdir()
        shutil.copy(REPO / "scripts" / "lib" / "backup-encrypt.sh", self.tmp / "lib" / "backup-encrypt.sh")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_backup(self, **env: str) -> subprocess.CompletedProcess:
        full = {
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "STORAGE_BOX_USER": "u", "STORAGE_BOX_HOST": "h", "HOME": str(self.tmp),
            **env,
        }
        return subprocess.run(["bash", str(self.script)], capture_output=True, text=True, env=full)

    def uploaded(self) -> list[str]:
        return [l.split()[1] for l in self.uploads.read_text().splitlines() if l.strip().startswith("put ")] if self.uploads.exists() else []

    def test_encrypted_upload_round_trips_with_the_offline_key(self) -> None:
        r = self.run_backup(BACKUP_AGE_RECIPIENT=self.recipient)
        self.assertEqual(r.returncode, 0, r.stderr)
        files = self.uploaded()
        self.assertTrue(files and all(f.endswith(".tar.gz.age") for f in files), files)
        enc = Path(files[0])
        self.assertTrue(enc.read_bytes().startswith(b"age-encryption.org/v1"))
        plain = Path(str(enc)[: -len(".age")])
        dec = self.tmp / "dec.tar.gz"
        subprocess.run(["age", "--decrypt", "-i", str(self.identity), "-o", str(dec), str(enc)], check=True)
        self.assertEqual(hashlib.sha256(dec.read_bytes()).hexdigest(), hashlib.sha256(plain.read_bytes()).hexdigest())
        self.assertNotIn(b"SYNTHETIC-DUMP", enc.read_bytes())

    def test_required_encryption_without_key_uploads_nothing(self) -> None:
        r = self.run_backup(BACKUP_REQUIRE_ENCRYPTION="true")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.uploaded(), [])

    def test_invalid_recipient_uploads_nothing(self) -> None:
        r = self.run_backup(BACKUP_AGE_RECIPIENT="ssh-ed25519 AAAA")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.uploaded(), [])

    def test_missing_age_binary_uploads_nothing(self) -> None:
        nobin = self.tmp / "noage"
        nobin.mkdir()
        for tool in ("bash", "tar", "gzip", "date", "mkdir", "find", "du", "cut", "basename", "dirname", "rm", "head", "grep", "wc", "sleep", "cat", "printf"):
            path = shutil.which(tool)
            if path:
                os.symlink(path, nobin / tool)
        env = {"PATH": f"{self.bin}:{nobin}", "STORAGE_BOX_USER": "u", "STORAGE_BOX_HOST": "h",
               "HOME": str(self.tmp), "BACKUP_AGE_RECIPIENT": self.recipient}
        r = subprocess.run([shutil.which("bash"), str(self.script)], capture_output=True, text=True, env=env)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.uploaded(), [])

    def test_default_stays_unencrypted_with_a_warning(self) -> None:
        r = self.run_backup()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(all(f.endswith(".tar.gz") for f in self.uploaded()))
        self.assertIn("UNENCRYPTED", r.stderr)


if __name__ == "__main__":
    unittest.main()
