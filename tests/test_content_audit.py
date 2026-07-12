from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("content_audit", ROOT / "scripts" / "content_audit.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ContentAuditTests(unittest.TestCase):
    def test_valid_fixture_has_no_errors(self) -> None:
        records = MODULE.load_records(ROOT / "tests" / "fixtures" / "valid_questions.jsonl")
        findings = MODULE.audit_records(records)
        self.assertFalse([f for f in findings if f.level == "error"])

    def test_invalid_fixture_exposes_core_failures(self) -> None:
        records = MODULE.load_records(ROOT / "tests" / "fixtures" / "invalid_questions.jsonl")
        codes = {f.code for f in MODULE.audit_records(records)}
        self.assertIn("duplicate_question_id", codes)
        self.assertIn("invalid_options", codes)
        self.assertIn("invalid_correct_option", codes)
        self.assertIn("experimental_published", codes)
        self.assertIn("missing_passage", codes)

    def test_published_content_requires_resolved_rights(self) -> None:
        record = MODULE.load_records(ROOT / "tests" / "fixtures" / "valid_questions.jsonl")[0]
        record["provenance"]["rights_status"] = "unknown"
        codes = {f.code for f in MODULE.audit_record(record)}
        self.assertIn("published_rights_unresolved", codes)


if __name__ == "__main__":
    unittest.main()
