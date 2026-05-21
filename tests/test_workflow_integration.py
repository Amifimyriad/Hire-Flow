from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from database.manager import DatabaseManager
from tests.test_imap_service import FakeClient, TestableImapService


class WorkflowIntegrationTests(unittest.TestCase):
    def test_initial_send_followup_due_and_reply_sync_cancel_pending_followup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database = DatabaseManager(Path(tmpdir) / "hireflow.sqlite3", {"theme": "light"})
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

                database.create_email_log(
                    recruiter_id=int(recruiter["id"]),
                    recruiter_email=recruiter["email"],
                    email_type="initial",
                    subject="Hello",
                    body_html="<p>Hello</p>",
                    status="sent",
                    attempt_count=1,
                    message_id="<sent-1@example.com>",
                    sent_at="2026-05-10T10:00:00+00:00",
                )
                database.mark_initial_sent(
                    recruiter_id=int(recruiter["id"]),
                    subject="Hello",
                    sent_at="2026-05-10T10:00:00+00:00",
                    followup_days=3,
                )

                due_followups = database.get_due_followups()
                self.assertEqual(len(due_followups), 1)

                client = FakeClient(
                    {
                        "INBOX": {
                            "message_ids": [b"401"],
                            "headers": {
                                b"401": (
                                    b"From: recruiter@example.com\r\n"
                                    b"Date: Thu, 21 May 2026 10:30:00 +0000\r\n"
                                    b"Message-ID: <reply-4@example.com>\r\n"
                                    b"In-Reply-To: <sent-1@example.com>\r\n"
                                    b"References: <sent-1@example.com>\r\n"
                                    b"Subject: Re: Hello\r\n\r\n"
                                )
                            },
                        }
                    }
                )
                service = TestableImapService([client])
                matched = service.sync_replies(
                    {
                        "imap_host": "imap.gmail.com",
                        "imap_port": "993",
                        "imap_security": "ssl",
                        "imap_username": "sender@gmail.com",
                    },
                    database.get_unreplied_recruiters(),
                    database,
                )

                self.assertEqual(matched, 1)
                updated_recruiter = database.get_recruiters()[0]
                self.assertEqual(updated_recruiter["reply_status"], 1)
                self.assertEqual(updated_recruiter["followup_status"], "replied")
                self.assertEqual(database.get_due_followups(), [])
                stats = database.get_stats()
                self.assertEqual(stats["sent_total"], 1)
                self.assertEqual(stats["replies_received"], 1)
            finally:
                database.close()

    def test_additional_reply_still_syncs_after_first_reply(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            database = DatabaseManager(Path(tmpdir) / "hireflow.sqlite3", {"theme": "light"})
            try:
                database.import_recruiters(
                    [{"name": "Recruiter One", "company": "Acme", "email": "recruiter@example.com"}],
                    "sample.csv",
                )
                recruiter = database.get_recruiters()[0]
                database.create_email_log(
                    recruiter_id=int(recruiter["id"]),
                    recruiter_email=recruiter["email"],
                    email_type="initial",
                    subject="Hello",
                    body_html="<p>Hello</p>",
                    status="sent",
                    attempt_count=1,
                    message_id="<sent-1@example.com>",
                    sent_at="2026-05-10T10:00:00+00:00",
                )
                database.mark_initial_sent(
                    recruiter_id=int(recruiter["id"]),
                    subject="Hello",
                    sent_at="2026-05-10T10:00:00+00:00",
                    followup_days=3,
                )
                for msgid in [b"501", b"502"]:
                    client = FakeClient(
                        {
                            "INBOX": {
                                "message_ids": [msgid],
                                "headers": {
                                    msgid: (
                                        b"From: recruiter@example.com\r\n"
                                        + (b"Date: Thu, 21 May 2026 10:30:00 +0000\r\n" if msgid == b"501" else b"Date: Thu, 21 May 2026 11:30:00 +0000\r\n")
                                        + (b"Message-ID: <reply-5@example.com>\r\n" if msgid == b"501" else b"Message-ID: <reply-6@example.com>\r\n")
                                        + b"In-Reply-To: <sent-1@example.com>\r\n"
                                        + b"References: <sent-1@example.com>\r\n"
                                        + b"Subject: Re: Hello\r\n\r\nSecond body"
                                    )
                                },
                            }
                        }
                    )
                    service = TestableImapService([client])
                    matched = service.sync_replies(
                        {
                            "imap_host": "imap.gmail.com",
                            "imap_port": "993",
                            "imap_security": "ssl",
                            "imap_username": "sender@gmail.com",
                        },
                        database.get_unreplied_recruiters(),
                        database,
                    )
                    self.assertEqual(matched, 1)
                messages = database.get_conversation_messages(int(recruiter["id"]))
                inbound = [row for row in messages if row["direction"] == "inbound"]
                self.assertEqual(len(inbound), 2)
            finally:
                database.close()


if __name__ == "__main__":
    unittest.main()
