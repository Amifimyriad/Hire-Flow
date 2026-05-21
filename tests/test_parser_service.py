from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from services.validation import RecruiterFileService, parse_recruiter_identity


class ParserServiceTests(unittest.TestCase):
    def test_parse_recruiter_identity_ignores_generic_domains(self) -> None:
        parsed = parse_recruiter_identity("recruit.team@gmail.com")
        self.assertEqual(parsed["name"], "Recruit Team")
        self.assertEqual(parsed["company"], "")

    def test_parse_recruiter_identity_extracts_company(self) -> None:
        parsed = parse_recruiter_identity("recruit@excelcorp.com")
        self.assertEqual(parsed["name"], "Recruit")
        self.assertEqual(parsed["company"], "Excelcorp")

    def test_build_preview_and_save_csv(self) -> None:
        service = RecruiterFileService()
        preview = service.build_preview_from_emails("recruit@excelcorp.com jobs@peakmetrics.io invalid-email")
        self.assertEqual(len(preview.valid_rows), 2)
        self.assertEqual(len(preview.invalid_rows), 1)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample_recruiters.csv"
            service.save_parsed_csv(path, preview.valid_rows)
            frame = pd.read_csv(path)
            self.assertEqual(frame.columns.tolist(), ["recruiter_name", "company_name", "email", "source", "created_at"])
            self.assertEqual(len(frame), 2)


if __name__ == "__main__":
    unittest.main()
