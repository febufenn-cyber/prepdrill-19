from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from prepdrill_content.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


class Phase1CliTests(unittest.TestCase):
    def test_init_import_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / "content.sqlite3")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--db", db, "init-db"]), 0)
                self.assertEqual(
                    main(["--db", db, "import", str(FIXTURES / "phase1_valid.jsonl"), "--source-document-id", "fixture-doc-001"]),
                    0,
                )
                self.assertEqual(main(["--db", db, "readiness-report"]), 0)
            self.assertIn('"canonical_questions": 1', output.getvalue())


if __name__ == "__main__":
    unittest.main()
