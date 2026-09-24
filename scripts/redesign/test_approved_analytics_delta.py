"""The EKA-33 exception must not weaken unrelated preservation gates."""

from __future__ import annotations

import unittest

import approved_analytics_delta as delta


class ApprovedAnalyticsDeltaTest(unittest.TestCase):
    def test_only_exact_script_evidence_is_removed(self) -> None:
        other = {"src": "https://example.org/necessary.js", "attrs": {"src": "https://example.org/necessary.js"}}
        other_resource = {"kind": "external", "source": "script.src", "host": "example.org", "url": other["src"]}
        page = {
            "scripts": {"external": [delta.SCRIPT, other]},
            "resources": [delta.RESOURCE, other_resource],
            "external_hosts": ["analytics.ekklesia.gr", "example.org"],
            "links": [{"href": "/el/results"}],
        }
        normalized = delta.baseline_without_analytics(page)
        self.assertEqual([other], normalized["scripts"]["external"])
        self.assertEqual([other_resource], normalized["resources"])
        self.assertEqual(["example.org"], normalized["external_hosts"])
        self.assertEqual(page["links"], normalized["links"])
        self.assertEqual([delta.SCRIPT, other], page["scripts"]["external"])

    def test_unapproved_page_uses_frozen_hash(self) -> None:
        self.assertEqual("frozen", delta.expected_sha256("docs/other.html", "frozen"))


if __name__ == "__main__":
    unittest.main()
