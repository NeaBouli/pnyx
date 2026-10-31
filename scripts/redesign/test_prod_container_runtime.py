"""EKA-13: production image users, cache ownership and immutable image pins.

Like apps/api/tests/test_prod_docker_proxy_boundary.py, parse Compose with
PyYAML so comments, quoting and service boundaries cannot hide policy changes.
No Docker daemon or production configuration is needed.
"""

import json
from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
OLLAMA_IMAGE = (
    "ollama/ollama@sha256:"
    "2038a264392af4d21f7f14e1568e8dd9aa0f2bd0f31d7d9a59a8cca1e9829663"
)
PROXY_IMAGE = (
    "ghcr.io/tecnativa/docker-socket-proxy:v0.4.2@sha256:"
    "1f3a6f303320723d199d2316a3e82b2e2685d86c275d5e3deeaf182573b47476"
)


def runtime_instructions(path):
    """Return instructions after the last FROM, ignoring comments/continuations."""
    source = (ROOT / path).read_text(encoding="utf-8").replace("\\\n", " ")
    instructions = []
    for line in source.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        opcode, value = line.split(None, 1)
        if opcode.upper() == "FROM":
            instructions = []
        instructions.append((opcode.upper(), value))
    return instructions


class ProductionContainerRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = yaml.safe_load(
            (ROOT / "infra/docker/docker-compose.prod.yml").read_text(encoding="utf-8")
        )
        cls.dashboard = runtime_instructions("apps/dashboard/Dockerfile.prod")
        cls.monitor = runtime_instructions("apps/monitor/Dockerfile")

    def test_final_stage_users_are_dedicated_non_root_accounts(self):
        for instructions, account, uid in (
            (self.dashboard, "nextjs", 1001),
            (self.monitor, "monitor", 10001),
        ):
            with self.subTest(account=account):
                users = [value for opcode, value in instructions if opcode == "USER"]
                self.assertTrue(users, "the final stage must explicitly set USER")
                self.assertEqual(users[-1], f"{account}:{account}")
                runs = "\n".join(value for opcode, value in instructions if opcode == "RUN")
                self.assertRegex(runs, rf"(?:addgroup|groupadd)\b[^\n]*?(?:-g|--gid) {uid}\b[^\n]*?\b{account}\b")
                self.assertRegex(runs, rf"(?:adduser|useradd)\b[^\n]*?(?:-u|--uid) {uid}\b[^\n]*?\b{account}\b")

    def test_dashboard_owns_cache_and_keeps_application_files_root_owned(self):
        runs = "\n".join(value for opcode, value in self.dashboard if opcode == "RUN")
        self.assertIn("mkdir -p /app/.next/cache", runs)
        self.assertIn("chown -R nextjs:nextjs /app/.next/cache", runs)
        copies = [value for opcode, value in self.dashboard if opcode == "COPY"]
        self.assertTrue(copies)
        for copy in copies:
            self.assertIn("--chown=0:0", copy)

    def test_runtime_commands_and_dashboard_port_are_preserved(self):
        for instructions, expected in (
            (self.dashboard, ["node", "server.js"]),
            (self.monitor, ["python", "monitor.py"]),
        ):
            commands = [value for opcode, value in instructions if opcode == "CMD"]
            self.assertEqual(json.loads(commands[-1]), expected)
        self.assertIn(("EXPOSE", "3001"), self.dashboard)
        self.assertIn(("ENV", "PYTHONDONTWRITEBYTECODE=1"), self.monitor)

    def test_compose_uses_image_users_without_application_mounts(self):
        for name in ("dashboard", "monitor"):
            with self.subTest(service=name):
                service = self.compose["services"][name]
                self.assertNotIn("user", service)
                self.assertFalse(service.get("volumes"))

    def test_ollama_and_socket_proxy_keep_exact_verified_digests(self):
        services = self.compose["services"]
        self.assertEqual(services["ollama"]["image"], OLLAMA_IMAGE)
        self.assertEqual(services["docker-proxy"]["image"], PROXY_IMAGE)
        self.assertNotIn("user", services["ollama"])
        self.assertEqual(services["ollama"]["volumes"], ["ollama-data:/root/.ollama"])

    def test_no_production_image_uses_latest(self):
        for name, service in self.compose["services"].items():
            if "image" in service:
                with self.subTest(service=name):
                    self.assertIsNone(re.search(r":latest(?:@|$)", service["image"]))


if __name__ == "__main__":
    unittest.main()


class DashboardBuildContextTest(unittest.TestCase):
    def test_dashboard_context_excludes_local_env_files(self):
        ignore = (Path(__file__).resolve().parents[2] / "apps/dashboard/.dockerignore").read_text(encoding="utf-8")
        lines = {line.strip() for line in ignore.splitlines()}
        self.assertTrue({".env", ".env.*"} <= lines)
