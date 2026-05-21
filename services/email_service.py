from __future__ import annotations

import mimetypes
import random
import smtplib
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Any

import keyring
from keyring.errors import KeyringError

from services.mail_utils import (
    build_ssl_context,
    format_smtp_exception,
    normalize_password,
    normalize_security_mode,
    redact_email,
    resolve_mail_username,
    resolve_runtime_secret,
    validate_mail_username,
)
from services.template_service import html_to_text, merge_signature, render_template


KEYRING_SMTP = "hireflow.smtp"
KEYRING_IMAP = "hireflow.imap"


@dataclass(slots=True)
class EmailSendResult:
    success: bool
    message_id: str | None
    error_message: str | None
    attempts_used: int
    sent_at: str | None


class EmailService:
    def __init__(self, logger: Any):
        self.logger = logger
        self._smtp: smtplib.SMTP | smtplib.SMTP_SSL | None = None
        self._smtp_signature: tuple[str, int, str, str] | None = None
        self._lock = threading.RLock()
        self._memory_passwords: dict[tuple[str, str], str] = {}

    def save_password(self, account: str, password: str, purpose: str) -> None:
        if not account:
            return
        service_name = KEYRING_SMTP if purpose == "smtp" else KEYRING_IMAP
        self._memory_passwords[(service_name, account)] = password
        try:
            keyring.set_password(service_name, account, password)
        except KeyringError as exc:
            self.logger.warning(f"Keychain save failed for {purpose} credentials: {exc}")

    def get_password(self, account: str, purpose: str, fallback: str = "") -> str:
        if not account:
            return fallback
        service_name = KEYRING_SMTP if purpose == "smtp" else KEYRING_IMAP
        try:
            stored = keyring.get_password(service_name, account)
        except KeyringError as exc:
            self.logger.warning(f"Keychain read failed for {purpose} credentials: {exc}")
            stored = None
        return stored or self._memory_passwords.get((service_name, account), fallback)

    def _connection_signature(self, settings: dict[str, str]) -> tuple[str, int, str, str]:
        host = settings["smtp_host"].strip()
        port = int(settings["smtp_port"])
        security = normalize_security_mode(settings.get("smtp_security", ""), port, "smtp")
        username = resolve_mail_username(settings, "smtp")
        return (
            host,
            port,
            security,
            username,
        )

    def _connect(self, settings: dict[str, str], force_reconnect: bool = False) -> None:
        with self._lock:
            signature = self._connection_signature(settings)
            if self._smtp and not force_reconnect and self._smtp_signature == signature:
                return

            self.disconnect()
            host, port, security, username = signature
            password = normalize_password(
                self.get_password(
                    username,
                    "smtp",
                    resolve_runtime_secret(settings, "smtp"),
                ),
                host,
            )
            if not username:
                raise ValueError("SMTP username is required. Use the Gmail address or set Sender Email.")
            validate_mail_username(host, username, "smtp")
            if not password:
                raise ValueError("SMTP password not found. Save it in Settings or provide it through .env.")

            self.logger.event(
                "smtp_connect_started",
                component="smtp",
                host=host,
                port=port,
                security=security,
                username=redact_email(username),
                force_reconnect=force_reconnect,
            )
            ssl_context = build_ssl_context()
            if security == "ssl":
                client = smtplib.SMTP_SSL(host, port, timeout=30, context=ssl_context)
                client.ehlo()
            elif security == "starttls":
                client = smtplib.SMTP(host, port, timeout=30)
                client.ehlo()
                client.starttls(context=ssl_context)
                client.ehlo()
            else:
                client = smtplib.SMTP(host, port, timeout=30)
                client.ehlo()
            client.login(username, password)
            self._smtp = client
            self._smtp_signature = signature
            self.logger.event(
                "smtp_connect_succeeded",
                component="smtp",
                host=host,
                port=port,
                security=security,
                username=redact_email(username),
            )

    def disconnect(self) -> None:
        with self._lock:
            if self._smtp:
                try:
                    self._smtp.quit()
                except Exception:
                    try:
                        self._smtp.close()
                    except Exception:
                        pass
            self._smtp = None
            self._smtp_signature = None

    def _build_message(
        self,
        recruiter: dict[str, Any],
        subject: str,
        body_html: str,
        settings: dict[str, str],
        attachments: list[str],
        extra_headers: dict[str, str] | None = None,
    ) -> EmailMessage:
        sender_name = settings.get("sender_name", "").strip()
        sender_email = settings.get("sender_email", "").strip() or resolve_mail_username(settings, "smtp")
        if not sender_email:
            raise ValueError("Sender email is required.")

        signature = render_template(
            settings.get("signature_html", ""),
            {
                "sender_name": sender_name,
                "sender_email": sender_email,
                "recruiter_name": recruiter.get("name", ""),
                "company": recruiter.get("company", ""),
            },
        )
        context = {
            "recruiter_name": recruiter.get("name", ""),
            "company": recruiter.get("company", ""),
            "email": recruiter.get("email", ""),
            "sender_name": sender_name,
            "sender_email": sender_email,
        }
        rendered_subject = render_template(subject, context).strip()
        rendered_body = render_template(body_html, context)
        merged_html = merge_signature(rendered_body, signature)

        message = EmailMessage()
        message["Subject"] = rendered_subject
        message["From"] = f"{sender_name} <{sender_email}>" if sender_name else sender_email
        message["To"] = recruiter["email"]
        message["Reply-To"] = sender_email
        message["Message-ID"] = make_msgid(domain=sender_email.split("@", 1)[-1])
        message["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        message["X-Mailer"] = "HireFlow"
        message.set_content(html_to_text(merged_html), subtype="plain", charset="utf-8")
        message.add_alternative(merged_html, subtype="html", charset="utf-8")
        for key, value in (extra_headers or {}).items():
            if value:
                message[key] = value

        for file_name in attachments:
            attachment = Path(file_name)
            if not attachment.exists() or not attachment.is_file():
                raise FileNotFoundError(f"Attachment not found: {attachment}")
            mime_type, _ = mimetypes.guess_type(attachment.name)
            maintype, subtype = ("application", "octet-stream")
            if mime_type:
                maintype, subtype = mime_type.split("/", 1)
            with attachment.open("rb") as handle:
                message.add_attachment(
                    handle.read(),
                    maintype=maintype,
                    subtype=subtype,
                    filename=attachment.name,
                )
        return message

    def test_smtp_connection(self, settings: dict[str, str]) -> None:
        try:
            self._connect(settings, force_reconnect=True)
            assert self._smtp is not None
            status_code, response = self._smtp.noop()
            self.logger.event(
                "smtp_noop_completed",
                component="smtp",
                status_code=status_code,
                response=response.decode("utf-8", errors="replace") if isinstance(response, bytes) else response,
            )
            if status_code != 250:
                raise smtplib.SMTPException(f"Unexpected SMTP NOOP response: {status_code} {response!r}")
        except Exception as exc:
            host, port, security, _ = self._connection_signature(settings)
            raise RuntimeError(format_smtp_exception(exc, host, port, security)) from exc
        finally:
            self.disconnect()

    def send_email(
        self,
        recruiter: dict[str, Any],
        subject: str,
        body_html: str,
        settings: dict[str, str],
        attachments: list[str],
        extra_headers: dict[str, str] | None = None,
    ) -> EmailSendResult:
        with self._lock:
            retries = max(int(settings.get("retry_count", "3")), 1)
            last_error = ""
            for attempt in range(1, retries + 1):
                self.logger.event(
                    "smtp_send_attempt_started",
                    component="smtp",
                    recruiter_email=recruiter["email"],
                    attempt=attempt,
                    max_attempts=retries,
                    email_type=settings.get("__email_type__", "unknown"),
                )
                try:
                    message = self._build_message(recruiter, subject, body_html, settings, attachments, extra_headers)
                    self._connect(settings, force_reconnect=(attempt > 1))
                    assert self._smtp is not None
                    self._smtp.send_message(message)
                    sent_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                    self.logger.event(
                        "smtp_send_succeeded",
                        component="smtp",
                        recruiter_email=recruiter["email"],
                        attempt=attempt,
                        message_id=message["Message-ID"],
                        sent_at=sent_at,
                    )
                    return EmailSendResult(
                        success=True,
                        message_id=message["Message-ID"],
                        error_message=None,
                        attempts_used=attempt,
                        sent_at=sent_at,
                    )
                except Exception as exc:
                    host, port, security, username = self._connection_signature(settings)
                    last_error = format_smtp_exception(exc, host, port, security)
                    self.logger.event(
                        "smtp_send_failed",
                        level="warning",
                        component="smtp",
                        recruiter_email=recruiter["email"],
                        attempt=attempt,
                        max_attempts=retries,
                        host=host,
                        port=port,
                        security=security,
                        username=redact_email(username),
                        error=last_error,
                    )
                    self.disconnect()
            return EmailSendResult(
                success=False,
                message_id=None,
                error_message=last_error,
                attempts_used=retries,
                sent_at=None,
            )

    @staticmethod
    def randomized_delay(settings: dict[str, str]) -> int:
        minimum = int(settings.get("delay_min_seconds", "5"))
        maximum = int(settings.get("delay_max_seconds", "15"))
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        return random.randint(minimum, maximum)

    def has_password(self, account: str, purpose: str, fallback: str = "") -> bool:
        return bool(self.get_password(account, purpose, fallback))
