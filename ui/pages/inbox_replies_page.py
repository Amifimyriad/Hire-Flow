from __future__ import annotations

from html import escape
from urllib.parse import quote

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.workers import SingleReplyWorker
from services.template_service import render_template
from ui.widgets.table_utils import configure_table, format_timestamp


class InboxRepliesPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.rows: list[dict] = []
        self.filtered_rows: list[dict] = []
        self.reply_worker = None
        self.current_row: dict | None = None
        self.search_input = QLineEdit()
        self.filter_box = QComboBox()
        self.table = QTableWidget()
        self.thread_view = QTextBrowser()
        self.notes_editor = QTextEdit()
        self.reply_subject = QLineEdit()
        self.reply_body = QTextEdit()
        self.status_label = QLabel("Select a recruiter reply.")
        self.thread_count_label = QLabel("0 threads")
        self.new_count_label = QLabel("0 new")
        self.interested_count_label = QLabel("0 interested")
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.detail_splitter = QSplitter(Qt.Orientation.Vertical)
        self._build_ui()
        self.context.bus.replies_updated.connect(self.refresh_data)
        self.context.bus.logs_updated.connect(self.refresh_data)
        self.refresh_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        self.setMinimumWidth(1360)

        hero_card = QFrame()
        hero_card.setObjectName("Card")
        hero_card.setProperty("variant", "hero")
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(22, 20, 22, 20)
        hero_layout.setSpacing(16)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(6)
        eyebrow = QLabel("Inbox")
        eyebrow.setObjectName("Eyebrow")
        title = QLabel("Recruiter conversations, notes, and replies in one Linear-style workspace.")
        title.setObjectName("SectionTitle")
        body = QLabel("Search threads, scan statuses, update notes, and send replies without losing context.")
        body.setObjectName("HeroBody")
        body.setWordWrap(True)
        hero_copy.addWidget(eyebrow)
        hero_copy.addWidget(title)
        hero_copy.addWidget(body)

        stat_row = QHBoxLayout()
        for label in [self.thread_count_label, self.new_count_label, self.interested_count_label]:
            label.setObjectName("Pill")
            stat_row.addWidget(label)
        stat_row.addStretch(1)
        hero_copy.addLayout(stat_row)

        hero_layout.addLayout(hero_copy, 1)
        layout.addWidget(hero_card)

        thread_card = QFrame()
        thread_card.setObjectName("Card")
        thread_card.setMinimumWidth(520)
        thread_card.setMaximumWidth(620)
        thread_layout = QVBoxLayout(thread_card)
        thread_layout.setContentsMargins(18, 18, 18, 18)
        thread_layout.setSpacing(12)

        thread_header = QHBoxLayout()
        thread_title = QLabel("Threads")
        thread_title.setObjectName("SectionTitle")
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_data)
        thread_header.addWidget(thread_title)
        thread_header.addStretch(1)
        thread_header.addWidget(refresh_button)
        thread_layout.addLayout(thread_header)

        toolbar = QHBoxLayout()
        self.search_input.setPlaceholderText("Search recruiter, company, email, subject...")
        self.search_input.textChanged.connect(self.apply_filters)
        self.filter_box.addItems(["all", "new", "replied", "completed", "interested", "not_interested"])
        self.filter_box.currentTextChanged.connect(self.apply_filters)
        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.filter_box)
        thread_layout.addLayout(toolbar)

        configure_table(
            self.table,
            ["Recruiter", "Company", "Latest", "Received", "Status"],
            column_widths=[180, 160, 280, 132, 150],
        )
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        thread_layout.addWidget(self.table)

        detail_card = QFrame()
        detail_card.setObjectName("Card")
        detail_card.setProperty("variant", "accent")
        detail_card.setMinimumWidth(820)
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(18, 18, 18, 18)
        detail_layout.setSpacing(12)

        detail_header = QHBoxLayout()
        header_copy = QVBoxLayout()
        header_copy.setSpacing(6)
        conversation_title = QLabel("Conversation")
        conversation_title.setObjectName("SectionTitle")
        self.status_label.setObjectName("Muted")
        self.status_label.setWordWrap(True)
        header_copy.addWidget(conversation_title)
        header_copy.addWidget(self.status_label)
        detail_header.addLayout(header_copy, 1)
        detail_layout.addLayout(detail_header)

        action_row = QHBoxLayout()
        manual_button = QPushButton("Manual Draft")
        manual_button.clicked.connect(self.prepare_manual_reply)
        auto_button = QPushButton("Quick Reply")
        auto_button.clicked.connect(self.auto_reply)
        gmail_button = QPushButton("Open Gmail")
        gmail_button.clicked.connect(self.open_gmail_thread)
        completed_button = QPushButton("Complete")
        completed_button.clicked.connect(lambda: self.update_state(status="completed"))
        interested_button = QPushButton("Interested")
        interested_button.clicked.connect(lambda: self.update_state(interest_status="interested"))
        not_interested_button = QPushButton("Declined")
        not_interested_button.clicked.connect(lambda: self.update_state(interest_status="not_interested"))
        archive_button = QPushButton("Archive")
        archive_button.clicked.connect(lambda: self.update_state(archived=1))
        self.manual_button = manual_button
        self.auto_button = auto_button
        self.gmail_button = gmail_button
        self.completed_button = completed_button
        self.interested_button = interested_button
        self.not_interested_button = not_interested_button
        self.archive_button = archive_button
        for widget in [
            manual_button,
            auto_button,
            gmail_button,
            completed_button,
            interested_button,
            not_interested_button,
            archive_button,
        ]:
            action_row.addWidget(widget)
        action_row.addStretch(1)
        detail_layout.addLayout(action_row)

        conversation_card = QFrame()
        conversation_card.setObjectName("Card")
        conversation_card.setProperty("variant", "subtle")
        conversation_card.setMinimumHeight(300)
        conversation_layout = QVBoxLayout(conversation_card)
        conversation_layout.setContentsMargins(14, 14, 14, 14)
        conversation_layout.setSpacing(10)
        conversation_label = QLabel("Full Thread")
        conversation_label.setObjectName("Eyebrow")
        self.thread_view.setOpenExternalLinks(True)
        conversation_layout.addWidget(conversation_label)
        conversation_layout.addWidget(self.thread_view)

        composer_card = QFrame()
        composer_card.setObjectName("Card")
        composer_card.setMinimumHeight(340)
        composer_layout = QVBoxLayout(composer_card)
        composer_layout.setContentsMargins(16, 16, 16, 16)
        composer_layout.setSpacing(10)
        notes_label = QLabel("Notes / Comments")
        notes_label.setObjectName("Eyebrow")
        composer_layout.addWidget(notes_label)
        self.notes_editor.setMaximumHeight(110)
        composer_layout.addWidget(self.notes_editor)

        subject_label = QLabel("Reply Subject")
        subject_label.setObjectName("Eyebrow")
        composer_layout.addWidget(subject_label)
        composer_layout.addWidget(self.reply_subject)

        body_label = QLabel("Reply Body")
        body_label.setObjectName("Eyebrow")
        composer_layout.addWidget(body_label)
        self.reply_body.setMinimumHeight(180)
        composer_layout.addWidget(self.reply_body, 1)

        composer_actions = QHBoxLayout()
        save_notes_button = QPushButton("Save Notes")
        save_notes_button.clicked.connect(self.save_notes)
        send_button = QPushButton("Send Reply")
        send_button.setObjectName("PrimaryButton")
        send_button.clicked.connect(self.send_reply)
        self.save_notes_button = save_notes_button
        self.send_button = send_button
        composer_actions.addWidget(save_notes_button)
        composer_actions.addStretch(1)
        composer_actions.addWidget(send_button)
        composer_layout.addLayout(composer_actions)

        self.detail_splitter.addWidget(conversation_card)
        self.detail_splitter.addWidget(composer_card)
        self.detail_splitter.setChildrenCollapsible(False)
        self.detail_splitter.setStretchFactor(0, 1)
        self.detail_splitter.setStretchFactor(1, 1)
        self.detail_splitter.setSizes([440, 320])
        detail_layout.addWidget(self.detail_splitter, 1)

        self.main_splitter.addWidget(thread_card)
        self.main_splitter.addWidget(detail_card)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([620, 960])
        layout.addWidget(self.main_splitter, 1)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search_input.setFocus)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self.send_reply)
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, activated=self.refresh_data)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)

    def refresh_data(self) -> None:
        self.rows = self.context.database.list_inbox_replies()
        new_count = sum(1 for row in self.rows if row["status"] == "new")
        interested_count = sum(1 for row in self.rows if row["interest_status"] == "interested")
        self.thread_count_label.setText(f"{len(self.rows)} threads")
        self.new_count_label.setText(f"{new_count} new")
        self.interested_count_label.setText(f"{interested_count} interested")
        self.apply_filters()

    def apply_filters(self) -> None:
        query = self.search_input.text().strip().lower()
        selected_filter = self.filter_box.currentText()
        rows = []
        for row in self.rows:
            haystack = " ".join(
                [
                    row["name"],
                    row["company"] or "",
                    row["email"],
                    row["latest_subject"] or "",
                    row["latest_preview"] or "",
                ]
            ).lower()
            if query and query not in haystack:
                continue
            if selected_filter == "new" and row["status"] != "new":
                continue
            if selected_filter == "replied" and row["status"] != "replied":
                continue
            if selected_filter == "completed" and row["status"] != "completed":
                continue
            if selected_filter == "interested" and row["interest_status"] != "interested":
                continue
            if selected_filter == "not_interested" and row["interest_status"] != "not_interested":
                continue
            rows.append(row)
        self.filtered_rows = rows
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            status = row["status"]
            interest = row["interest_status"]
            name = row["name"] if status != "new" else f"{row['name']}  NEW"
            values = [
                name,
                row["company"] or "-",
                (row["latest_subject"] or row["latest_preview"] or "-")[:86],
                format_timestamp(row["last_received_at"]),
                f"{status} / {interest}",
            ]
            for column_index, value in enumerate(values):
                self.table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
        if rows:
            self.select_row(0)
        else:
            self.current_row = None
            self.thread_view.setHtml("<div style='padding:24px;'>No replies match the current filter.</div>")
            self.notes_editor.clear()
            self.reply_subject.clear()
            self.reply_body.clear()
            self.status_label.setText("No inbox replies found.")

    def select_row(self, row_index: int) -> None:
        if row_index < 0 or row_index >= len(self.filtered_rows):
            return
        self.table.selectRow(row_index)
        self.on_selection_changed()

    def on_selection_changed(self) -> None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes or not self.filtered_rows:
            return
        self.current_row = self.filtered_rows[indexes[0].row()]
        messages = self.context.database.get_conversation_messages(int(self.current_row["recruiter_id"]))
        self.thread_view.setHtml(self._build_thread_html(messages))
        self.notes_editor.setPlainText(self.current_row.get("notes", ""))
        latest_subject = self.current_row["latest_subject"] or ""
        self.reply_subject.setText(f"Re: {latest_subject}".strip())
        self.reply_body.setPlainText("")
        self.status_label.setText(
            f"{self.current_row['name']}  •  {self.current_row['email']}  •  "
            f"{self.current_row['status']}  •  {self.current_row['interest_status']}"
        )

    def _build_thread_html(self, messages: list[dict]) -> str:
        if not messages:
            return "<div style='padding:24px;'>No thread history.</div>"
        bubbles = []
        for message in messages:
            timestamp = message["received_at"] or message["sent_at"] or message["created_at"]
            direction = message["direction"].title()
            tone = "#5AA2FF" if message["direction"] == "outbound" else "#9DB2D0"
            subject = escape(message["subject"] or "(No Subject)")
            body = escape(message["body_text"] or "").replace("\n", "<br>")
            html_body = message["body_html"] or ""
            content = html_body if html_body else body
            bubbles.append(
                f"""
                <div style="margin:0 0 14px 0; padding:14px 16px; border-radius:18px;
                            background:rgba(255,255,255,0.05); border:1px solid rgba(145,170,210,0.16);">
                    <div style="font-size:12px; font-weight:700; color:{tone}; margin-bottom:6px;">{direction}</div>
                    <div style="font-size:12px; color:#90A1BE; margin-bottom:8px;">{escape(format_timestamp(timestamp))}</div>
                    <div style="font-size:14px; font-weight:700; color:#F4F8FF; margin-bottom:8px;">{subject}</div>
                    <div style="font-size:13px; line-height:1.55; color:#D5E0F5;">{content}</div>
                </div>
                """
            )
        return (
            "<div style='font-family:-apple-system, SF Pro Display, Segoe UI, sans-serif; padding:8px;'>"
            + "".join(bubbles)
            + "</div>"
        )

    def _selected_recruiter(self) -> dict | None:
        if not self.current_row:
            self.context.bus.notification_requested.emit("No Reply Selected", "Select an inbox reply first.", "error")
            return None
        return {
            "id": int(self.current_row["recruiter_id"]),
            "name": self.current_row["name"],
            "company": self.current_row["company"],
            "email": self.current_row["email"],
        }

    def _thread_headers(self) -> dict[str, str]:
        recruiter = self._selected_recruiter()
        if recruiter is None:
            return {}
        latest = self.context.database.get_latest_conversation_message(recruiter["id"]) or {}
        latest_message_id = (latest.get("external_message_id") or self.current_row.get("latest_message_id") or "").strip()
        references = " ".join(
            part
            for part in [(latest.get("references_header") or "").strip(), latest_message_id]
            if part
        ).strip()
        return {"In-Reply-To": latest_message_id, "References": references}

    def prepare_manual_reply(self) -> None:
        recruiter = self._selected_recruiter()
        if recruiter is None:
            return
        settings = self.context.database.get_settings()
        self.reply_subject.setText(f"Re: {self.current_row['latest_subject']}".strip())
        self.reply_body.setHtml(
            render_template(
                "<p>Hi {{recruiter_name}},</p><p>Thank you for your reply.</p><p></p>{{signature_html}}",
                {
                    "recruiter_name": recruiter["name"],
                    "company": recruiter["company"],
                    "signature_html": settings.get("signature_html", ""),
                },
            )
        )

    def auto_reply(self) -> None:
        recruiter = self._selected_recruiter()
        if recruiter is None:
            return
        settings = self.context.database.get_settings()
        company = recruiter["company"] or "your team"
        self.reply_subject.setText(f"Re: {self.current_row['latest_subject']}".strip())
        self.reply_body.setHtml(
            render_template(
                (
                    "<p>Hi {{recruiter_name}},</p>"
                    "<p>Thank you for your reply. I'm interested in continuing the conversation about roles with {{company}}.</p>"
                    "<p>Please share the next steps and any suitable time slots.</p>"
                    "{{signature_html}}"
                ),
                {
                    "recruiter_name": recruiter["name"],
                    "company": company,
                    "signature_html": settings.get("signature_html", ""),
                },
            )
        )

    def send_reply(self) -> None:
        recruiter = self._selected_recruiter()
        if recruiter is None or (self.reply_worker and self.reply_worker.isRunning()):
            return
        subject = self.reply_subject.text().strip()
        body_html = self.reply_body.toHtml().strip()
        if not subject or not body_html:
            self.context.bus.notification_requested.emit("Missing Reply", "Reply subject and body are required.", "error")
            return
        mode = "auto_reply" if "Thank you for your reply" in self.reply_body.toPlainText() else "manual_reply"
        self.reply_worker = SingleReplyWorker(
            recruiter=recruiter,
            subject=subject,
            body_html=body_html,
            mode=mode,
            settings=self.context.database.get_settings(),
            thread_headers=self._thread_headers(),
            database=self.context.database,
            email_service=self.context.email_service,
        )
        self._set_busy(True)
        self.reply_worker.completed.connect(self._reply_completed)
        self.reply_worker.failed.connect(self._reply_failed)
        self.reply_worker.finished.connect(self.reply_worker.deleteLater)
        self.reply_worker.start()

    def _reply_completed(self, payload: dict) -> None:
        self.reply_worker = None
        recruiter = self._selected_recruiter()
        if recruiter:
            self.context.database.update_inbox_reply_state(recruiter["id"], status="replied")
        self._set_busy(False)
        self.context.bus.logs_updated.emit()
        self.context.bus.replies_updated.emit()
        self.context.bus.notification_requested.emit("Reply Sent", f"Reply sent at {payload['sent_at']}.", "success")

    def _reply_failed(self, message: str) -> None:
        self.reply_worker = None
        self._set_busy(False)
        self.context.bus.notification_requested.emit("Reply Failed", message, "error")

    def _set_busy(self, busy: bool) -> None:
        for button in [
            self.send_button,
            self.manual_button,
            self.auto_button,
            self.gmail_button,
            self.completed_button,
            self.interested_button,
            self.not_interested_button,
            self.archive_button,
            self.save_notes_button,
        ]:
            button.setEnabled(not busy)

    def update_state(self, *, status: str | None = None, interest_status: str | None = None, archived: int | None = None) -> None:
        recruiter = self._selected_recruiter()
        if recruiter is None:
            return
        self.context.database.update_inbox_reply_state(
            recruiter["id"],
            status=status,
            interest_status=interest_status,
            archived=archived,
        )
        self.context.bus.replies_updated.emit()

    def save_notes(self) -> None:
        recruiter = self._selected_recruiter()
        if recruiter is None:
            return
        self.context.database.update_inbox_reply_state(recruiter["id"], notes=self.notes_editor.toPlainText().strip())
        self.context.bus.replies_updated.emit()
        self.context.bus.notification_requested.emit("Notes Saved", "Reply notes updated.", "success")

    def open_gmail_thread(self) -> None:
        recruiter = self._selected_recruiter()
        if recruiter is None:
            return
        latest_message_id = (self.current_row.get("latest_message_id") or "").strip()
        url = (
            f"https://mail.google.com/mail/u/0/#search/rfc822msgid%3A{quote(latest_message_id)}"
            if latest_message_id
            else f"https://mail.google.com/mail/u/0/#search/{quote(recruiter['email'])}"
        )
        QDesktopServices.openUrl(QUrl(url))

    def shutdown(self) -> None:
        if self.reply_worker and self.reply_worker.isRunning():
            self.reply_worker.wait(5000)
