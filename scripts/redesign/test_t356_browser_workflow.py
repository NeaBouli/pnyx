"""Contracts for the optional, local-only T-356 browser workflow.

The existing Docs job discovers these standard-library tests. Validator fixtures
execute only its extracted inline Node validator, never install or launch browsers.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github/workflows/t356-browser.yml"
TOOLING = REPO / "scripts/redesign/browser-tooling"
NODE = shutil.which("node")


def workflow_step(source: str, marker: str) -> str:
    """Find a step without introducing a YAML dependency into the Docs job."""
    starts = [match.start() for match in re.finditer(
        r"(?m)^\s*- (?:name|uses):", source
    )]
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(source)
        block = source[start:end]
        if marker in block:
            return block
    raise AssertionError(f"workflow step containing {marker!r} missing")


class BrowserWorkflowContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = WORKFLOW.read_text(encoding="utf-8")

    def test_dispatch_is_manual_with_bounded_modes_and_trusted_refs(self) -> None:
        trigger = re.search(r"(?ms)^on:\s*\n(.*?)(?=^\S|\Z)", self.source)
        self.assertIsNotNone(trigger, "expected a top-level on block")
        block = trigger.group(1)
        self.assertIn("workflow_dispatch:", block)
        self.assertNotRegex(block, r"(?m)^\s*(?:push|pull_request|schedule|workflow_call):")
        self.assertRegex(block, r"default:\s*['\"]?data-only['\"]?")
        self.assertRegex(block, r"type:\s*choice")
        self.assertIn("full", block)
        self.assertNotRegex(block, r"(?m)^\s+ref:\s*$")
        self.assertIn("refs/heads/main", self.source)
        self.assertIn("refs/heads/agent/(codex|claude|kimi)/T-[0-9]+", self.source)

    def test_runner_and_action_credentials_follow_ci_contract(self) -> None:
        self.assertIn("fromJSON(vars.CI_RUNNER || '[\"ubuntu-latest\"]')", self.source)
        self.assertRegex(self.source, r"(?m)^\s*contents:\s*read\s*$")
        self.assertRegex(self.source, r"persist-credentials:\s*false")
        self.assertRegex(self.source, r"timeout-minutes:\s*\$\{\{\s*inputs\.mode\s*==\s*'full'\s*&&\s*20\s*\|\|\s*15\s*\}\}")
        actions = re.findall(r"uses:\s*([^\s#]+)", self.source)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$", action)
        self.assertTrue(any(action.startswith("actions/upload-artifact@") for action in actions))

    def test_runner_temp_paths_are_exported_from_the_initial_step(self) -> None:
        header = re.split(r"(?m)^\s*steps:\s*$", self.source, maxsplit=1)[0]
        self.assertNotIn("runner.temp", header, "runner context is unavailable in job.env")
        initial = workflow_step(self.source, "Require a trusted same-repository branch")
        for variable in ("T356_OUT", "PLAYWRIGHT_BROWSERS_PATH"):
            self.assertRegex(initial, rf"{variable}:\s*\$\{{\{{\s*runner\.temp\s*\}}\}}")
            self.assertIn(f"{variable}=%s", initial)
        self.assertRegex(initial, r'>>\s*"\$GITHUB_ENV"')

    def test_isolated_lock_pins_browser_package_and_core_with_integrity(self) -> None:
        manifest = json.loads((TOOLING / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((TOOLING / "package-lock.json").read_text(encoding="utf-8"))
        dependencies = {**manifest.get("dependencies", {}), **manifest.get("devDependencies", {})}
        self.assertEqual(dependencies.get("playwright"), "1.63.0")
        self.assertTrue(manifest.get("private"), "browser tooling must not be publishable")
        packages = lock["packages"]
        for name in ("playwright", "playwright-core"):
            package = packages[f"node_modules/{name}"]
            self.assertEqual(package["version"], "1.63.0")
            self.assertRegex(package["integrity"], r"^sha512-[A-Za-z0-9+/]+=*$")
        self.assertEqual(packages["node_modules/playwright"]["dependencies"]["playwright-core"], "1.63.0")

    def test_install_uses_lock_and_fallback_never_installs_system_libraries(self) -> None:
        self.assertIn("scripts/redesign/browser-tooling", self.source)
        self.assertRegex(self.source, r"npm ci[^\n]*--ignore-scripts[^\n]*--no-audit[^\n]*--no-fund")
        self.assertIn("PLAYWRIGHT_MODULE", self.source)
        self.assertIn("node_modules/playwright", self.source)
        hosted = workflow_step(self.source, "--with-deps")
        self.assertIn("!vars.CI_RUNNER", hosted)
        self.assertRegex(hosted, r"install\s+--with-deps\s+chromium\s+webkit")
        self.assertRegex(self.source, r"install\s+chromium\s+webkit")
        self.assertNotRegex(self.source, r"(?m)^\s*(?:sudo|apt-get|apt)\s")
        self.assertNotRegex(self.source, r"\bnpx\b")

    def test_harness_is_bounded_and_evidence_is_collected_after_failure(self) -> None:
        self.assertIn("t356_democracy_cycle.browser.cjs", self.source)
        self.assertIn("8m", self.source)
        self.assertIn("12m", self.source)
        self.assertRegex(self.source, r"set\s+-[a-z]*o\s+pipefail")
        self.assertRegex(self.source, r"tee[^\n]*harness\.log")
        self.assertIn("env -i PATH=", self.source)
        harness = workflow_step(self.source, "Run local mocked browser harness")
        self.assertRegex(harness, r"(?m)^\s*node -e [^\n]*\|\| exit \$\?\s*$")
        self.assertRegex(harness, r"chmod\s+-R\s+a-w\s+docs\s+scripts/redesign\s+\|\| exit \$\?")
        validator = workflow_step(self.source, "Validate complete evidence")
        uploader = workflow_step(self.source, "actions/upload-artifact@")
        for step in (validator, uploader):
            self.assertRegex(step, r"if:\s*(?:\$\{\{\s*)?always\(\)")
            self.assertIn("env.T356_OUT != ''", step, "unset output must not expand into root globs")
        for artifact in ("setup.log", "harness.log", "results.json", "*.png"):
            self.assertIn(artifact, uploader)
        self.assertRegex(uploader, r"retention-days:\s*3\b")


@unittest.skipUnless(NODE, "Node is required for the inline evidence-validator fixtures")
class BrowserEvidenceValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        step = workflow_step(source, "Validate complete evidence")
        heredoc = re.search(r"(?ms)node\s*<<\s*['\"]?NODE['\"]?\s*\n(.*?)^\s*NODE\s*$", step)
        if heredoc is None:
            raise AssertionError("inline Node evidence validator missing")
        cls.validator = textwrap.dedent(heredoc.group(1))

    def validate(self, payload: object, *, png: bool = True, raw: str | None = None,
                 mode: str = "data-only") -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="t356-validator-") as directory:
            output = Path(directory)
            if payload is not None or raw is not None:
                (output / "results.json").write_text(
                    raw if raw is not None else json.dumps(payload), encoding="utf-8"
                )
            if png:
                (output / "fixture.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            return subprocess.run(
                [NODE, "-"], input=self.validator, capture_output=True, text=True,
                env={"PATH": os.environ.get("PATH", ""), "T356_OUT": directory,
                     "T356_MODE": mode},
                timeout=10, check=False,
            )

    def good_result(self, *, data_only: bool = True) -> dict[str, object]:
        return {"meta": {"dataOnly": data_only, "engines": {"chromium": "123", "webkit": "456"}},
                "total": 1, "failed": 0,
                "results": [{"case": "fixture", "check": "visible", "ok": True, "detail": {}}]}

    def test_complete_evidence_passes(self) -> None:
        completed = self.validate(self.good_result())
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_complete_full_mode_evidence_passes(self) -> None:
        completed = self.validate(self.good_result(data_only=False), mode="full")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_missing_malformed_or_screenshot_free_evidence_fails(self) -> None:
        cases = [(None, True, None), ({}, True, "{broken"), (self.good_result(), False, None)]
        for payload, png, raw in cases:
            with self.subTest(payload=payload, png=png, raw=raw):
                self.assertNotEqual(self.validate(payload, png=png, raw=raw).returncode, 0)

    def test_schema_counts_mode_and_engine_mismatches_fail(self) -> None:
        good = self.good_result()
        invalid = []
        for field, value in (("total", 0), ("total", 2), ("total", "1"), ("failed", 1)):
            result = copy.deepcopy(good)
            result[field] = value
            invalid.append(result)
        for engines in ({"chromium": "123"}, {"chromium": "", "webkit": "456"},
                        {"chromium": "123", "webkit": "456", "firefox": "789"}):
            result = copy.deepcopy(good)
            result["meta"]["engines"] = engines
            invalid.append(result)
        result = copy.deepcopy(good)
        result["meta"]["dataOnly"] = False
        invalid.append(result)
        for ok in ("true", False):
            result = copy.deepcopy(good)
            result["results"][0]["ok"] = ok
            invalid.append(result)
        result = copy.deepcopy(good)
        result["results"][0]["ok"] = False
        result["failed"] = 1
        invalid.append(result)
        for index, result in enumerate(invalid):
            with self.subTest(case=index):
                self.assertNotEqual(self.validate(result).returncode, 0)


if __name__ == "__main__":
    unittest.main()
