"""Pin the public audit disclosure to its reviewed status claims."""

import unittest

import approved_audit_delta
import r0_inventory


class ApprovedAuditDeltaTest(unittest.TestCase):
    def test_published_page_matches(self) -> None:
        content = (r0_inventory.DOCS_DIR / "wiki/audit.html").read_text(encoding="utf-8")
        self.assertTrue(approved_audit_delta.matches_audit_page(content))

    def test_changed_finding_count_fails(self) -> None:
        content = (r0_inventory.DOCS_DIR / "wiki/audit.html").read_text(encoding="utf-8")
        self.assertFalse(approved_audit_delta.matches_audit_page(content.replace("62 ευρήματα", "0 ευρήματα")))


if __name__ == "__main__":
    unittest.main()
