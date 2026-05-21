from __future__ import annotations

import email
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email.message import Message
from email.utils import parsedate_to_datetime, parseaddr
from typing import Any

from database.manager import parse_iso
from services.mail_utils import (
    build_ssl_context,
    format_imap_exception,
    normalize_password,
    normalize_security_mode,
    redact_email,
    resolve_mail_username,
    resolve_runtime_secret,
    validate_mail_username,
)
from services.template_service import html_to_text


MAILBOX_PATTERN = re.compile(rb'.*\((?P<flags>[^)]*)\)\s+"(?P<delimiter>[^"]*)"\s+(?P<name>.+)')
MESSAGE_ID_PATTERN = re.compile(r"<[^>]+>")


class ImapService:
    def __init__(self, logger: Any, credentials: Any):
        self.logger = logger
        self.credentials = credentials

    def _connection_params(self, settings: dict[str, str]) -> tuple[str, int, str, str]:
        host = settings["imap_host"].strip()
        port = int(settings["imap_port"])
        security = normalize_security_mode(settings.get("imap_security", ""), port, "imap")
        username = resolve_mail_username(settings, "imap")
        return host, port, security, username

    def _connect(self, settings: dict[str, str]) -> imaplib.IMAP4 | imaplib.IMAP4_SSL:
        host, port, security, username = self._connection_params(settings)
        password = normalize_password(
            self.credentials.get_password(
                username,
                "imap",
                resolve_runtime_secret(settings, "imap"),
            ),
            host,
        )
        if not username:
            raise ValueError("IMAP username is required. Use the Gmail address or set Sender Email.")
        validate_mail_username(host, username, "imap")
        if not password:
            raise ValueError("IMAP password not found. Save it in Settings or provide it through .env.")

        self.logger.event(
            "imap_connect_started",
            component="imap",
            host=host,
            port=port,
            security=security,
            username=redact_email(username),
        )
        if security == "ssl":
            client = imaplib.IMAP4_SSL(host, port, ssl_context=build_ssl_context(), timeout=30)
        else:
            client = imaplib.IMAP4(host, port, timeout=30)
        client.login(username, password)
        self.logger.event(
            "imap_connect_succeeded",
            component="imap",
            host=host,
            port=port,
            security=security,
            username=redact_email(username),
        )
        return client

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        return isinstance(exc, (TimeoutError, OSError, imaplib.IMAP4.abort))

    def _safe_logout(self, client: imaplib.IMAP4 | imaplib.IMAP4_SSL | None) -> None:
        if client is None:
            return
        try:
            client.logout()
        except Exception as exc:
            self.logger.event(
                "imap_logout_failed",
                level="warning",
                component="imap",
                error=str(exc),
            )

    @staticmethod
    def _decode_mailbox_name(raw_name: bytes) -> str:
        candidate = raw_name.strip()
        if candidate.startswith(b'"') and candidate.endswith(b'"'):
            candidate = candidate[1:-1]
            candidate = candidate.replace(b'\\"', b'"').replace(b"\\\\", b"\\")
        return candidate.decode("utf-8", errors="replace")

    def _parse_mailbox_line(self, raw_line: bytes) -> tuple[set[str], str] | None:
        match = MAILBOX_PATTERN.match(raw_line.strip())
        if not match:
            return None
        raw_flags = match.group("flags").decode("ascii", errors="ignore")
        flags = {flag.strip() for flag in raw_flags.split() if flag.strip()}
        mailbox = self._decode_mailbox_name(match.group("name"))
        return flags, mailbox

    def _list_mailboxes(self, client: imaplib.IMAP4 | imaplib.IMAP4_SSL) -> list[str]:
        defaults = ["INBOX", "[Gmail]/All Mail", "[Google Mail]/All Mail"]
        try:
            status, payload = client.list()
        except Exception as exc:
            self.logger.event(
                "imap_mailbox_list_failed",
                level="warning",
                component="imap",
                error=str(exc),
            )
            return defaults

        if status != "OK":
            self.logger.event(
                "imap_mailbox_list_rejected",
                level="warning",
                component="imap",
                status=status,
                response=self._stringify_response(payload),
            )
            return defaults

        inboxes: list[str] = []
        all_mail: list[str] = []
        fallbacks: list[str] = []
        for raw_line in payload or []:
            if not raw_line:
                continue
            parsed = self._parse_mailbox_line(raw_line)
            if parsed is None:
                continue
            flags, mailbox = parsed
            lowered = mailbox.lower()
            if "\\Noselect" in flags:
                continue
            if "\\Inbox" in flags or lowered == "inbox":
                inboxes.append(mailbox)
            elif "\\All" in flags or lowered in {"[gmail]/all mail", "[google mail]/all mail"}:
                all_mail.append(mailbox)
            elif lowered == "inbox":
                fallbacks.append(mailbox)

        ordered: list[str] = []
        candidates = [*inboxes, *all_mail, *fallbacks]
        if not candidates:
            candidates = defaults
        elif not inboxes:
            candidates = ["INBOX", *candidates]
        for mailbox in candidates:
            if mailbox not in ordered:
                ordered.append(mailbox)
        self.logger.event(
            "imap_mailboxes_resolved",
            component="imap",
            candidates=" | ".join(ordered),
        )
        return ordered

    @staticmethod
    def _quote_mailbox(client: imaplib.IMAP4 | imaplib.IMAP4_SSL, mailbox: str) -> str:
        quote = getattr(client, "_quote", None)
        if callable(quote):
            return quote(mailbox)
        escaped = mailbox.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    @staticmethod
    def _stringify_response(payload: Any) -> str:
        if payload is None:
            return ""
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload).decode("utf-8", errors="replace")
        if isinstance(payload, list):
            return " | ".join(ImapService._stringify_response(item) for item in payload if item)
        return str(payload)

    def _select_mailbox(
        self,
        client: imaplib.IMAP4 | imaplib.IMAP4_SSL,
        mailbox: str,
        readonly: bool,
    ) -> bool:
        quoted_mailbox = self._quote_mailbox(client, mailbox)
        self.logger.event(
            "imap_mailbox_select_started",
            component="imap",
            mailbox=mailbox,
            readonly=readonly,
        )
        status, payload = client.select(quoted_mailbox, readonly=readonly)
        self.logger.event(
            "imap_mailbox_select_finished",
            component="imap",
            mailbox=mailbox,
            readonly=readonly,
            status=status,
            response=self._stringify_response(payload),
        )
        return status == "OK"

    def _ensure_selectable_mailbox(
        self,
        client: imaplib.IMAP4 | imaplib.IMAP4_SSL,
        readonly: bool,
    ) -> str:
        last_error: Exception | None = None
        for mailbox in self._list_mailboxes(client):
            try:
                if self._select_mailbox(client, mailbox, readonly=readonly):
                    return mailbox
            except Exception as exc:
                last_error = exc
                self.logger.event(
                    "imap_mailbox_select_failed",
                    level="warning",
                    component="imap",
                    mailbox=mailbox,
                    readonly=readonly,
                    error=str(exc),
                )
        if last_error is not None:
            raise last_error
        raise imaplib.IMAP4.error("Unable to open a compatible mailbox.")

    @staticmethod
    def _thread_message_ids(parsed_message: email.message.Message) -> set[str]:
        values = " ".join(
            value for value in (parsed_message.get("In-Reply-To", ""), parsed_message.get("References", "")) if value
        )
        return {match.group(0).strip().lower() for match in MESSAGE_ID_PATTERN.finditer(values)}

    @staticmethod
    def _decode_part(part: Message) -> tuple[str, str]:
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace"), part.get_content_type()
        except Exception:
            return payload.decode("utf-8", errors="replace"), part.get_content_type()

    def _message_bodies(self, parsed_message: Message) -> tuple[str, str]:
        plain_parts: list[str] = []
        html_parts: list[str] = []
        if parsed_message.is_multipart():
            for part in parsed_message.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                if part.get_filename():
                    continue
                content, content_type = self._decode_part(part)
                if content_type == "text/plain":
                    plain_parts.append(content)
                elif content_type == "text/html":
                    html_parts.append(content)
        else:
            content, content_type = self._decode_part(parsed_message)
            if content_type == "text/html":
                html_parts.append(content)
            else:
                plain_parts.append(content)
        body_html = "\n".join(part.strip() for part in html_parts if part.strip())
        body_text = "\n".join(part.strip() for part in plain_parts if part.strip())
        if not body_text and body_html:
            body_text = html_to_text(body_html)
        return body_text.strip(), body_html.strip()

    def _sync_replies_once(self, settings: dict[str, str], recruiter_rows: list[dict], database: Any) -> int:
        first_sent_dates = [
            parse_iso(row.get("first_sent_at"))
            for row in recruiter_rows
            if row.get("first_sent_at")
        ]
        if not first_sent_dates:
            return 0

        since_date = min(first_sent_dates) - timedelta(days=1)
        since_filter = since_date.strftime("%d-%b-%Y")
        email_to_recruiter = {row["email"].lower(): row for row in recruiter_rows}
        sent_message_ids = database.get_sent_message_ids_by_recruiter(
            [int(row["id"]) for row in recruiter_rows if row.get("id") is not None]
        )

        client = self._connect(settings)
        try:
            matched = 0
            seen_recruiters: set[int] = set()
            selected_mailboxes: list[str] = []
            for mailbox in self._list_mailboxes(client):
                if mailbox in selected_mailboxes:
                    continue
                try:
                    if not self._select_mailbox(client, mailbox, readonly=True):
                        continue
                except Exception as exc:
                    self.logger.event(
                        "imap_mailbox_skipped",
                        level="warning",
                        component="imap",
                        mailbox=mailbox,
                        error=str(exc),
                    )
                    continue
                selected_mailboxes.append(mailbox)
                status, ids = client.search(None, "SINCE", since_filter)
                if status != "OK":
                    self.logger.event(
                        "imap_search_failed",
                        level="warning",
                        component="imap",
                        mailbox=mailbox,
                        status=status,
                        response=self._stringify_response(ids),
                    )
                    continue

                message_ids = ids[0].split() if ids and ids[0] else []
                self.logger.event(
                    "imap_search_succeeded",
                    component="imap",
                    mailbox=mailbox,
                    since=since_filter,
                    result_count=len(message_ids),
                )
                for message_id in reversed(message_ids):
                    if len(seen_recruiters) == len(email_to_recruiter):
                        break
                    status, payload = client.fetch(
                        message_id,
                        "(BODY.PEEK[])",
                    )
                    if status != "OK" or not payload:
                        self.logger.event(
                            "imap_fetch_failed",
                            level="warning",
                            component="imap",
                            mailbox=mailbox,
                            message_seq=message_id.decode("ascii", errors="ignore"),
                            status=status,
                        )
                        continue
                    raw_bytes = payload[0][1]
                    parsed = email.message_from_bytes(raw_bytes)
                    from_address = parseaddr(parsed.get("From", ""))[1].strip().lower()
                    recruiter = email_to_recruiter.get(from_address)
                    if recruiter is None:
                        continue
                    if int(recruiter["id"]) in seen_recruiters:
                        continue

                    thread_ids = self._thread_message_ids(parsed)
                    recruiter_thread_ids = sent_message_ids.get(int(recruiter["id"]), set())
                    if thread_ids and recruiter_thread_ids and not (thread_ids & recruiter_thread_ids):
                        continue

                    external_message_id = parsed.get("Message-ID", "").strip() or None
                    body_text, body_html = self._message_bodies(parsed)
                    preview = " ".join(body_text.split())[:280] or parsed.get("Subject", "").strip()
                    reply_date = parsedate_to_datetime(parsed.get("Date", "")) if parsed.get("Date") else None
                    first_sent_at = parse_iso(recruiter.get("first_sent_at"))
                    if first_sent_at and reply_date:
                        if reply_date.tzinfo is None:
                            reply_date = reply_date.replace(tzinfo=timezone.utc)
                        if reply_date < first_sent_at:
                            continue

                    reply_received_at = (reply_date or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
                    inserted = database.save_conversation_message(
                        recruiter_id=int(recruiter["id"]),
                        direction="inbound",
                        message_type="reply",
                        subject=parsed.get("Subject", "").strip(),
                        body_text=body_text,
                        body_html=body_html,
                        preview_text=preview,
                        external_message_id=external_message_id,
                        in_reply_to=parsed.get("In-Reply-To", "").strip(),
                        references_header=parsed.get("References", "").strip(),
                        mailbox=mailbox,
                        status="received",
                        received_at=reply_received_at,
                    )
                    if not inserted:
                        seen_recruiters.add(int(recruiter["id"]))
                        continue
                    database.upsert_inbox_reply(
                        recruiter_id=int(recruiter["id"]),
                        subject=parsed.get("Subject", "").strip(),
                        preview=preview,
                        external_message_id=external_message_id,
                        received_at=reply_received_at,
                    )
                    database.mark_reply_received(
                        int(recruiter["id"]),
                        reply_received_at,
                    )
                    seen_recruiters.add(int(recruiter["id"]))
                    matched += 1
                    self.logger.event(
                        "imap_reply_matched",
                        component="imap",
                        mailbox=mailbox,
                        recruiter_id=int(recruiter["id"]),
                        recruiter_email=from_address,
                        matched_by_thread=bool(thread_ids & recruiter_thread_ids),
                    )
            self.logger.event(
                "imap_sync_finished",
                component="imap",
                matched=matched,
                mailboxes_scanned=" | ".join(selected_mailboxes),
                since=since_filter,
            )
            return matched
        finally:
            self._safe_logout(client)

    def test_connection(self, settings: dict[str, str]) -> None:
        host, port, security, _ = self._connection_params(settings)
        client = None
        try:
            client = self._connect(settings)
            mailbox = self._ensure_selectable_mailbox(client, readonly=True)
            self.logger.event(
                "imap_test_connection_succeeded",
                component="imap",
                host=host,
                port=port,
                security=security,
                mailbox=mailbox,
            )
        except Exception as exc:
            raise RuntimeError(format_imap_exception(exc, host, port, security)) from exc
        finally:
            self._safe_logout(client)

    def sync_replies(self, settings: dict[str, str], recruiter_rows: list[dict], database: Any) -> int:
        if not recruiter_rows:
            return 0

        host, port, security, _ = self._connection_params(settings)
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            self.logger.event(
                "imap_sync_started",
                component="imap",
                attempt=attempt,
                recruiter_count=len(recruiter_rows),
            )
            try:
                return self._sync_replies_once(settings, recruiter_rows, database)
            except Exception as exc:
                if attempt >= max_attempts or not self._is_retryable(exc):
                    raise RuntimeError(format_imap_exception(exc, host, port, security)) from exc
                self.logger.event(
                    "imap_sync_retrying",
                    level="warning",
                    component="imap",
                    attempt=attempt,
                    error=str(exc),
                )
        return 0
