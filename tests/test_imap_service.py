from __future__ import annotations

import imaplib
import unittest

from services.imap_service import ImapService


class FakeLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def event(self, event: str, **fields: object) -> None:
        self.events.append((event, fields))

    def info(self, message: str) -> None:
        self.events.append(("info", {"message": message}))

    def warning(self, message: str) -> None:
        self.events.append(("warning", {"message": message}))

    def error(self, message: str) -> None:
        self.events.append(("error", {"message": message}))


class FakeCredentials:
    def get_password(self, account: str, purpose: str, fallback: str = "") -> str:
        return fallback or "secret"


class FakeDatabase:
    def __init__(self, sent_message_ids: dict[int, set[str]]) -> None:
        self.sent_message_ids = sent_message_ids
        self.marked: list[tuple[int, str]] = []
        self.saved_messages: list[dict[str, object]] = []
        self.upserts: list[dict[str, object]] = []

    def get_sent_message_ids_by_recruiter(self, recruiter_ids: list[int]) -> dict[int, set[str]]:
        return {
            recruiter_id: self.sent_message_ids.get(recruiter_id, set())
            for recruiter_id in recruiter_ids
        }

    def mark_reply_received(self, recruiter_id: int, reply_received_at: str) -> None:
        self.marked.append((recruiter_id, reply_received_at))

    def save_conversation_message(self, **payload):
        external_message_id = payload.get("external_message_id")
        if external_message_id and any(row.get("external_message_id") == external_message_id for row in self.saved_messages):
            return False
        self.saved_messages.append(payload)
        return True

    def upsert_inbox_reply(self, **payload):
        self.upserts.append(payload)


class FakeClient:
    def __init__(self, mailboxes: dict[str, dict[str, object]]) -> None:
        self.mailboxes = mailboxes
        self.current_mailbox = ""
        self.selected_arguments: list[str] = []
        self.logged_out = False

    def _quote(self, mailbox: str) -> str:
        escaped = mailbox.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def list(self):
        rows = []
        for mailbox in self.mailboxes:
            if mailbox == "INBOX":
                rows.append(b'(\\HasNoChildren \\Inbox) "/" "INBOX"')
            elif "All Mail" in mailbox:
                rows.append(f'(\\HasNoChildren \\All) "/" "{mailbox}"'.encode("utf-8"))
        return "OK", rows

    def select(self, mailbox: str, readonly: bool = False):
        self.selected_arguments.append(mailbox)
        self.current_mailbox = mailbox.strip('"')
        if self.current_mailbox not in self.mailboxes:
            return "NO", [b"Unknown mailbox"]
        return "OK", [b"1"]

    def search(self, charset, *criteria):
        mailbox = self.mailboxes[self.current_mailbox]
        search = mailbox.get("search")
        if isinstance(search, Exception):
            raise search
        message_ids = mailbox.get("message_ids", [])
        return "OK", [b" ".join(message_ids)]

    def fetch(self, message_id: bytes, query: str):
        headers = self.mailboxes[self.current_mailbox]["headers"][message_id]
        return "OK", [(b"1", headers)]

    def logout(self) -> None:
        self.logged_out = True


class TestableImapService(ImapService):
    def __init__(self, clients):
        super().__init__(FakeLogger(), FakeCredentials())
        self.clients = list(clients)
        self.connect_calls = 0

    def _connect(self, settings):
        self.connect_calls += 1
        return self.clients.pop(0)


class ImapServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = {
            "imap_host": "imap.gmail.com",
            "imap_port": "993",
            "imap_security": "ssl",
            "imap_username": "sender@gmail.com",
        }
        self.recruiter_rows = [
            {
                "id": 1,
                "email": "recruiter@example.com",
                "first_sent_at": "2026-05-20T10:00:00+00:00",
            }
        ]

    def test_sync_replies_quotes_gmail_all_mail_and_matches_threaded_reply(self) -> None:
        client = FakeClient(
            {
                "INBOX": {
                    "message_ids": [],
                    "headers": {},
                },
                "[Gmail]/All Mail": {
                    "message_ids": [b"101"],
                    "headers": {
                        b"101": (
                            b"From: recruiter@example.com\r\n"
                            b"Date: Thu, 21 May 2026 10:30:00 +0000\r\n"
                            b"Message-ID: <reply-1@example.com>\r\n"
                            b"In-Reply-To: <sent-1@example.com>\r\n"
                            b"References: <sent-1@example.com>\r\n"
                            b"Subject: Re: Hello\r\n\r\n"
                        )
                    },
                },
            }
        )
        service = TestableImapService([client])
        database = FakeDatabase({1: {"<sent-1@example.com>"}})

        matched = service.sync_replies(self.settings, self.recruiter_rows, database)

        self.assertEqual(matched, 1)
        self.assertEqual(len(database.marked), 1)
        self.assertIn('"[Gmail]/All Mail"', client.selected_arguments)
        self.assertTrue(client.logged_out)

    def test_sync_replies_skips_non_thread_message_from_same_sender(self) -> None:
        client = FakeClient(
            {
                "INBOX": {
                    "message_ids": [b"201"],
                    "headers": {
                        b"201": (
                            b"From: recruiter@example.com\r\n"
                            b"Date: Thu, 21 May 2026 10:30:00 +0000\r\n"
                            b"Message-ID: <reply-2@example.com>\r\n"
                            b"In-Reply-To: <other-thread@example.com>\r\n"
                            b"References: <other-thread@example.com>\r\n"
                            b"Subject: Re: Different Thread\r\n\r\n"
                        )
                    },
                }
            }
        )
        service = TestableImapService([client])
        database = FakeDatabase({1: {"<sent-1@example.com>"}})

        matched = service.sync_replies(self.settings, self.recruiter_rows, database)

        self.assertEqual(matched, 0)
        self.assertEqual(database.marked, [])

    def test_sync_replies_retries_after_transient_abort(self) -> None:
        transient_client = FakeClient(
            {
                "INBOX": {
                    "search": imaplib.IMAP4.abort("temporary disconnect"),
                    "message_ids": [],
                    "headers": {},
                }
            }
        )
        success_client = FakeClient(
            {
                "INBOX": {
                    "message_ids": [b"301"],
                    "headers": {
                        b"301": (
                            b"From: recruiter@example.com\r\n"
                            b"Date: Thu, 21 May 2026 10:30:00 +0000\r\n"
                            b"Message-ID: <reply-3@example.com>\r\n"
                            b"In-Reply-To: <sent-1@example.com>\r\n"
                            b"References: <sent-1@example.com>\r\n"
                            b"Subject: Re: Hello Again\r\n\r\n"
                        )
                    },
                }
            }
        )
        service = TestableImapService([transient_client, success_client])
        database = FakeDatabase({1: {"<sent-1@example.com>"}})

        matched = service.sync_replies(self.settings, self.recruiter_rows, database)

        self.assertEqual(matched, 1)
        self.assertEqual(service.connect_calls, 2)
        self.assertEqual(len(database.marked), 1)


if __name__ == "__main__":
    unittest.main()
