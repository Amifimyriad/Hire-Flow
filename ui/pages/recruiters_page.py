from __future__ import annotations

from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.table_utils import configure_table, format_timestamp, set_table_rows


class RecruitersPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.preview_data = None
        self.preview_summary = QLabel("Upload a CSV or Excel file to preview recruiter data before import.")
        self.email_input = QPlainTextEdit()
        self.preview_table = QTableWidget()
        self.recruiters_table = QTableWidget()
        self.import_button = QPushButton("Import Valid Recruiters")
        self._build_ui()
        self.context.bus.recruiters_updated.connect(self.refresh_data)
        self.refresh_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        hero_card = QFrame()
        hero_card.setObjectName("Card")
        hero_layout = QVBoxLayout(hero_card)
        eyebrow = QLabel("Pipeline")
        eyebrow.setObjectName("Eyebrow")
        title = QLabel("Import, parse, and maintain a polished recruiter list.")
        title.setObjectName("SectionTitle")
        body = QLabel("Blend file import with quick email parsing to keep your workspace populated and clean.")
        body.setObjectName("HeroBody")
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(body)
        layout.addWidget(hero_card)

        actions = QHBoxLayout()
        upload_button = QPushButton("Upload CSV / XLSX")
        upload_button.setObjectName("PrimaryButton")
        upload_button.clicked.connect(self.upload_file)
        parse_button = QPushButton("Parse Emails")
        parse_button.clicked.connect(self.parse_emails)
        self.import_button.clicked.connect(self.import_recruiters)
        self.import_button.setEnabled(False)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_data)
        actions.addWidget(upload_button)
        actions.addWidget(parse_button)
        actions.addWidget(self.import_button)
        actions.addStretch(1)
        actions.addWidget(refresh_button)
        layout.addLayout(actions)

        email_card = QFrame()
        email_card.setObjectName("Card")
        email_layout = QVBoxLayout(email_card)
        email_layout.addWidget(QLabel("Paste recruiter emails to auto-generate sample_recruiters.csv"))
        self.email_input.setPlaceholderText("recruit@excelcorp.com\njobs@acme.ai")
        self.email_input.setMaximumHeight(90)
        email_layout.addWidget(self.email_input)
        layout.addWidget(email_card)

        self.preview_summary.setObjectName("Muted")
        layout.addWidget(self.preview_summary)

        splitter = QSplitter()

        preview_card = QFrame()
        preview_card.setObjectName("Card")
        preview_layout = QVBoxLayout(preview_card)
        preview_title = QLabel("Import Preview")
        preview_title.setObjectName("SectionTitle")
        preview_layout.addWidget(preview_title)
        configure_table(
            self.preview_table,
            ["Row", "Name", "Company", "Email", "Validation"],
        )
        preview_layout.addWidget(self.preview_table)

        recruiters_card = QFrame()
        recruiters_card.setObjectName("Card")
        recruiters_layout = QVBoxLayout(recruiters_card)
        imported_title = QLabel("Imported Recruiters")
        imported_title.setObjectName("SectionTitle")
        recruiters_layout.addWidget(imported_title)
        configure_table(
            self.recruiters_table,
            ["Name", "Company", "Email", "Initial Sent", "Reply", "Follow-Ups", "Updated"],
        )
        recruiters_layout.addWidget(self.recruiters_table)

        splitter.addWidget(preview_card)
        splitter.addWidget(recruiters_card)
        splitter.setSizes([650, 750])
        layout.addWidget(splitter, 1)

    def upload_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select recruiter file",
            str(self.context.config.paths.samples_dir),
            "Recruiter Files (*.csv *.xlsx *.xls)",
        )
        if not file_path:
            return
        try:
            self.preview_data = self.context.recruiter_files.load_preview(file_path)
            valid_count = len(self.preview_data.valid_rows)
            invalid_count = len(self.preview_data.invalid_rows)
            self.preview_summary.setText(
                f"Loaded {self.preview_data.source_file}: {valid_count} valid row(s), {invalid_count} invalid row(s)."
            )
            set_table_rows(
                self.preview_table,
                [
                    [
                        row["row_number"],
                        row["name"],
                        row["company"] or "-",
                        row["email"] or "-",
                        row["validation_error"] or "Valid",
                    ]
                    for row in self.preview_data.preview_rows
                ],
            )
            self.import_button.setEnabled(valid_count > 0)
        except Exception as exc:
            self.context.bus.notification_requested.emit("Import Failed", str(exc), "error")

    def import_recruiters(self) -> None:
        if not self.preview_data:
            return
        inserted, updated = self.context.database.import_recruiters(
            recruiters=self.preview_data.valid_rows,
            source_file=self.preview_data.source_file,
        )
        self.context.bus.notification_requested.emit(
            "Recruiters Imported",
            f"Inserted {inserted} and updated {updated} recruiter record(s).",
            "success",
        )
        self.context.bus.recruiters_updated.emit()
        self.context.bus.stats_updated.emit()
        self.import_button.setEnabled(False)

    def parse_emails(self) -> None:
        raw_text = self.email_input.toPlainText().strip()
        if not raw_text:
            self.context.bus.notification_requested.emit("No Emails", "Paste recruiter emails first.", "error")
            return
        try:
            self.preview_data = self.context.recruiter_files.build_preview_from_emails(raw_text)
            destination = self.context.config.paths.samples_dir / "sample_recruiters.csv"
            self.context.recruiter_files.save_parsed_csv(destination, self.preview_data.valid_rows)
            self.preview_summary.setText(
                f"Generated {destination.name}: {len(self.preview_data.valid_rows)} valid row(s), "
                f"{len(self.preview_data.invalid_rows)} invalid row(s)."
            )
            set_table_rows(
                self.preview_table,
                [
                    [
                        row["row_number"],
                        row["name"],
                        row["company"] or "-",
                        row["email"] or "-",
                        row["validation_error"] or "Valid",
                    ]
                    for row in self.preview_data.preview_rows
                ],
            )
            self.import_button.setEnabled(bool(self.preview_data.valid_rows))
            self.context.bus.notification_requested.emit(
                "CSV Generated",
                f"Saved parsed recruiters to {destination.name}.",
                "success",
            )
        except Exception as exc:
            self.context.bus.notification_requested.emit("Parse Failed", str(exc), "error")

    def refresh_data(self) -> None:
        recruiters = self.context.database.get_recruiters()
        set_table_rows(
            self.recruiters_table,
            [
                [
                    row["name"],
                    row["company"] or "-",
                    row["email"],
                    "Yes" if row["initial_sent"] else "No",
                    "Yes" if row["reply_status"] else "No",
                    str(row["followup_count"]),
                    format_timestamp(row["updated_at"]),
                ]
                for row in recruiters
            ],
        )
        self.recruiters_table.resizeColumnsToContents()
