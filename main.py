from __future__ import annotations

import sys
import threading
import traceback

from PyQt6.QtWidgets import QApplication

from app.context import AppContext
from app.signals import EventBus
from config import build_config
from database import DatabaseManager
from services import EmailService, ImapService, LogService, RecruiterFileService, SchedulerService
from ui.main_window import MainWindow


def bootstrap() -> AppContext:
    config = build_config()
    bus = EventBus()
    logger = LogService(config.paths.log_file, enable_console=not getattr(sys, "frozen", False))
    database = DatabaseManager(config.paths.database_file, config.default_settings, logger=logger)
    recruiter_files = RecruiterFileService()
    email_service = EmailService(logger)
    imap_service = ImapService(logger, email_service)

    settings = database.get_settings()
    smtp_username = settings.get("smtp_username") or settings.get("sender_email")
    imap_username = settings.get("imap_username") or settings.get("sender_email")
    if smtp_username and config.env_defaults.get("smtp_password"):
        email_service.save_password(smtp_username, config.env_defaults["smtp_password"], "smtp")
    if imap_username and config.env_defaults.get("imap_password"):
        email_service.save_password(imap_username, config.env_defaults["imap_password"], "imap")

    scheduler = SchedulerService(
        database=database,
        imap_service=imap_service,
        logger=logger,
        settings_provider=database.get_settings,
        bus=bus,
    )

    return AppContext(
        config=config,
        bus=bus,
        logger=logger,
        database=database,
        recruiter_files=recruiter_files,
        email_service=email_service,
        imap_service=imap_service,
        scheduler=scheduler,
    )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("HireFlow")
    app.setOrganizationName("HireFlow")
    context = bootstrap()

    def _log_unhandled_exception(exc_type, exc, tb) -> None:
        formatted = "".join(traceback.format_exception(exc_type, exc, tb))
        context.logger.error(f"Unhandled exception:\n{formatted}")

    def _log_thread_exception(args) -> None:
        formatted = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        context.logger.error(f"Unhandled thread exception in {args.thread.name}:\n{formatted}")

    sys.excepthook = _log_unhandled_exception
    threading.excepthook = _log_thread_exception
    window = MainWindow(context)
    window.show()
    context.scheduler.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
