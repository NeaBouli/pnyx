"""Offline tests for scripts/synthetic_restore_drill.py (no Docker/DB)."""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "drill", Path(__file__).resolve().parents[1] / "synthetic_restore_drill.py")
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)
HEADS = ["y801a2b3c4d5"]


class DrillTests(unittest.TestCase):
    def test_default_is_offline_plan(self):
        with mock.patch.object(d.subprocess, "run") as run:
            self.assertEqual(d.main([]), 0)
            run.assert_not_called()

    def test_rejects_dsn_and_dump_args(self):
        for arg in (["--dsn", "x"], ["--dump", "x"], ["--source", "x"]):
            with self.assertRaises(SystemExit):
                d.main(arg)

    def test_remote_docker_refused(self):
        with self.assertRaises(d.DrillError):
            d.check_local_docker({"DOCKER_HOST": "tcp://10.0.0.1:2375"}, lambda c: "")
        with self.assertRaises(d.DrillError):
            d.check_local_docker({}, lambda c: "ssh://u@h")
        with self.assertRaises(d.DrillError):
            d.check_local_docker({"DOCKER_HOST": "unix:///var/run/docker.sock", "DOCKER_CONTEXT": "remote"}, lambda c: "")
        d.check_local_docker({}, lambda c: "unix:///var/run/docker.sock")

    def test_binding_and_major(self):
        self.assertEqual(d.check_binding("127.0.0.1:55001\n"), 55001)
        with self.assertRaises(d.DrillError):
            d.check_binding("0.0.0.0:55001")
        d.check_major("15.8 (Debian)")
        with self.assertRaises(d.DrillError):
            d.check_major("16.2")

    def test_malformed_archive(self):
        with tempfile.NamedTemporaryFile() as fh:
            fh.write(b"-- plain sql"); fh.flush()
            with self.assertRaises(d.DrillError):
                d.check_archive(Path(fh.name))

    def test_count_and_head_mismatch(self):
        ok = "50,2550,7,y801a2b3c4d5"
        d.compare(ok, ok, HEADS)
        with self.assertRaises(d.DrillError):
            d.compare(ok, "49,2550,7,y801a2b3c4d5", HEADS)
        with self.assertRaises(d.DrillError):
            d.compare("50,2550,7,aaaaaaaaaaaa", "50,2550,7,aaaaaaaaaaaa", HEADS)
        d.check_current("y801a2b3c4d5 (head)", HEADS)
        with self.assertRaises(d.DrillError):
            d.check_current("", HEADS)

    def test_containers_new_labelled_no_pull_loopback(self):
        src = d.docker_run("drill-src-x", "pw", True)
        tgt = d.docker_run("drill-tgt-x", "pw", False)
        for cmd in (src, tgt):
            self.assertIn("--pull=never", cmd)
            self.assertIn(d.LABEL, cmd)
            self.assertNotIn("--rm", cmd)
            self.assertEqual(cmd[-1], d.IMAGE_ID)
        self.assertIn("none", src)
        self.assertIn("127.0.0.1::5432", tgt)

    def test_nonzero_restore_fails_closed_without_delete(self):
        calls = []

        def run(cmd):
            calls.append(list(cmd))
            if cmd[:2] == ["docker", "--host"]:
                cmd = ["docker", *cmd[3:]]
            if "pg_restore" in cmd and "--exit-on-error" in cmd:
                raise d.subprocess.CalledProcessError(1, cmd)
            if cmd[:2] == ["docker", "context"]:
                return "unix:///var/run/docker.sock"
            if cmd[:2] == ["docker", "run"]:
                return "c" * 64
            if cmd[:2] == ["docker", "port"]:
                return "127.0.0.1:55001"
            if "SHOW server_version;" in cmd:
                return "15.8"
            if "-f" in cmd:
                return ""
            if cmd[:2] == ["docker", "cp"] and cmd[-1].endswith(".dump") and ":" in cmd[2]:
                Path(cmd[-1]).write_bytes(b"PGDMP\x01")
            return "50,2550,7,y801a2b3c4d5"

        real_mkdtemp = tempfile.mkdtemp
        with tempfile.TemporaryDirectory() as root, \
             mock.patch.object(d.tempfile, "mkdtemp",
                               side_effect=lambda prefix="", dir=None: real_mkdtemp(prefix=prefix, dir=dir or root)), \
             mock.patch.object(d, "expected_heads", return_value=HEADS), \
             mock.patch.dict(d.os.environ, {}, clear=True), \
             mock.patch.object(d.os, "umask"):
            d.os.environ.pop("DOCKER_HOST", None)
            with self.assertRaises(d.subprocess.CalledProcessError):
                d.drill(run=run, run_env=lambda *a, **k: "y801a2b3c4d5")
        flat = [" ".join(c) for c in calls]
        self.assertTrue(any(c[:3] == ["docker", "--host", "unix:///var/run/docker.sock"] for c in calls))
        for word in ("docker rm", "prune", "docker stop", "--clean", "DROP"):
            self.assertFalse(any(word in c for c in flat), word)


    def _fake_docker(self, calls):
        def run(cmd):
            calls.append(("run", list(cmd)))
            if cmd[:2] == ["docker", "--host"]:
                cmd = ["docker", *cmd[3:]]
            if cmd[:2] == ["docker", "context"]:
                return "unix:///var/run/docker.sock"
            if cmd[:2] == ["docker", "run"]:
                return "c" * 64
            if cmd[:2] == ["docker", "port"]:
                return "127.0.0.1:55001"
            if "SHOW server_version;" in cmd:
                return "15.8"
            if cmd[:2] == ["docker", "cp"] and cmd[-1].endswith(".dump") and ":" in cmd[2]:
                Path(cmd[-1]).write_bytes(b"PGDMP\x01")
            return "50,2550,7,y801a2b3c4d5"
        return run

    def test_preflight_child_is_sanitized_import_only(self):
        seen = []
        with mock.patch.dict(d.os.environ, {"PATH": "/usr/bin", "DATABASE_URL": "x",
                                            "SERVER_SALT": "s"}, clear=True):
            d.preflight_imports(lambda cmd, **kw: seen.append((cmd, kw)) or "")
        (cmd, kw), = seen
        self.assertEqual(cmd[:2], [d.sys.executable, "-c"])
        self.assertEqual(kw["env"], {"PATH": "/usr/bin"})
        self.assertEqual(kw["cwd"], d.os.sep)
        code = cmd[2]
        compile(code, "<preflight>", "exec")  # syntax only, nothing imported
        for need in ("async_sessionmaker", "DeclarativeBase", "import asyncpg", "AliasChoices",
                     "BaseSettings", "SettingsConfigDict", "from alembic"):
            self.assertIn(need, code)
        for bad in ("from config", "from database", "from models", "import config",
                    "env.py", "settings.", ".env", "connect", "sys.path"):
            self.assertNotIn(bad, code)

    def test_preflight_failure_creates_nothing(self):
        errors = (d.subprocess.CalledProcessError(1, "py", stderr="Traceback ImportError PW=hunter2"),
                  d.subprocess.TimeoutExpired("py", 120), FileNotFoundError("python"))
        for err in errors:
            calls = []

            def run_env(cmd, **kw):
                calls.append(("run_env", list(cmd)))
                raise err

            with mock.patch.object(d, "expected_heads") as heads, \
                 mock.patch.object(d.tempfile, "mkdtemp") as mkdtemp, \
                 mock.patch.object(d.os, "umask"):
                with self.assertRaises(d.DrillError) as ctx:
                    d.drill(run=self._fake_docker(calls), run_env=run_env)
            self.assertEqual(str(ctx.exception), d.DEPENDENCY_FAIL)
            self.assertEqual([c[0] for c in calls], ["run_env"])
            mkdtemp.assert_not_called()
            heads.assert_not_called()

    def test_cli_dependency_failure_fixed_message_exit1(self):
        err = d.subprocess.CalledProcessError(1, "py", stderr="Traceback\nImportError: PW=hunter2")
        out = io.StringIO()
        with mock.patch.object(d.subprocess, "run", side_effect=err) as run, \
             mock.patch.object(d.tempfile, "mkdtemp") as mkdtemp, \
             mock.patch.object(d.os, "umask"), contextlib.redirect_stderr(out):
            self.assertEqual(d.main(["--run"]), 1)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][:2], [d.sys.executable, "-c"])
        mkdtemp.assert_not_called()
        self.assertIn(d.DEPENDENCY_FAIL, out.getvalue())
        for leak in ("Traceback", "hunter2", "ImportError"):
            self.assertNotIn(leak, out.getvalue())

    def test_compatible_preflight_keeps_flow_and_alembic_current(self):
        calls = []

        def run_env(cmd, **kw):
            calls.append(("run_env", cmd[2]))
            return "" if cmd[2] == d.PREFLIGHT_CODE else "y801a2b3c4d5 (head)"

        with tempfile.TemporaryDirectory() as root:
            real_mkdtemp = tempfile.mkdtemp

            def mkdtemp(prefix="", dir=None):
                calls.append(("mkdtemp", prefix))
                return real_mkdtemp(prefix=prefix, dir=dir or root)

            with mock.patch.object(d, "expected_heads", side_effect=lambda: calls.append(("heads",)) or HEADS), \
                 mock.patch.object(d.tempfile, "mkdtemp", side_effect=mkdtemp), \
                 mock.patch.dict(d.os.environ, {}, clear=True), \
                 mock.patch.object(d.os, "umask"):
                receipt = d.drill(run=self._fake_docker(calls), run_env=run_env)
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(calls[0], ("run_env", d.PREFLIGHT_CODE))
        self.assertEqual(calls[1], ("heads",))
        self.assertEqual(calls[2][0], "run")
        self.assertEqual(calls[-2][0], "run_env")
        self.assertIn("command.current", calls[-2][1])
        self.assertEqual(sum(c[0] == "run_env" for c in calls), 2)


class FailureReceiptTests(unittest.TestCase):
    SECRET = "pw-zz9"

    def _run(self, fail_on, run_out="c" * 64):
        made = []

        def run(cmd):
            if cmd[:2] == ["docker", "--host"]:
                cmd = ["docker", *cmd[3:]]
            if fail_on(cmd, made):
                raise d.subprocess.CalledProcessError(
                    1, cmd, stderr=f"postgresql://u:{self.SECRET}@h/db SELECT 1")
            if cmd[:2] == ["docker", "context"]:
                return "unix:///var/run/docker.sock"
            if cmd[:2] == ["docker", "run"]:
                made.append(1)
                return run_out if len(made) == 1 else "d" * 64
            if cmd[:2] == ["docker", "port"]:
                return "127.0.0.1:55001"
            if "SHOW server_version;" in cmd:
                return "15.8"
            if cmd[:2] == ["docker", "cp"] and cmd[-1].endswith(".dump") and ":" in cmd[2]:
                Path(cmd[-1]).write_bytes(b"PGDMP\x01")
            return "50,2550,7,y801a2b3c4d5"
        return run

    def _cli(self, run, run_env=lambda *a, **k: "y801a2b3c4d5"):
        real_mkdtemp = tempfile.mkdtemp
        err, out = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as root, \
             mock.patch.object(d.tempfile, "mkdtemp",
                               side_effect=lambda prefix="", dir=None: real_mkdtemp(prefix=prefix, dir=dir or root)), \
             mock.patch.object(d, "expected_heads", return_value=HEADS), \
             mock.patch.object(d.secrets, "token_hex", return_value=self.SECRET), \
             mock.patch.dict(d.os.environ, {}, clear=True), mock.patch.object(d.os, "umask"):
            caught = []
            real_drill = d.drill

            def wrapped():
                try:
                    return real_drill(run=run, run_env=run_env)
                except BaseException as exc:
                    caught.append(exc)
                    raise
            with mock.patch.object(d, "drill", wrapped), contextlib.redirect_stderr(err), \
                 contextlib.redirect_stdout(out):
                code = d.main(["--run"])
        return code, err.getvalue(), out.getvalue(), caught

    def _assert_clean(self, text):
        for bad in (self.SECRET, "postgresql://", "SELECT", "POSTGRES_PASSWORD", "docker run"):
            self.assertNotIn(bad, text)

    def test_first_create_failure_uncertain_no_ids(self):
        code, err, out, (exc,) = self._cli(self._run(lambda c, m: c[:2] == ["docker", "run"]))
        self.assertEqual(code, 1)
        self.assertIsInstance(exc, d.subprocess.CalledProcessError)
        r = exc.failure_receipt
        self.assertEqual((r["stage"], r["acknowledged_container_ids"], r["creation_uncertain"]),
                         ("create_source", [], True))
        self.assertIn('"workdir"', err)
        self._assert_clean(err + out)

    def test_second_create_failure_keeps_first_id(self):
        code, err, _, (exc,) = self._cli(self._run(lambda c, m: c[:2] == ["docker", "run"] and m))
        self.assertEqual(code, 1)
        r = exc.failure_receipt
        self.assertEqual((r["stage"], r["acknowledged_container_ids"]), ("create_target", ["c" * 64]))
        self.assertTrue(r["creation_uncertain"])
        self._assert_clean(err)

    def test_restore_and_current_failures_list_both_ids(self):
        restore = lambda c, m: "pg_restore" in c and "--exit-on-error" in c
        for kwargs in ({}, {"run_env": lambda *a, **k: "zzz"}):
            fail = restore if not kwargs else (lambda c, m: False)
            code, err, out, (exc,) = self._cli(self._run(fail), **kwargs)
            self.assertEqual(code, 1)
            r = exc.failure_receipt
            self.assertEqual((r["stage"], r["acknowledged_container_ids"]), ("restore", ["c" * 64, "d" * 64]))
            self.assertNotIn("creation_uncertain", r)
            self.assertNotIn("status\": \"ok", err + out)
            self._assert_clean(err + out)
        self.assertIsInstance(exc, d.DrillError)

    def test_count_mismatch_same_exception_identity(self):
        n = []

        def run_env(*a, **k):
            return "y801a2b3c4d5"
        run = self._run(lambda c, m: False)

        def counting(cmd):
            res = run(cmd)
            if res.startswith("50,2550"):
                n.append(1)
                return res if len(n) == 1 else "49,2550,7,y801a2b3c4d5"
            return res
        sentinel = d.DrillError("x")
        with mock.patch.object(d, "compare", side_effect=sentinel):
            code, _, _, (exc,) = self._cli(counting, run_env)
        self.assertEqual(code, 1)
        self.assertIs(exc, sentinel)
        self.assertEqual(exc.failure_receipt["stage"], "restore")

    def test_malformed_create_output_sanitised(self):
        bad = f"Warning {self.SECRET}\n" + "e" * 64
        _, err, _, (exc,) = self._cli(self._run(
            lambda c, m: "pg_restore" in c and "--exit-on-error" in c, run_out=bad))
        r = exc.failure_receipt
        self.assertEqual(r["acknowledged_container_ids"], ["d" * 64])
        self.assertTrue(r["creation_uncertain"])
        self._assert_clean(err)

    def test_preflight_failure_has_no_receipt(self):
        def run_env(*a, **k):
            raise d.subprocess.CalledProcessError(1, a[0], stderr=self.SECRET)
        code, err, _, (exc,) = self._cli(self._run(lambda c, m: False), run_env)
        self.assertEqual(code, 1)
        self.assertFalse(hasattr(exc, "failure_receipt"))
        self.assertIn(d.DEPENDENCY_FAIL, err)
        self._assert_clean(err)

    def test_success_shape_unchanged(self):
        code, err, out, caught = self._cli(self._run(lambda c, m: False))
        self.assertEqual((code, err, caught), (0, "", []))
        r = json.loads(out)
        self.assertEqual(set(r), {"label", "workdir_private", "heads", "created", "status",
                                  "sample", "dump_bytes", "server_version"})
        self.assertEqual(r["created"], ["c" * 64, "d" * 64])



if __name__ == "__main__":
    unittest.main()
