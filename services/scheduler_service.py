from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler


class SchedulerService:
    def __init__(self, database, imap_service, logger, settings_provider, bus):
        self.database = database
        self.imap_service = imap_service
        self.logger = logger
        self.settings_provider = settings_provider
        self.bus = bus
        self.scheduler = BackgroundScheduler(
            daemon=True,
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 300,
            },
        )
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self.scheduler.add_job(self.scan_followups, "interval", minutes=60, id="followup_scan")
        self.scheduler.add_job(self.sync_replies, "interval", minutes=120, id="reply_sync")
        self.scheduler.start()
        self._started = True
        self.logger.info("Background scheduler started")
        self.scan_followups()

    def stop(self) -> None:
        if not self._started:
            return
        self.scheduler.shutdown(wait=False)
        self._started = False
        self.logger.info("Background scheduler stopped")

    def scan_followups(self) -> None:
        due_count = self.database.refresh_followup_statuses()
        self.bus.followups_updated.emit()
        self.bus.stats_updated.emit()
        if due_count:
            self.bus.notification_requested.emit(
                "Follow-up Reminder",
                f"{due_count} recruiter follow-up(s) are due.",
                "info",
            )
            self.logger.info(f"{due_count} follow-up reminders are due")

    def sync_replies(self) -> None:
        settings = self.settings_provider()
        username = settings.get("imap_username", "").strip() or settings.get("sender_email", "").strip()
        if not settings.get("imap_host", "").strip() or not username:
            self.logger.info("Skipping background IMAP sync because IMAP settings are incomplete")
            return
        if not self.imap_service.credentials.has_password(username, "imap"):
            self.logger.info("Skipping background IMAP sync because IMAP credentials are unavailable")
            return
        try:
            matched = self.imap_service.sync_replies(
                settings=settings,
                recruiter_rows=self.database.get_unreplied_recruiters(),
                database=self.database,
            )
            if matched:
                self.bus.stats_updated.emit()
                self.bus.followups_updated.emit()
                self.bus.recruiters_updated.emit()
                self.bus.logs_updated.emit()
                self.bus.replies_updated.emit()
                self.bus.notification_requested.emit(
                    "Replies Updated",
                    f"Marked {matched} recruiter replies from your inbox.",
                    "success",
                )
        except Exception as exc:
            self.logger.error(f"Background IMAP sync failed: {exc}")
            self.bus.notification_requested.emit(
                "Background Reply Sync Failed",
                str(exc),
                "warning",
            )
