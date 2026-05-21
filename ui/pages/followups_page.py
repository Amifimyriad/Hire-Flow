from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from app.workers import BulkEmailWorker
from ui.widgets.table_utils import configure_table, format_timestamp, set_table_rows


class FollowUpsPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.worker = None
        self._draft_dirty = False
        self._loading_draft = False
        self.followups: list[dict] = []
        self.subject_input = QLineEdit()
        self.body_editor = QTextEdit()
        self.table = QTableWidget()
        self.progress_bar = QProgressBar()
        self.status_label = QLabel("Pending recruiter follow-ups will appear here.")
        self._build_ui()
        self.context.bus.followups_updated.connect(self.refresh_data)
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
        eyebrow = QLabel("Cadence")
        eyebrow.setObjectName("Eyebrow")
        title = QLabel("Review due follow-ups and keep reminders intentional.")
        title.setObjectName("SectionTitle")
        body = QLabel("Two-touch follow-up flow with queue control, stoppable sends, and clean status feedback.")
        body.setObjectName("HeroBody")
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(body)
        layout.addWidget(hero_card)

        compose_card = QFrame()
        compose_card.setObjectName("Card")
        compose_card.setProperty("variant", "accent")
        compose_layout = QVBoxLayout(compose_card)
        helper = QLabel("Follow-ups are limited to two attempts per recruiter and skip recruiters who already replied.")
        helper.setObjectName("Muted")
        compose_layout.addWidget(helper)

        compose_layout.addWidget(QLabel("Subject"))
        compose_layout.addWidget(self.subject_input)
        compose_layout.addWidget(QLabel("HTML Follow-Up Body"))
        self.body_editor.setMinimumHeight(180)
        compose_layout.addWidget(self.body_editor)

        action_row = QHBoxLayout()
        refresh_button = QPushButton("Refresh Due Follow-Ups")
        refresh_button.clicked.connect(self.refresh_data)
        save_button = QPushButton("Save Template")
        save_button.clicked.connect(lambda: self.save_draft(notify=True))
        send_selected_button = QPushButton("Send Selected")
        send_selected_button.clicked.connect(lambda: self.start_sending(selected_only=True))
        send_all_button = QPushButton("Send All Due")
        send_all_button.setObjectName("PrimaryButton")
        send_all_button.clicked.connect(lambda: self.start_sending(selected_only=False))
        stop_button = QPushButton("Stop")
        stop_button.setObjectName("DangerButton")
        stop_button.clicked.connect(self.stop_sending)
        self.stop_button = stop_button
        self.stop_button.setEnabled(False)
        action_row.addWidget(refresh_button)
        action_row.addWidget(save_button)
        action_row.addStretch(1)
        action_row.addWidget(send_selected_button)
        action_row.addWidget(send_all_button)
        action_row.addWidget(stop_button)
        compose_layout.addLayout(action_row)
        self.refresh_button = refresh_button
        self.save_button = save_button
        self.send_selected_button = send_selected_button
        self.send_all_button = send_all_button

        compose_layout.addWidget(self.progress_bar)
        self.status_label.setObjectName("Muted")
        compose_layout.addWidget(self.status_label)

        self.subject_input.textChanged.connect(self._mark_draft_dirty)
        self.body_editor.textChanged.connect(self._mark_draft_dirty)

        layout.addWidget(compose_card)

        table_card = QFrame()
        table_card.setObjectName("Card")
        table_card.setMinimumWidth(980)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(18, 18, 18, 18)
        table_layout.setSpacing(10)
        due_title = QLabel("Due Follow-Ups")
        due_title.setObjectName("SectionTitle")
        table_layout.addWidget(due_title)
        configure_table(
            self.table,
            ["Due", "Attempt", "Recruiter", "Company", "Email"],
            column_widths=[140, 92, 180, 160, 240],
        )
        table_layout.addWidget(self.table)
        layout.addWidget(table_card)
        layout.addStretch(1)

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
            self.subject_input.setText(settings.get("followup_subject", ""))
            self.body_editor.setPlainText(settings.get("followup_body_html", ""))
            self._draft_dirty = False
        finally:
            self._loading_draft = False

    def save_draft(self, notify: bool = True) -> None:
        self.context.database.save_settings(
            {
                "followup_subject": self.subject_input.text().strip(),
                "followup_body_html": self.body_editor.toPlainText(),
            }
        )
        self._draft_dirty = False
        if notify:
            self.context.bus.notification_requested.emit("Template Saved", "Follow-up template saved.", "success")

    def refresh_data(self) -> None:
        settings = self.current_settings()
        self._load_draft_fields(settings)
        self.followups = self.context.database.get_due_followups()
        set_table_rows(
            self.table,
            [
                [
                    format_timestamp(row["due_at"]),
                    f"#{row['attempt_number']}",
                    row["name"],
                    row["company"] or "-",
                    row["email"],
                ]
                for row in self.followups
            ],
        )
        self.progress_bar.setMaximum(max(len(self.followups), 1))
        self.progress_bar.setValue(0)
        self.status_label.setText(f"{len(self.followups)} follow-up(s) are currently due.")

    def _selected_followups(self) -> list[dict]:
        selected_rows = {index.row() for index in self.table.selectionModel().selectedRows()}
        return [self.followups[row_index] for row_index in sorted(selected_rows)]

    def start_sending(self, selected_only: bool) -> None:
        if self.worker and self.worker.isRunning():
            return
        subject = self.subject_input.text().strip()
        body_html = self.body_editor.toPlainText().strip()
        targets = self._selected_followups() if selected_only else self.followups
        if not targets:
            self.context.bus.notification_requested.emit("No Follow-Ups", "No follow-up rows were selected or due.", "error")
            return
        if not subject or not body_html:
            self.context.bus.notification_requested.emit("Missing Content", "Follow-up subject and body are required.", "error")
            return
        settings = self.current_settings()
        self.save_draft(notify=False)
        self.worker = BulkEmailWorker(
            mode="followup",
            targets=targets,
            subject=subject,
            body_html=body_html,
            attachments=[],
            settings=settings,
            database=self.context.database,
            email_service=self.context.email_service,
        )
        self.worker.progress_updated.connect(self.on_progress)
        self.worker.completed.connect(self.on_completed)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.worker.deleteLater)
        self.refresh_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.send_selected_button.setEnabled(False)
        self.send_all_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.worker.start()

    def stop_sending(self) -> None:
        if self.worker:
            self.worker.stop()
            self.status_label.setText("Stopping follow-up queue...")

    def on_progress(self, current: int, total: int, message: str) -> None:
        if current >= 0 and total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        self.status_label.setText(message)

    def on_completed(self, summary: dict) -> None:
        self.worker = None
        self.refresh_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.send_selected_button.setEnabled(True)
        self.send_all_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.context.bus.logs_updated.emit()
        self.context.bus.recruiters_updated.emit()
        self.context.bus.followups_updated.emit()
        self.context.bus.stats_updated.emit()
        self.refresh_data()
        self.context.bus.notification_requested.emit(
            "Follow-Up Queue Finished",
            f"Sent {summary['sent']}, failed {summary['failed']}, skipped {summary['skipped']}.",
            "success" if summary["failed"] == 0 else "error",
        )

    def on_failed(self, message: str) -> None:
        self.worker = None
        self.refresh_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.send_selected_button.setEnabled(True)
        self.send_all_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.context.bus.logs_updated.emit()
        self.context.bus.recruiters_updated.emit()
        self.context.bus.followups_updated.emit()
        self.context.bus.stats_updated.emit()
        self.refresh_data()
        self.context.bus.notification_requested.emit("Follow-Up Failed", message, "error")

    def shutdown(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
