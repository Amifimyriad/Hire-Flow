from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.workers import BulkEmailWorker
from ui.widgets.table_utils import configure_table, set_table_rows


class SendEmailsPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.worker = None
        self._draft_dirty = False
        self._loading_draft = False
        self.recipients: list[dict] = []
        self.subject_input = QLineEdit()
        self.resume_input = QLineEdit()
        self.cover_input = QLineEdit()
        self.body_editor = QTextEdit()
        self.table = QTableWidget()
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("Ready to send initial outreach emails.")
        self.start_button = QPushButton("Start Sending")
        self.stop_button = QPushButton("Stop")
        self.save_draft_button = QPushButton("Save Draft")
        self.refresh_button = QPushButton("Refresh Recipients")
        self._build_ui()
        self.context.bus.recruiters_updated.connect(self.refresh_data)
        self.context.bus.logs_updated.connect(self.refresh_data)
        self.refresh_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        self.setMinimumWidth(1180)

        hero_card = QFrame()
        hero_card.setObjectName("Card")
        hero_card.setProperty("variant", "hero")
        hero_layout = QVBoxLayout(hero_card)
        eyebrow = QLabel("Campaign")
        eyebrow.setObjectName("Eyebrow")
        title = QLabel("Compose outreach with a clean delivery queue.")
        title.setObjectName("SectionTitle")
        caption = QLabel("Draft once, attach your PDFs, and let HireFlow handle pacing and persistence.")
        caption.setObjectName("HeroBody")
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(caption)
        layout.addWidget(hero_card)

        top_card = QFrame()
        top_card.setObjectName("Card")
        top_card.setProperty("variant", "accent")
        top_layout = QVBoxLayout(top_card)
        intro = QLabel(
            "Use placeholders like {{recruiter_name}}, {{company}}, {{sender_name}}, and {{sender_email}}."
        )
        intro.setObjectName("Muted")
        top_layout.addWidget(intro)

        form_layout = QGridLayout()
        form_layout.addWidget(QLabel("Subject"), 0, 0)
        form_layout.addWidget(self.subject_input, 0, 1, 1, 3)

        self.resume_input.setPlaceholderText("Attach your resume PDF")
        self.cover_input.setPlaceholderText("Attach your cover letter PDF")
        resume_button = QPushButton("Browse Resume")
        cover_button = QPushButton("Browse Cover Letter")
        resume_button.clicked.connect(lambda: self.pick_file(self.resume_input))
        cover_button.clicked.connect(lambda: self.pick_file(self.cover_input))

        form_layout.addWidget(QLabel("Resume PDF"), 1, 0)
        form_layout.addWidget(self.resume_input, 1, 1, 1, 2)
        form_layout.addWidget(resume_button, 1, 3)
        form_layout.addWidget(QLabel("Cover Letter PDF"), 2, 0)
        form_layout.addWidget(self.cover_input, 2, 1, 1, 2)
        form_layout.addWidget(cover_button, 2, 3)
        top_layout.addLayout(form_layout)

        top_layout.addWidget(QLabel("HTML Email Body"))
        self.body_editor.setMinimumHeight(220)
        top_layout.addWidget(self.body_editor)

        actions = QHBoxLayout()
        self.refresh_button.clicked.connect(self.refresh_data)
        self.save_draft_button.clicked.connect(lambda: self.save_draft(notify=True))
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self.start_sending)
        self.stop_button.setObjectName("DangerButton")
        self.stop_button.clicked.connect(self.stop_sending)
        self.stop_button.setEnabled(False)
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.save_draft_button)
        actions.addStretch(1)
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        top_layout.addLayout(actions)

        self.progress_bar.setValue(0)
        top_layout.addWidget(self.progress_bar)
        self.status_label.setObjectName("Muted")
        top_layout.addWidget(self.status_label)

        self.subject_input.textChanged.connect(self._mark_draft_dirty)
        self.resume_input.textChanged.connect(self._mark_draft_dirty)
        self.cover_input.textChanged.connect(self._mark_draft_dirty)
        self.body_editor.textChanged.connect(self._mark_draft_dirty)

        layout.addWidget(top_card)

        table_card = QFrame()
        table_card.setObjectName("Card")
        table_card.setMinimumWidth(980)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 18, 18, 18)
        table_layout.setSpacing(10)
        pending_title = QLabel("Pending Initial Recipients")
        pending_title.setObjectName("SectionTitle")
        table_layout.addWidget(pending_title)
        configure_table(
            self.table,
            ["Name", "Company", "Email", "Created"],
            column_widths=[180, 170, 260, 120],
        )
        table_layout.addWidget(self.table)
        layout.addWidget(table_card)
        layout.addStretch(1)

    def pick_file(self, target_input: QLineEdit) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose PDF attachment",
            str(Path.home()),
            "PDF Files (*.pdf)",
        )
        if file_path:
            target_input.setText(file_path)

    def current_settings(self) -> dict[str, str]:
        return self.context.database.get_settings()

    def _mark_draft_dirty(self) -> None:
        if not self._loading_draft:
            self._draft_dirty = True

    def _load_draft_fields(self, settings: dict[str, str], force: bool = False) -> None:
        if self._draft_dirty and not force:
            return
        self._loading_draft = True
        try:
            self.subject_input.setText(settings.get("email_subject", ""))
            self.body_editor.setPlainText(settings.get("email_body_html", ""))
            self.resume_input.setText(settings.get("resume_path", ""))
            self.cover_input.setText(settings.get("cover_letter_path", ""))
            self._draft_dirty = False
        finally:
            self._loading_draft = False

    def save_draft(self, notify: bool = True) -> None:
        self.context.database.save_settings(
            {
                "email_subject": self.subject_input.text().strip(),
                "email_body_html": self.body_editor.toPlainText(),
                "resume_path": self.resume_input.text().strip(),
                "cover_letter_path": self.cover_input.text().strip(),
            }
        )
        self._draft_dirty = False
        if notify:
            self.context.bus.notification_requested.emit("Draft Saved", "Email draft settings were saved.", "success")

    def refresh_data(self) -> None:
        settings = self.current_settings()
        self._load_draft_fields(settings)

        self.recipients = self.context.database.get_initial_send_candidates()
        set_table_rows(
            self.table,
            [
                [
                    row["name"],
                    row["company"] or "-",
                    row["email"],
                    row["created_at"][:10],
                ]
                for row in self.recipients
            ],
        )
        self.status_label.setText(f"{len(self.recipients)} recipient(s) are ready for initial outreach.")
        self.progress_bar.setMaximum(max(len(self.recipients), 1))
        self.progress_bar.setValue(0)

    def _validate_before_send(self) -> list[str] | None:
        subject = self.subject_input.text().strip()
        body = self.body_editor.toPlainText().strip()
        resume = self.resume_input.text().strip()
        cover = self.cover_input.text().strip()
        if not self.recipients:
            self.context.bus.notification_requested.emit("No Recipients", "No new recruiters are available to email.", "error")
            return None
        if not subject or not body:
            self.context.bus.notification_requested.emit("Missing Content", "Subject and body are required.", "error")
            return None
        attachments = [resume, cover]
        if not all(attachments):
            self.context.bus.notification_requested.emit(
                "Missing Attachments",
                "Both resume and cover letter PDFs are required for initial outreach.",
                "error",
            )
            return None
        for file_name in attachments:
            if not Path(file_name).exists():
                self.context.bus.notification_requested.emit("Attachment Error", f"Attachment not found: {file_name}", "error")
                return None
        return attachments

    def start_sending(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        attachments = self._validate_before_send()
        if attachments is None:
            return
        settings = self.current_settings()
        self.save_draft(notify=False)
        self.worker = BulkEmailWorker(
            mode="initial",
            targets=self.recipients,
            subject=self.subject_input.text().strip(),
            body_html=self.body_editor.toPlainText(),
            attachments=attachments,
            settings=settings,
            database=self.context.database,
            email_service=self.context.email_service,
        )
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.completed.connect(self.on_completed)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.worker.deleteLater)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.save_draft_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.worker.start()

    def stop_sending(self) -> None:
        if self.worker:
            self.worker.stop()
            self.status_label.setText("Stopping send queue...")

    def on_progress(self, current: int, total: int, message: str) -> None:
        if current >= 0 and total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        self.status_label.setText(message)

    def on_completed(self, summary: dict) -> None:
        self.worker = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_draft_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.context.bus.logs_updated.emit()
        self.context.bus.recruiters_updated.emit()
        self.context.bus.followups_updated.emit()
        self.context.bus.stats_updated.emit()
        self.refresh_data()
        self.context.bus.notification_requested.emit(
            "Send Queue Finished",
            f"Sent {summary['sent']}, failed {summary['failed']}, skipped {summary['skipped']}.",
            "success" if summary["failed"] == 0 else "error",
        )

    def on_failed(self, message: str) -> None:
        self.worker = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_draft_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.context.bus.logs_updated.emit()
        self.context.bus.recruiters_updated.emit()
        self.context.bus.followups_updated.emit()
        self.context.bus.stats_updated.emit()
        self.refresh_data()
        self.context.bus.notification_requested.emit("Sending Failed", message, "error")

    def shutdown(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
