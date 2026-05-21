from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _bundle_root() -> Path:
    if _is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


@dataclass(slots=True)
class AppPaths:
    project_root: Path
    runtime_root: Path
    database_file: Path
    logs_dir: Path
    log_file: Path
    templates_dir: Path
    assets_dir: Path
    samples_dir: Path

    def ensure_directories(self) -> None:
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class AppConfig:
    app_name: str
    version: str
    paths: AppPaths
    default_settings: dict[str, str]
    env_defaults: dict[str, str]


def _load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def build_paths() -> AppPaths:
    project_root = Path(__file__).resolve().parent.parent
    bundle_root = _bundle_root()
    if _is_frozen():
        if sys.platform == "darwin":
            runtime_root = Path.home() / "Library" / "Application Support" / "HireFlow"
            logs_dir = Path.home() / "Library" / "Logs" / "HireFlow"
        elif sys.platform.startswith("win"):
            runtime_root = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "HireFlow"
            logs_dir = runtime_root / "logs"
        else:
            runtime_root = Path(os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "HireFlow"
            logs_dir = Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "HireFlow"
        database_file = runtime_root / "hireflow.sqlite3"
    else:
        runtime_root = project_root
        database_file = project_root / "database" / "hireflow.sqlite3"
        logs_dir = project_root / "logs"

    return AppPaths(
        project_root=project_root,
        runtime_root=runtime_root,
        database_file=database_file,
        logs_dir=logs_dir,
        log_file=logs_dir / "hireflow.log",
        templates_dir=bundle_root / "templates",
        assets_dir=bundle_root / "assets",
        samples_dir=bundle_root / "samples",
    )


def build_config() -> AppConfig:
    paths = build_paths()
    load_dotenv(paths.project_root / ".env")
    paths.ensure_directories()

    email_template = _load_template(paths.templates_dir / "default_email.html")
    followup_template = _load_template(paths.templates_dir / "default_followup.html")

    default_settings = {
        "sender_name": os.getenv("HIREFLOW_SENDER_NAME", ""),
        "sender_email": os.getenv("HIREFLOW_SENDER_EMAIL", ""),
        "smtp_host": os.getenv("HIREFLOW_SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": os.getenv("HIREFLOW_SMTP_PORT", "465"),
        "smtp_security": os.getenv("HIREFLOW_SMTP_SECURITY", "ssl"),
        "smtp_username": os.getenv("HIREFLOW_SMTP_USERNAME", ""),
        "imap_host": os.getenv("HIREFLOW_IMAP_HOST", "imap.gmail.com"),
        "imap_port": os.getenv("HIREFLOW_IMAP_PORT", "993"),
        "imap_security": os.getenv("HIREFLOW_IMAP_SECURITY", "ssl"),
        "imap_username": os.getenv("HIREFLOW_IMAP_USERNAME", ""),
        "daily_send_limit": os.getenv("HIREFLOW_DAILY_SEND_LIMIT", "40"),
        "delay_min_seconds": os.getenv("HIREFLOW_DELAY_MIN_SECONDS", "5"),
        "delay_max_seconds": os.getenv("HIREFLOW_DELAY_MAX_SECONDS", "15"),
        "retry_count": os.getenv("HIREFLOW_RETRY_COUNT", "3"),
        "followup_delay_days": os.getenv("HIREFLOW_FOLLOWUP_DELAY_DAYS", "3"),
        "theme": os.getenv("HIREFLOW_THEME", "system"),
        "signature_html": os.getenv(
            "HIREFLOW_SIGNATURE_HTML",
            "<p>Best regards,<br>{{sender_name}}<br>{{sender_email}}</p>",
        ),
        "email_subject": os.getenv(
            "HIREFLOW_EMAIL_SUBJECT",
            "Application for Data Analyst / Power BI Developer Opportunities",
        ),
        "followup_subject": os.getenv(
            "HIREFLOW_FOLLOWUP_SUBJECT",
            "Following up on my application for Data Analyst / Power BI Developer roles",
        ),
        "email_body_html": email_template,
        "followup_body_html": followup_template,
    }

    env_defaults = {
        "smtp_password": os.getenv("HIREFLOW_SMTP_PASSWORD", ""),
        "imap_password": os.getenv("HIREFLOW_IMAP_PASSWORD", ""),
    }

    return AppConfig(
        app_name="HireFlow",
        version="1.0.0",
        paths=paths,
        default_settings=default_settings,
        env_defaults=env_defaults,
    )
