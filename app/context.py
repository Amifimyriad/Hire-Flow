from __future__ import annotations

from dataclasses import dataclass

from app.signals import EventBus
from config.app_config import AppConfig
from database.manager import DatabaseManager
from services.email_service import EmailService
from services.imap_service import ImapService
from services.logging_service import LogService
from services.scheduler_service import SchedulerService
from services.validation import RecruiterFileService


@dataclass(slots=True)
class AppContext:
    config: AppConfig
    bus: EventBus
    logger: LogService
    database: DatabaseManager
    recruiter_files: RecruiterFileService
    email_service: EmailService
    imap_service: ImapService
    scheduler: SchedulerService

