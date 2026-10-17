"""No-network tests for secret delivery and backup URL compatibility."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class DatabaseRoleShellTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        self.capture = self.directory / "capture.jsonl"
        # Record test credentials to a disposable fixture, never stdout/argv.
        for name in ("psql", "docker"):
            script = self.bin / name
            script.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
with Path(os.environ['CAPTURE']).open('a') as output:
    output.write(json.dumps({'tool':Path(sys.argv[0]).name, 'args':sys.argv[1:],
       'PGDATABASE':os.getenv('PGDATABASE'), 'PGUSER':os.getenv('PGUSER'),
       'password':os.getenv('EKKLESIA_API_PASSWORD')})+'\\n')
if 'cp' in sys.argv: sys.exit(1)
if 'pg_dump' in sys.argv: print('SYNTHETIC DUMP')
if 'psql' in sys.argv: print('z901a2b3c4d5')
""")
            script.chmod(0o755)
        # Run the complete backup script with only its external commands stubbed.
        for name, body in (("sftp", "cat >/dev/null\n"), ("sleep", "exit 0\n")):
            script = self.bin / name
            script.write_text("#!/bin/bash\n" + body)
            script.chmod(0o755)
        self.env = {"PATH": f"{self.bin}:{os.environ['PATH']}", "CAPTURE": str(self.capture),
                    "PGDATABASE": "pnyx_test_roles", "PGUSER": "test_admin",
                    **{f"EKKLESIA_{role}_PASSWORD": "test'\\$@password" for role in ("API", "MIGRATOR", "MONITOR", "DASHBOARD", "BACKUP")}}

    def records(self):
        return [json.loads(line) for line in self.capture.read_text().splitlines()]

    def test_missing_secret_fails_before_psql(self):
        self.env.pop("EKKLESIA_MONITOR_PASSWORD")
        result = subprocess.run([str(ROOT / "scripts/ops/db-roles.sh")], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("EKKLESIA_MONITOR_PASSWORD", result.stderr)
        self.assertFalse(self.capture.exists())

    def test_psql_reads_secrets_from_environment(self):
        result = subprocess.run([str(ROOT / "scripts/ops/db-roles.sh")], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        record = self.records()[0]
        self.assertEqual(record["password"], self.env["EKKLESIA_API_PASSWORD"])
        self.assertNotIn(record["password"], " ".join(record["args"]) + result.stdout + result.stderr)
        self.assertIn("--no-psqlrc", record["args"])

    def test_docker_forwards_names_without_password_arguments(self):
        result = subprocess.run([str(ROOT / "scripts/ops/db-roles.sh"), "--docker", "isolated-db"], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        record = self.records()[0]
        self.assertIn("EKKLESIA_API_PASSWORD", record["args"])
        self.assertIn("PGPASSWORD", record["args"])
        self.assertNotIn(record["password"], " ".join(record["args"]) + result.stdout + result.stderr)

    def backup(self, url):
        script = self.directory / "backup-offsite.sh"
        script.write_text((ROOT / "scripts/backup-offsite.sh").read_text().replace(
            'LOCAL_BACKUP_DIR="/opt/backups/ekklesia"', f'LOCAL_BACKUP_DIR="{self.directory}/backups"'))
        library = self.directory / "lib"
        library.mkdir()
        (library / "backup-encrypt.sh").write_text((ROOT / "scripts/lib/backup-encrypt.sh").read_text())
        env = {**self.env, "BACKUP_DATABASE_URL": url, "POSTGRES_USER": "legacy", "POSTGRES_DB": "pnyx_test_legacy",
               "STORAGE_BOX_USER": "fixture", "STORAGE_BOX_HOST": "fixture.invalid"}
        result = subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        records = [r for r in self.records() if "pg_dump" in r["args"] or "psql" in r["args"]]
        self.assertEqual(len(records), 2)
        return records, result

    def test_backup_url_applies_to_both_dump_and_alembic_capture(self):
        url = "postgresql://ekklesia_backup:test%40password@127.0.0.1/pnyx_test_roles"
        records, result = self.backup(url)
        for record in records:
            self.assertEqual(record["PGDATABASE"], url)
            self.assertNotIn(url, " ".join(record["args"]))
            self.assertNotIn("-U", record["args"])
        self.assertNotIn(url, result.stdout + result.stderr)

    def test_backup_without_new_url_keeps_legacy_credentials(self):
        records, _ = self.backup("")
        for record in records:
            self.assertEqual(record["PGDATABASE"], "pnyx_test_legacy")
            self.assertEqual(record["PGUSER"], "legacy")


if __name__ == "__main__":
    unittest.main()
