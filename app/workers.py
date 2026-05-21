from __future__ import annotations

from collections.abc import Callable
import time

from PyQt6.QtCore import QThread, pyqtSignal

from services.template_service import html_to_text


class BulkEmailWorker(QThread):
    progress_updated = pyqtSignal(int, int, str)
    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(
        self,
        mode,
        targets,
        subject,
        body_html,
        attachments,
        settings,
        database,
        email_service,
    ):
        super().__init__()
        self.mode = mode
        self.targets = targets
        self.subject = subject
        self.body_html = body_html
        self.attachments = attachments
        self.settings = settings
        self.database = database
        self.email_service = email_service
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def _sleep_with_stop(self, seconds: int) -> bool:
        for remaining in range(seconds, 0, -1):
            if self._stop_requested:
                return False
            self.progress_updated.emit(-1, -1, f"Waiting {remaining}s before the next send...")
            time.sleep(1)
        return not self._stop_requested

    def run(self) -> None:
        summary = {"sent": 0, "failed": 0, "skipped": 0, "stopped": False}
        total = len(self.targets)
        followup_days = int(self.settings.get("followup_delay_days", "3"))
        daily_limit = max(int(self.settings.get("daily_send_limit", "40")), 1)

        try:
            for index, target in enumerate(self.targets, start=1):
                if self._stop_requested:
                    summary["stopped"] = True
                    break

                if self.database.get_daily_sent_count() >= daily_limit:
                    summary["stopped"] = True
                    summary["skipped"] = total - index + 1
                    self.progress_updated.emit(
                        index - 1,
                        total,
                        f"Daily send limit of {daily_limit} reached.",
                    )
                    break

                recruiter = {
                    "id": target.get("recruiter_id", target.get("id")),
                    "name": target["name"],
                    "company": target.get("company", ""),
                    "email": target["email"],
                }
                self.progress_updated.emit(index - 1, total, f"Sending to {recruiter['email']}...")
                result = self.email_service.send_email(
                    recruiter=recruiter,
                    subject=self.subject,
                    body_html=self.body_html,
                    settings=self.settings | {"__email_type__": self.mode},
                    attachments=self.attachments,
                )
                if result.success and result.sent_at:
                    log_id = self.database.create_email_log(
                        recruiter_id=recruiter["id"],
                        recruiter_email=recruiter["email"],
                        email_type=self.mode,
                        subject=self.subject,
                        body_html=self.body_html,
                        status="sent",
                        attempt_count=result.attempts_used,
                        message_id=result.message_id,
                        sent_at=result.sent_at,
                    )
                    self.database.save_conversation_message(
                        recruiter_id=int(recruiter["id"]),
                        direction="outbound",
                        message_type=self.mode,
                        subject=self.subject,
                        body_text=html_to_text(self.body_html),
                        body_html=self.body_html,
                        preview_text=self.subject,
                        external_message_id=result.message_id,
                        sent_at=result.sent_at,
                        status="sent",
                    )
                    if self.mode == "initial":
                        self.database.mark_initial_sent(
                            recruiter_id=recruiter["id"],
                            subject=self.subject,
                            sent_at=result.sent_at,
                            followup_days=followup_days,
                        )
                    else:
                        self.database.mark_followup_sent(
                            followup_id=target["followup_id"],
                            recruiter_id=recruiter["id"],
                            sent_log_id=log_id,
                            sent_at=result.sent_at,
                            subject=self.subject,
                            body_html=self.body_html,
                            followup_days=followup_days,
                        )
                    summary["sent"] += 1
                    self.progress_updated.emit(index, total, f"Sent to {recruiter['email']}")
                else:
                    self.database.create_email_log(
                        recruiter_id=recruiter["id"],
                        recruiter_email=recruiter["email"],
                        email_type=self.mode,
                        subject=self.subject,
                        body_html=self.body_html,
                        status="failed",
                        attempt_count=result.attempts_used,
                        error_message=result.error_message,
                    )
                    summary["failed"] += 1
                    self.progress_updated.emit(
                        index,
                        total,
                        f"Failed for {recruiter['email']}: {result.error_message}",
                    )

                if index < total and not self._stop_requested:
                    delay = self.email_service.randomized_delay(self.settings)
                    if not self._sleep_with_stop(delay):
                        summary["stopped"] = True
                        summary["skipped"] = total - index
                        break
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        finally:
            self.email_service.disconnect()

        self.completed.emit(summary)


class ReplySyncWorker(QThread):
    completed = pyqtSignal(int)
    failed = pyqtSignal(str)

    def __init__(self, settings, database, imap_service):
        super().__init__()
        self.settings = settings
        self.database = database
        self.imap_service = imap_service

    def run(self) -> None:
        try:
            matched = self.imap_service.sync_replies(
                settings=self.settings,
                recruiter_rows=self.database.get_unreplied_recruiters(),
                database=self.database,
            )
            self.completed.emit(matched)
        except Exception as exc:
            self.failed.emit(str(exc))


class ConnectivityTestWorker(QThread):
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, label: str, callback: Callable[[], None]):
        super().__init__()
        self.label = label
        self.callback = callback

    def run(self) -> None:
        try:
            self.callback()
            self.completed.emit(self.label)
        except Exception as exc:
            self.failed.emit(str(exc))


class SingleReplyWorker(QThread):
    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, recruiter, subject, body_html, mode, settings, thread_headers, database, email_service):
        super().__init__()
        self.recruiter = recruiter
        self.subject = subject
        self.body_html = body_html
        self.mode = mode
        self.settings = settings
        self.thread_headers = thread_headers
        self.database = database
        self.email_service = email_service

    def run(self) -> None:
        try:
            result = self.email_service.send_email(
                recruiter=self.recruiter,
                subject=self.subject,
                body_html=self.body_html,
                settings=self.settings | {"__email_type__": self.mode},
                attachments=[],
                extra_headers=self.thread_headers,
            )
            if not result.success or not result.sent_at:
                raise RuntimeError(result.error_message or "Reply send failed.")
            log_id = self.database.create_email_log(
                recruiter_id=self.recruiter["id"],
                recruiter_email=self.recruiter["email"],
                email_type=self.mode,
                subject=self.subject,
                body_html=self.body_html,
                status="sent",
                attempt_count=result.attempts_used,
                message_id=result.message_id,
                sent_at=result.sent_at,
            )
            self.database.save_conversation_message(
                recruiter_id=int(self.recruiter["id"]),
                direction="outbound",
                message_type=self.mode,
                subject=self.subject,
                body_text=html_to_text(self.body_html),
                body_html=self.body_html,
                preview_text=self.subject,
                external_message_id=result.message_id,
                in_reply_to=self.thread_headers.get("In-Reply-To", ""),
                references_header=self.thread_headers.get("References", ""),
                sent_at=result.sent_at,
                status="sent",
            )
            self.completed.emit(
                {
                    "log_id": log_id,
                    "message_id": result.message_id,
                    "sent_at": result.sent_at,
                    "attempts_used": result.attempts_used,
                }
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.email_service.disconnect()
