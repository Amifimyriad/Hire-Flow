from __future__ import annotations

import imaplib
import socket
import smtplib
import ssl
from typing import Any

import certifi


GMAIL_HOST_SUFFIXES = (
    "gmail.com",
    "googlemail.com",
)


def is_gmail_host(host: str) -> bool:
    normalized = host.strip().lower()
    return any(normalized.endswith(suffix) for suffix in GMAIL_HOST_SUFFIXES)


def normalize_security_mode(value: str, port: int, protocol: str) -> str:
    normalized = value.strip().lower()
    aliases = {
        "tls": "starttls",
        "tls/starttls": "starttls",
        "start tls": "starttls",
    }
    normalized = aliases.get(normalized, normalized)

    if protocol == "smtp":
        if port == 465 and normalized in {"", "ssl", "starttls"}:
            return "ssl"
        if port == 587 and normalized in {"", "ssl", "starttls"}:
            return "starttls"
        if normalized in {"ssl", "starttls", "plain"}:
            return normalized
        if port == 465:
            return "ssl"
        if port == 587:
            return "starttls"
        return "plain"

    if normalized == "ssl" or port == 993:
        return "ssl"
    return "plain"


def resolve_mail_username(settings: dict[str, str], purpose: str) -> str:
    key = "smtp_username" if purpose == "smtp" else "imap_username"
    return settings.get(key, "").strip() or settings.get("sender_email", "").strip()


def resolve_runtime_secret(settings: dict[str, str], purpose: str) -> str:
    key = "__smtp_password__" if purpose == "smtp" else "__imap_password__"
    return settings.get(key, "").strip()


def validate_mail_username(host: str, username: str, purpose: str) -> None:
    normalized = username.strip()
    if not normalized:
        return
    if is_gmail_host(host) and "@" not in normalized:
        label = "SMTP" if purpose == "smtp" else "IMAP"
        raise ValueError(f"{label} username must be the full Gmail address when using Gmail.")


def normalize_password(password: str, host: str) -> str:
    if password and is_gmail_host(host) and " " in password:
        return "".join(password.split())
    return password.strip()


def build_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=certifi.where())
    if hasattr(ssl, "TLSVersion"):
        context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def _decode_smtp_error(exc: smtplib.SMTPResponseException) -> str:
    try:
        return exc.smtp_error.decode("utf-8", errors="replace").strip()
    except Exception:
        return str(exc).strip()


def format_smtp_exception(exc: Exception, host: str, port: int, security: str) -> str:
    endpoint = f"{host}:{port} ({security})"
    if isinstance(exc, ssl.SSLCertVerificationError):
        return (
            f"SMTP connection to {endpoint} failed SSL certificate verification. "
            "The app now uses a bundled CA store; if this persists, check macOS trust settings or TLS interception software."
        )
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        detail = _decode_smtp_error(exc)
        return (
            f"SMTP authentication failed for {endpoint}. "
            "For Gmail, use the full Gmail address as the username and a Google App Password. "
            f"Server response: {detail}"
        )
    if isinstance(exc, smtplib.SMTPNotSupportedError):
        return f"SMTP server {endpoint} does not support the requested security mode. {exc}"
    if isinstance(exc, smtplib.SMTPConnectError):
        return f"SMTP server {endpoint} rejected the connection. {exc}"
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return f"SMTP server {endpoint} disconnected unexpectedly. {exc}"
    if isinstance(exc, TimeoutError):
        return f"SMTP connection to {endpoint} timed out."
    if isinstance(exc, socket.gaierror):
        return f"SMTP host lookup failed for {host}. Check the hostname and network connection."
    if isinstance(exc, OSError):
        return f"SMTP connection to {endpoint} failed. {exc}"
    return f"SMTP connection to {endpoint} failed. {exc}"


def format_imap_exception(exc: Exception, host: str, port: int, security: str) -> str:
    endpoint = f"{host}:{port} ({security})"
    if isinstance(exc, ssl.SSLCertVerificationError):
        return (
            f"IMAP connection to {endpoint} failed SSL certificate verification. "
            "The app now uses a bundled CA store; if this persists, check macOS trust settings or TLS interception software."
        )
    if isinstance(exc, imaplib.IMAP4.abort):
        return f"IMAP server {endpoint} disconnected unexpectedly. {exc}"
    if isinstance(exc, imaplib.IMAP4.error):
        detail = str(exc).strip()
        lowered = detail.lower()
        if any(token in lowered for token in ("auth", "login", "application-specific password", "invalid credentials")):
            return (
                f"IMAP authentication failed for {endpoint}. "
                "For Gmail, use the full Gmail address and a Google App Password. "
                f"Server response: {detail}"
            )
        if any(token in lowered for token in ("examine", "select", "parse command", "mailbox")):
            return f"IMAP mailbox command failed for {endpoint}. Server response: {detail}"
        return (
            f"IMAP request failed for {endpoint}. "
            f"Server response: {detail}"
        )
    if isinstance(exc, TimeoutError):
        return f"IMAP connection to {endpoint} timed out."
    if isinstance(exc, socket.gaierror):
        return f"IMAP host lookup failed for {host}. Check the hostname and network connection."
    if isinstance(exc, OSError):
        return f"IMAP connection to {endpoint} failed. {exc}"
    return f"IMAP connection to {endpoint} failed. {exc}"


def redact_email(value: str) -> str:
    email = value.strip()
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[:2]}***@{domain}"
