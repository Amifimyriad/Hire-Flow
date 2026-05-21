from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database.manager import DatabaseManager


class DummyLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def event(self, event: str, **fields: object) -> None:
        self.events.append((event, fields))


class DatabaseManagerTests(unittest.TestCase):
    def test_reset_runtime_state_clears_runtime_tables_and_keeps_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database = DatabaseManager(
                Path(tmpdir) / "hireflow.sqlite3",
                {"theme": "light", "sender_email": "sender@example.com"},
                logger=DummyLogger(),
            )
            try:
                inserted, updated = database.import_recruiters(
                    [
                        {
                            "name": "Recruiter One",
                            "company": "Acme",
                            "email": "recruiter@example.com",
                        }
                    ],
                    "sample.csv",
                )
                self.assertEqual((inserted, updated), (1, 0))
                recruiter = database.get_recruiters()[0]
                log_id = database.create_email_log(
                    recruiter_id=int(recruiter["id"]),
                    recruiter_email=recruiter["email"],
                    email_type="initial",
                    subject="Hello",
                    body_html="<p>Hello</p>",
                    status="sent",
                    attempt_count=1,
                    message_id="<sent-1@example.com>",
                    sent_at="2026-05-20T10:00:00+00:00",
                )
                database.mark_initial_sent(
                    recruiter_id=int(recruiter["id"]),
                    subject="Hello",
                    sent_at="2026-05-20T10:00:00+00:00",
                    followup_days=3,
                )
                self.assertGreater(log_id, 0)
                self.assertEqual(len(database.get_recruiters()), 1)
                self.assertEqual(len(database.list_logs(limit=100)), 1)
                self.assertEqual(len(database.get_sent_message_ids_by_recruiter([int(recruiter["id"])])), 1)

                counts = database.reset_runtime_state(preserve_settings=True)

                self.assertEqual(counts["recruiters"], 1)
                self.assertEqual(counts["email_logs"], 1)
                self.assertEqual(counts["followups"], 1)
                self.assertEqual(len(database.get_recruiters()), 0)
                self.assertEqual(len(database.list_logs(limit=100)), 0)
                self.assertEqual(len(database.get_due_followups()), 0)
                settings = database.get_settings()
                self.assertEqual(settings["theme"], "light")
                self.assertEqual(settings["sender_email"], "sender@example.com")
            finally:
                database.close()


if __name__ == "__main__":
    unittest.main()
