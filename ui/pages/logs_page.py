from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.table_utils import configure_table, format_timestamp, set_table_rows


class LogsPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.status_filter = QComboBox()
        self.type_filter = QComboBox()
        self.table = QTableWidget()
        self.app_log_viewer = QPlainTextEdit()
        self._build_ui()
        self.context.bus.logs_updated.connect(self.refresh_data)
        self.refresh_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        self.setMinimumWidth(1440)

        hero_card = QFrame()
        hero_card.setObjectName("Card")
        hero_card.setProperty("variant", "hero")
        hero_layout = QVBoxLayout(hero_card)
        eyebrow = QLabel("Audit")
        eyebrow.setObjectName("Eyebrow")
        title = QLabel("Inspect delivery history and runtime health.")
        title.setObjectName("SectionTitle")
        body = QLabel("Filter events, export diagnostics, and review the local application log.")
        body.setObjectName("HeroBody")
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(body)
        layout.addWidget(hero_card)

        actions = QHBoxLayout()
        self.status_filter.addItems(["all", "sent", "failed"])
        self.type_filter.addItems(["all", "initial", "followup"])
        self.status_filter.currentTextChanged.connect(self.refresh_data)
        self.type_filter.currentTextChanged.connect(self.refresh_data)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_data)
        export_button = QPushButton("Export Logs")
        export_button.clicked.connect(self.export_logs)
        actions.addWidget(QLabel("Status"))
        actions.addWidget(self.status_filter)
        actions.addWidget(QLabel("Email Type"))
        actions.addWidget(self.type_filter)
        actions.addStretch(1)
        actions.addWidget(refresh_button)
        actions.addWidget(export_button)
        layout.addLayout(actions)

        tabs = QTabWidget()

        email_logs_card = QFrame()
        email_logs_card.setObjectName("Card")
        email_logs_layout = QVBoxLayout(email_logs_card)
        email_logs_layout.setContentsMargins(18, 18, 18, 18)
        email_logs_layout.setSpacing(10)
        email_logs_title = QLabel("Email Logs")
        email_logs_title.setObjectName("SectionTitle")
        email_logs_layout.addWidget(email_logs_title)
        configure_table(
            self.table,
            ["When", "Type", "Recruiter", "Company", "Email", "Status", "Attempts", "Error"],
            column_widths=[132, 90, 180, 160, 230, 100, 90, 280],
        )
        email_logs_layout.addWidget(self.table)
        tabs.addTab(email_logs_card, "Email Logs")

        app_logs_card = QFrame()
        app_logs_card.setObjectName("Card")
        app_logs_layout = QVBoxLayout(app_logs_card)
        app_logs_layout.setContentsMargins(18, 18, 18, 18)
        app_logs_layout.setSpacing(10)
        app_logs_title = QLabel("Application Log")
        app_logs_title.setObjectName("SectionTitle")
        app_logs_layout.addWidget(app_logs_title)
        self.app_log_viewer.setReadOnly(True)
        app_logs_layout.addWidget(self.app_log_viewer)
        tabs.addTab(app_logs_card, "Application Log")

        layout.addWidget(tabs, 1)
        layout.addStretch(1)

    def refresh_data(self) -> None:
        rows = self.context.database.list_logs(
            status=self.status_filter.currentText(),
            email_type=self.type_filter.currentText(),
        )
        set_table_rows(
            self.table,
            [
                [
                    format_timestamp(row["sent_at"] or row["created_at"]),
                    row["email_type"].title(),
                    row["recruiter_name"] or "-",
                    row["company"] or "-",
                    row["recruiter_email"],
                    row["status"].title(),
                    str(row["attempt_count"]),
                    row["error_message"] or "-",
                ]
                for row in rows
            ],
        )
        self.app_log_viewer.setPlainText(self.context.logger.tail())

    def export_logs(self) -> None:
        default_path = Path.home() / "hireflow_logs.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export logs",
            str(default_path),
            "CSV Files (*.csv)",
        )
        if not file_path:
            return
        self.context.database.export_logs(
            Path(file_path),
            status=self.status_filter.currentText(),
            email_type=self.type_filter.currentText(),
        )
        self.context.bus.notification_requested.emit("Logs Exported", f"Saved logs to {file_path}", "success")
