"""No-network tests for secret delivery and backup URL compatibility."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
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
       'PGHOST':os.getenv('PGHOST'), 'PGPORT':os.getenv('PGPORT'),
       'PGPASSWORD':os.getenv('PGPASSWORD'), 'PGSSLMODE':os.getenv('PGSSLMODE'),
       'BACKUP_DATABASE_URL':os.getenv('BACKUP_DATABASE_URL'),
       'password':os.getenv('EKKLESIA_API_PASSWORD')})+'\\n')
if os.getenv('FAIL_DUMP') and 'pg_dump' in sys.argv:
    print('connection failed for database ' + os.environ['PGDATABASE'], file=sys.stderr)
    sys.exit(1)
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

    def backup(self, url, *, expect_success=True, **extra_env):
        script = self.directory / "backup-offsite.sh"
        script.write_text((ROOT / "scripts/backup-offsite.sh").read_text().replace(
            'LOCAL_BACKUP_DIR="/opt/backups/ekklesia"', f'LOCAL_BACKUP_DIR="{self.directory}/backups"'))
        library = self.directory / "lib"
        library.mkdir()
        (library / "backup-encrypt.sh").write_text((ROOT / "scripts/lib/backup-encrypt.sh").read_text())
        (library / "backup-db.py").write_text((ROOT / "scripts/lib/backup-db.py").read_text())
        env = {**self.env, "BACKUP_DATABASE_URL": url, "POSTGRES_USER": "legacy", "POSTGRES_DB": "pnyx_test_legacy",
               "STORAGE_BOX_USER": "fixture", "STORAGE_BOX_HOST": "fixture.invalid", **extra_env}
        result = subprocess.run(["bash", "-x", str(script)], env=env, capture_output=True, text=True)
        if expect_success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        records = [r for r in self.records() if "pg_dump" in r["args"] or "psql" in r["args"]] if self.capture.exists() else []
        if expect_success:
            self.assertEqual(len(records), 2)
        return records, result

    def test_backup_url_applies_to_both_dump_and_alembic_capture(self):
        url = "postgresql://ekklesia_backup:test%40password@127.0.0.1:5544/pnyx_test_roles?sslmode=require"
        records, result = self.backup(url, PGPASSWORD="bootstrap-secret")
        for record in records:
            self.assertEqual(record["PGDATABASE"], "pnyx_test_roles")
            self.assertEqual(record["PGUSER"], "ekklesia_backup")
            self.assertEqual(record["PGHOST"], "127.0.0.1")
            self.assertEqual(record["PGPORT"], "5544")
            self.assertEqual(record["PGPASSWORD"], "test@password")
            self.assertEqual(record["PGSSLMODE"], "require")
            self.assertIsNone(record["BACKUP_DATABASE_URL"])
            self.assertNotIn(url, " ".join(record["args"]))
            self.assertNotIn("test@password", " ".join(record["args"]) + result.stdout + result.stderr)
            self.assertNotIn("-U", record["args"])
        self.assertTrue(all(r["BACKUP_DATABASE_URL"] is None for r in self.records()))
        self.assertNotIn(url, result.stdout + result.stderr)

    def test_backup_failure_does_not_log_uri_or_password(self):
        url = "postgresql://ekklesia_backup:secret%40password@127.0.0.1/missing_db"
        _, result = self.backup(url, expect_success=False, FAIL_DUMP="1")
        self.assertIn("missing_db", result.stderr)
        self.assertNotIn(url, result.stdout + result.stderr)
        self.assertNotIn("secret@password", result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("pg_dump"), "libpq client not installed")
    def test_real_libpq_error_uses_components_without_disclosing_password(self):
        # Exercise real libpq against a missing Unix socket, with no network.
        (self.bin / "docker").write_text('#!/bin/bash\nshift\nwhile [[ "$1" == "--env" ]]; do shift 2; done\nshift\nexec "$@"\n')
        url = "postgresql://ekklesia_backup:secret%40password@%2Fprivate%2Ftmp%2Ft9142-no-such-socket:5544/missing_db"
        _, result = self.backup(url, expect_success=False)
        self.assertIn("/private/tmp/t9142-no-such-socket/.s.PGSQL.5544", result.stderr)
        self.assertNotIn(url, result.stdout + result.stderr)
        self.assertNotIn("secret@password", result.stdout + result.stderr)

    def test_malformed_backup_url_fails_closed_without_logging_it(self):
        url = "postgresql://ekklesia_backup:secret@127.0.0.1:secret/db"
        records, result = self.backup(url, expect_success=False)
        self.assertEqual(records, [])
        self.assertNotIn(url, result.stdout + result.stderr)
        self.assertNotIn("secret", result.stdout + result.stderr)

    def test_backup_without_new_url_keeps_legacy_credentials(self):
        records, _ = self.backup("")
        for record in records:
            self.assertEqual(record["PGDATABASE"], "pnyx_test_legacy")
            self.assertEqual(record["PGUSER"], "legacy")


class BackupURLParserTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("backup_db", ROOT / "scripts/lib/backup-db.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_ipv6_and_percent_encoded_credentials(self):
        env = self.module.connection_env("postgres://user%40name:p%3Aa%25%27%5C%24@[::1]:5544/db%20name?connect_timeout=5&application_name=backup")
        self.assertEqual({k: env[k] for k in ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGCONNECT_TIMEOUT", "PGAPPNAME")},
                         dict(PGHOST="::1", PGPORT="5544", PGUSER="user@name", PGPASSWORD="p:a%'\\$", PGDATABASE="db name", PGCONNECT_TIMEOUT="5", PGAPPNAME="backup"))

    def test_ambiguous_or_unsafe_urls_are_rejected(self):
        for uri in ("not a uri", "https://user:secret@host/db", "postgresql://user:secret@host/",
                    "postgresql://user:secret@host/db?password=override", "postgresql://user:secret@host/db?host=other",
                    "postgresql://user:secret@host/db?sslmode=require&sslmode=disable",
                    "postgresql://user:secret@host/db#fragment", "postgresql://user:secret@host/db%zz",
                    "postgresql://user:secret@host/postgresql%3A%2F%2Fuser%3Asecret%40host%2Fdb"):
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                self.module.connection_env(uri)


if __name__ == "__main__":
    unittest.main()
