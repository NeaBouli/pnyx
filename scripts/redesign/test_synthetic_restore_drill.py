"""Offline tests for scripts/synthetic_restore_drill.py (no Docker/DB)."""
import importlib.util
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

        with mock.patch.object(d, "expected_heads", return_value=HEADS), \
             mock.patch.dict(d.os.environ, {}, clear=False), \
             mock.patch.object(d.os, "umask"):
            d.os.environ.pop("DOCKER_HOST", None)
            with self.assertRaises(d.subprocess.CalledProcessError):
                d.drill(run=run, run_env=lambda *a, **k: "y801a2b3c4d5")
        flat = [" ".join(c) for c in calls]
        for word in ("docker rm", "prune", "docker stop", "--clean", "DROP"):
            self.assertFalse(any(word in c for c in flat), word)


if __name__ == "__main__":
    unittest.main()
