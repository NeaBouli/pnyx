"""Targeted real-SQL checks without an async driver or any network access.

Set PNYX_TEST_POSTGRES_SOCKET and PGDATABASE=pnyx_test_* for a disposable
socket-only cluster, with psql >= 15 on PATH. No cluster roles may preexist.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ROLES = ("api", "migrator", "monitor", "dashboard", "backup")


class Rows:
    def __init__(self, output):
        self.rows = [tuple(row.split("\t")) for row in output.splitlines()]

    def all(self):
        return self.rows

    def scalar(self):
        value = self.rows[0][0] if self.rows else None
        return {"t": True, "f": False}.get(value, value)

    scalar_one = scalar


class PsqlOperations:
    """Execute the revision's operations against PostgreSQL through psql."""
    def __init__(self, env):
        from sqlalchemy.dialects.postgresql import dialect
        self.env = env
        self.dialect = dialect()

    def get_bind(self):
        return self

    def execute(self, sql, params=None):
        # This revision binds role/view names and a list of creator names.
        def literal(value):
            if isinstance(value, list):
                return "ARRAY[" + ",".join(literal(v) for v in value) + "]::text[]"
            return "'" + value.replace("'", "''") + "'"
        sql = str(sql)
        for key, value in (params or {}).items():
            sql = sql.replace(":" + key, literal(value))
        result = subprocess.run(["psql", "-XAt", "-F", "\t", "-v", "ON_ERROR_STOP=1"],
                                input=sql, env=self.env, capture_output=True, text=True, check=True)
        return Rows(result.stdout)


@unittest.skipUnless(os.getenv("PNYX_TEST_POSTGRES_SOCKET"), "isolated socket-only PostgreSQL not configured")
class DatabaseRoleSQLTest(unittest.TestCase):
    def setUp(self):
        self.env = {**os.environ, "PGHOST": os.environ["PNYX_TEST_POSTGRES_SOCKET"]}
        self.assertTrue(Path(self.env["PGHOST"]).is_absolute())
        self.assertTrue(self.env.get("PGDATABASE", "").startswith("pnyx_test_"))
        self.admin = PsqlOperations(self.env)
        self.assertEqual(self.admin.execute("SELECT rolname FROM pg_roles WHERE rolname LIKE 'ekklesia_%'").all(), [])
        self.addCleanup(self.cleanup_database)
        self.admin.execute("""
            DROP SCHEMA public CASCADE; CREATE SCHEMA public;
            CREATE TABLE parliament_bills (
                id text PRIMARY KEY, title_el text, status text, source text,
                admin_hidden boolean, results_visibility text, created_at timestamp,
                updated_at timestamp, parliament_vote_date timestamp, submitted_date timestamp,
                status_changed_at timestamp, arweave_tx_id text, party_votes_parliament jsonb,
                governance_level text, forum_topic_id text, summary_short_el text, summary_long_el text);
            CREATE TABLE bill_status_logs (bill_id text, from_status text, to_status text, changed_at timestamp);
            CREATE TABLE citizen_votes (id serial, bill_id text, vote text, created_at timestamp);
            CREATE TABLE zk_merkle_roots (vote_scope_id varchar(128), merkle_root text, group_size integer, status text);
            CREATE TABLE zk_vote_receipts (id serial, vote_scope_id varchar(128), merkle_root text,
                vote_commitment text, arweave_pending boolean, created_at timestamptz);
            CREATE TABLE alembic_version (version_num text);
        """)
        sys.path.insert(0, str(ROOT / "apps/api"))
        self.addCleanup(sys.path.remove, str(ROOT / "apps/api"))
        spec = importlib.util.spec_from_file_location("roles_revision", ROOT / "apps/api/alembic/versions/z901a2b3c4d5_separate_database_roles.py")
        self.revision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.revision)

    def cleanup_database(self):
        self.admin.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        for role in (*ROLES, "monitor_owner"):
            if self.admin.execute(f"SELECT EXISTS(SELECT FROM pg_roles WHERE rolname='ekklesia_{role}')").scalar():
                self.admin.execute(f"DROP OWNED BY ekklesia_{role}; DROP ROLE ekklesia_{role}")
        self.admin.execute("ALTER DEFAULT PRIVILEGES REVOKE ALL ON TABLES FROM PUBLIC; ALTER DEFAULT PRIVILEGES REVOKE ALL ON SEQUENCES FROM PUBLIC")

    def bootstrap(self):
        env = {**self.env, **{f"EKKLESIA_{role.upper()}_PASSWORD": "test-only-secret" for role in ROLES}}
        subprocess.run([str(ROOT / "scripts/ops/db-roles.sh")], env=env, capture_output=True, text=True, check=True)

    def as_role(self, role):
        return PsqlOperations({**self.env, "PGUSER": f"ekklesia_{role}", "PGPASSWORD": "test-only-secret"})

    def upgrade(self, k):
        from unittest.mock import patch
        self.revision.op = self.as_role("migrator")
        with patch.dict(os.environ, PUBLIC_RESULTS_MIN_COUNT=str(k)):
            self.revision.upgrade()

    def test_global_defaults_for_legacy_and_migrator_are_removed(self):
        self.admin.execute("ALTER DEFAULT PRIVILEGES GRANT ALL ON TABLES TO PUBLIC; ALTER DEFAULT PRIVILEGES GRANT ALL ON SEQUENCES TO PUBLIC")
        self.bootstrap()
        grantees = "PUBLIC, " + ", ".join("ekklesia_" + role for role in ("api", "monitor", "dashboard", "backup"))
        self.admin.execute("CREATE ROLE t9142_old_creator")
        self.addCleanup(self.admin.execute, "DROP OWNED BY t9142_old_creator; DROP ROLE t9142_old_creator")
        self.admin.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE t9142_old_creator GRANT ALL ON TABLES TO {grantees}; ALTER DEFAULT PRIVILEGES FOR ROLE t9142_old_creator GRANT ALL ON SEQUENCES TO {grantees}")
        for creator in (self.env["PGUSER"], "ekklesia_migrator"):
            quoted = self.admin.dialect.identifier_preparer.quote(creator)
            self.admin.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE {quoted} GRANT ALL ON TABLES TO {grantees}; ALTER DEFAULT PRIVILEGES FOR ROLE {quoted} GRANT ALL ON SEQUENCES TO {grantees}")
        # The migrator must reject another creator's newly introduced defaults.
        with self.assertRaisesRegex(RuntimeError, "Unsafe global default privileges"):
            self.upgrade(10)
        self.bootstrap()
        self.assertEqual(self.admin.execute("""
            SELECT FROM pg_default_acl d CROSS JOIN LATERAL aclexplode(d.defaclacl) acl
            LEFT JOIN pg_roles grantee ON grantee.oid=acl.grantee
            WHERE d.defaclnamespace=0 AND d.defaclobjtype IN ('r','S')
              AND (acl.grantee=0 OR grantee.rolname IN
                ('ekklesia_api','ekklesia_monitor','ekklesia_dashboard','ekklesia_backup'))
        """).all(), [])
        # Reintroduce only migrator defaults to exercise migration reconciliation.
        self.as_role("migrator").execute(f"ALTER DEFAULT PRIVILEGES GRANT ALL ON TABLES TO {grantees}; ALTER DEFAULT PRIVILEGES GRANT ALL ON SEQUENCES TO {grantees}")
        self.upgrade(10)
        self.upgrade(10)
        self.as_role("migrator").execute("CREATE TABLE public.future_private(id serial); CREATE VIEW public.future_report AS SELECT * FROM public.future_private")
        self.admin.execute("CREATE TABLE public.future_legacy(id serial)")
        for role in ("monitor", "dashboard"):
            reader = self.as_role(role)
            for obj in ("future_private", "future_report", "future_private_id_seq", "future_legacy", "future_legacy_id_seq"):
                with self.subTest(role=role, obj=obj), self.assertRaises(subprocess.CalledProcessError):
                    reader.execute(f"SELECT * FROM public.{obj}")
        for role in ("api", "backup"):
            self.as_role(role).execute("SELECT * FROM public.future_private")
            with self.assertRaises(subprocess.CalledProcessError):
                self.as_role(role).execute("SELECT * FROM public.future_legacy")
        with self.assertRaises(subprocess.CalledProcessError):
            self.as_role("api").execute("TRUNCATE public.future_private")
        for sql in ("INSERT INTO public.future_private DEFAULT VALUES", "SELECT nextval('public.future_private_id_seq')"):
            with self.assertRaises(subprocess.CalledProcessError):
                self.as_role("backup").execute(sql)
        self.revision.downgrade()
        self.upgrade(10)

    def test_zk_release_rule_and_all_partition_complements(self):
        # Reconciliation must preserve the original deployed view column types.
        self.admin.execute("""
            CREATE VIEW public.monitor_zk_pending AS
            SELECT vote_scope_id, 100::integer AS group_size, 0::numeric AS pending_hours,
                   TRUE AS parliament_eligible, COUNT(*) AS receipt_count
            FROM public.zk_vote_receipts GROUP BY vote_scope_id
        """)
        self.bootstrap()
        self.upgrade(10)
        self.admin.execute("""
            INSERT INTO parliament_bills(id,status,source,results_visibility) VALUES
                ('safe','ACTIVE','PARLIAMENT','ALWAYS');
            INSERT INTO zk_merkle_roots VALUES ('bill:safe','root',100,'OPEN');
            INSERT INTO zk_vote_receipts(vote_scope_id,merkle_root,vote_commitment,arweave_pending,created_at)
                SELECT 'bill:safe','root',choice,TRUE,DATE_TRUNC('day',NOW())-INTERVAL '2 days'
                FROM unnest(ARRAY['YES','NO','ABSTAIN','UNKNOWN']) choice CROSS JOIN generate_series(1,10);
        """)
        reader = self.as_role("monitor")
        query = "SELECT receipt_count FROM public.monitor_zk_pending WHERE vote_scope_id='bill:safe'"
        self.assertEqual(reader.execute(query).scalar(), "40")
        self.assertEqual(reader.execute("SELECT receipt_count FROM public.monitor_zk_pending_aggregate()").scalar(), "40")
        self.admin.execute("""
            INSERT INTO citizen_votes(bill_id,vote,created_at)
                SELECT 'safe',choice,DATE_TRUNC('day',NOW() AT TIME ZONE 'UTC')-INTERVAL '2 days'
                FROM unnest(ARRAY['YES','NO','ABSTAIN','UNKNOWN']) choice CROSS JOIN generate_series(1,10)
        """)
        self.assertEqual(reader.execute(query).scalar(), "40")
        self.upgrade(25)
        self.assertEqual(reader.execute(query).all(), [])
        self.assertEqual(reader.execute("SELECT * FROM public.monitor_zk_pending_aggregate()").all(), [])
        self.upgrade(10)
        # A reader-controlled setting cannot weaken the literal database rule.
        self.assertEqual(reader.execute("SET app.public_results_min_count='0'; " + query).all()[-1], ("40",))
        perturbations = (
            "DELETE FROM zk_vote_receipts WHERE id=(SELECT MIN(id) FROM zk_vote_receipts)",
            "DELETE FROM citizen_votes WHERE id=(SELECT MIN(id) FROM citizen_votes)",
            "UPDATE zk_vote_receipts SET vote_commitment='YES' WHERE vote_commitment='UNKNOWN'",
            "INSERT INTO citizen_votes(bill_id,vote,created_at) VALUES ('safe','YES',NOW())",
            "UPDATE zk_vote_receipts SET created_at=created_at+INTERVAL '1 hour' WHERE id=(SELECT MIN(id) FROM zk_vote_receipts)",
            "UPDATE zk_vote_receipts SET arweave_pending=FALSE WHERE id=(SELECT MIN(id) FROM zk_vote_receipts)",
            "INSERT INTO zk_merkle_roots VALUES ('bill:safe','other',101,'OPEN'); UPDATE zk_vote_receipts SET merkle_root='other' WHERE id=(SELECT MIN(id) FROM zk_vote_receipts)",
            "UPDATE zk_merkle_roots SET group_size=1",
            "UPDATE zk_vote_receipts SET merkle_root='missing' WHERE id=(SELECT MIN(id) FROM zk_vote_receipts)",
            "UPDATE zk_vote_receipts SET vote_commitment='invalid' WHERE id=(SELECT MIN(id) FROM zk_vote_receipts)",
            "UPDATE parliament_bills SET results_visibility='HIDDEN'",
            "UPDATE parliament_bills SET admin_hidden=TRUE",
            "UPDATE parliament_bills SET source='ZK_CANARY'",
        )
        for sql in perturbations:
            with self.subTest(sql=sql):
                self.admin.execute("BEGIN; " + sql + "; "
                                   "SET LOCAL ROLE ekklesia_monitor; "
                                   "DO $$ BEGIN IF EXISTS(SELECT FROM public.monitor_zk_pending) THEN RAISE EXCEPTION 'unsafe release'; END IF; END $$; ROLLBACK")
        # Disabled suppression retains the documented flag-off count behavior.
        self.admin.execute("DELETE FROM zk_vote_receipts WHERE id<>1")
        self.upgrade(0)
        self.assertEqual(reader.execute(query).scalar(), "1")

    def test_explain_and_function_privilege_boundary(self):
        self.bootstrap()
        self.bootstrap()  # Reconcile the sole allowed migrator membership.
        self.upgrade(10)
        self.admin.execute("""
            INSERT INTO parliament_bills(id,status,source,results_visibility)
                VALUES ('small','ACTIVE','PARLIAMENT','ALWAYS');
            INSERT INTO zk_merkle_roots VALUES ('bill:small','root',100,'OPEN');
            INSERT INTO zk_vote_receipts(vote_scope_id,merkle_root,vote_commitment,arweave_pending,created_at)
                VALUES ('bill:small','root','YES',TRUE,NOW()-INTERVAL '2 days');
        """)
        reader = self.as_role("monitor")
        self.assertEqual(reader.execute("SELECT * FROM public.monitor_zk_pending_aggregate()").all(), [])
        for view in self.revision.VIEWS:
            with self.subTest(view=view):
                output = reader.execute(f"EXPLAIN (ANALYZE, VERBOSE, FORMAT JSON) SELECT * FROM public.{view}")
                plan = json.loads("\n".join(row[0] for row in output.all()))[0]["Plan"]
                # No underlying plan, relation name, estimates or Actual Rows
                # from a source table may be visible, even for a suppressed cell.
                nodes = [plan]
                for node in nodes:
                    nodes.extend(node.get("Plans", []))
                self.assertIn("Function Scan", [node["Node Type"] for node in nodes])
                for node in nodes:
                    self.assertIn(node["Node Type"], ("Function Scan", "Subquery Scan", "Result"))
                    self.assertNotIn("Relation Name", node)
                if view == "monitor_zk_pending":
                    self.assertEqual(plan["Actual Rows"], 0)
                function = f"public.{view}_aggregate()"
                metadata = self.admin.execute(f"""
                    SELECT r.rolname, p.prosecdef, array_to_string(p.proconfig, ';')
                    FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner
                    WHERE p.oid='{function}'::regprocedure
                """).all()
                self.assertEqual(metadata, [("ekklesia_monitor_owner", "t", "search_path=pg_catalog, public")])
                self.assertEqual(self.admin.execute(f"""
                    SELECT FROM pg_proc p CROSS JOIN LATERAL aclexplode(p.proacl) acl
                    WHERE p.oid='{function}'::regprocedure AND acl.grantee=0
                """).all(), [])
                for role in ("api", "dashboard", "backup"):
                    self.assertFalse(self.admin.execute(
                        f"SELECT has_function_privilege('ekklesia_{role}', '{function}', 'EXECUTE')").scalar())
                for role in ("api", "dashboard"):
                    with self.assertRaises(subprocess.CalledProcessError):
                        self.as_role(role).execute(f"SELECT * FROM {function}")
        for role in ("monitor", "dashboard"):
            for table in self.revision.AGGREGATE_SOURCES:
                with self.subTest(role=role, table=table), self.assertRaises(subprocess.CalledProcessError):
                    self.as_role(role).execute(f"EXPLAIN (ANALYZE, FORMAT JSON) SELECT * FROM public.{table}")
            with self.assertRaises(subprocess.CalledProcessError):
                self.as_role(role).execute("SET ROLE ekklesia_monitor_owner")
        self.assertFalse(self.admin.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname='ekklesia_monitor_owner'").scalar())
        self.assertFalse(self.admin.execute("SELECT has_schema_privilege('ekklesia_monitor_owner','public','CREATE')").scalar())

    def test_function_search_path_cannot_be_hijacked(self):
        self.bootstrap()
        self.upgrade(10)
        self.admin.execute("""
            INSERT INTO parliament_bills(id,status,source,results_visibility)
                VALUES ('safe','ACTIVE','PARLIAMENT','ALWAYS');
            INSERT INTO zk_merkle_roots VALUES ('bill:safe','root',100,'OPEN');
            INSERT INTO zk_vote_receipts(vote_scope_id,merkle_root,vote_commitment,arweave_pending,created_at)
                SELECT 'bill:safe','root',choice,TRUE,DATE_TRUNC('day',NOW())-INTERVAL '2 days'
                FROM unnest(ARRAY['YES','NO','ABSTAIN','UNKNOWN']) choice CROSS JOIN generate_series(1,10);
        """)
        # Give the attacker an otherwise unavailable schema and TEMP privilege
        # in this isolated fixture, so the test exercises real shadow objects.
        database = self.admin.dialect.identifier_preparer.quote(self.env["PGDATABASE"])
        self.admin.execute("""
            CREATE SCHEMA attacker AUTHORIZATION ekklesia_monitor;
            GRANT TEMP ON DATABASE """ + database + " TO ekklesia_monitor")
        self.addCleanup(self.admin.execute, "DROP SCHEMA IF EXISTS attacker CASCADE")
        # One connection is necessary for temporary objects and session GUCs.
        self.as_role("monitor").execute("""
            CREATE FUNCTION attacker.count() RETURNS bigint LANGUAGE sql AS 'SELECT 999::bigint';
            CREATE FUNCTION attacker.now() RETURNS timestamptz LANGUAGE plpgsql AS
                $$ BEGIN RAISE EXCEPTION 'hijacked now'; END $$;
            CREATE FUNCTION attacker.date_trunc(text, timestamptz) RETURNS timestamptz LANGUAGE plpgsql AS
                $$ BEGIN RAISE EXCEPTION 'hijacked date_trunc'; END $$;
            CREATE TABLE attacker.zk_vote_receipts (private_value text);
            CREATE TEMP TABLE zk_merkle_roots (status text);
            INSERT INTO zk_merkle_roots VALUES ('INVALID');
            SET search_path = attacker, pg_temp, public, pg_catalog;
            DO $$ BEGIN
                IF (SELECT invalid_roots FROM public.monitor_zk_health_aggregate()) <> 0
                   OR (SELECT receipt_count FROM public.monitor_zk_pending_aggregate()) IS DISTINCT FROM 40::bigint THEN
                    RAISE EXCEPTION 'shadow objects changed aggregate output';
                END IF;
                PERFORM * FROM public.monitor_bill_health_aggregate();
            END $$;
        """)

    def test_backup_components_work_with_real_libpq(self):
        self.bootstrap()
        self.upgrade(10)
        from urllib.parse import quote
        uri = f"postgresql://ekklesia_backup:test-only-secret@{quote(self.env['PGHOST'], safe='')}:{self.env.get('PGPORT', '5432')}/{self.env['PGDATABASE']}"
        with tempfile.TemporaryDirectory() as directory:
            docker = Path(directory) / "docker"
            docker.write_text('#!/bin/bash\nshift\nwhile [[ "$1" == "--env" ]]; do shift 2; done\nshift\nexec "$@"\n')
            docker.chmod(0o755)
            env = {**self.env, "PATH": directory + os.pathsep + self.env["PATH"]}
            helper = str(ROOT / "scripts/lib/backup-db.py")
            for args in (("psql", "-XAt", "-c", "SELECT current_user || ':' || current_database()"), ("pg_dump", "--no-password", "-Fc")):
                result = subprocess.run([sys.executable, helper, "fixture", *args], input=uri.encode(), env=env, capture_output=True, check=True)
                if args[0] == "psql":
                    self.assertEqual(result.stdout.strip(), f"ekklesia_backup:{self.env['PGDATABASE']}".encode())
                else:
                    self.assertTrue(result.stdout.startswith(b"PGDMP"))
                self.assertNotIn(uri.encode(), result.stderr)


if __name__ == "__main__":
    unittest.main()
