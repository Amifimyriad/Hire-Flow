from __future__ import annotations

from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
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
        self.tables_host = QWidget()
        self.tables_layout = QGridLayout()
        self._table_columns = 0
        self._build_ui()
        self.context.bus.recruiters_updated.connect(self.refresh_data)
        self.refresh_data()

    def _build_ui(self) -> None:
        self.setMinimumWidth(1040)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        hero_card = QFrame()
        hero_card.setObjectName("Card")
        hero_card.setProperty("variant", "hero")
        hero_layout = QVBoxLayout(hero_card)
        eyebrow = QLabel("Pipeline")
        eyebrow.setObjectName("Eyebrow")
        title = QLabel("Import, parse, and maintain a recruiter pipeline built for real outbound work.")
        title.setObjectName("SectionTitle")
        body = QLabel("Preview incoming data, repair invalid records, and keep the active recruiter table readable at a glance.")
        body.setObjectName("HeroBody")
        body.setWordWrap(True)
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(body)
        layout.addWidget(hero_card)

        actions_card = QFrame()
        actions_card.setObjectName("Card")
        actions_card.setProperty("variant", "accent")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(18, 18, 18, 18)
        actions_layout.setSpacing(14)

        actions_row = QHBoxLayout()
        upload_button = QPushButton("Upload CSV / XLSX")
        upload_button.setObjectName("PrimaryButton")
        upload_button.clicked.connect(self.upload_file)
        parse_button = QPushButton("Parse Emails")
        parse_button.clicked.connect(self.parse_emails)
        self.import_button.clicked.connect(self.import_recruiters)
        self.import_button.setEnabled(False)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_data)
        actions_row.addWidget(upload_button)
        actions_row.addWidget(parse_button)
        actions_row.addWidget(self.import_button)
        actions_row.addStretch(1)
        actions_row.addWidget(refresh_button)
        actions_layout.addLayout(actions_row)

        prompt = QLabel("Paste recruiter emails to generate `sample_recruiters.csv` with inferred names and companies.")
        prompt.setObjectName("Muted")
        actions_layout.addWidget(prompt)
        self.email_input.setPlaceholderText("recruit@excelcorp.com\njobs@acme.ai")
        self.email_input.setMaximumHeight(112)
        actions_layout.addWidget(self.email_input)
        layout.addWidget(actions_card)

        summary_card = QFrame()
        summary_card.setObjectName("Card")
        summary_card.setProperty("variant", "subtle")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(16, 14, 16, 14)
        summary_layout.setSpacing(6)
        summary_label = QLabel("Import Summary")
        summary_label.setObjectName("Eyebrow")
        self.preview_summary.setWordWrap(True)
        self.preview_summary.setObjectName("Muted")
        summary_layout.addWidget(summary_label)
        summary_layout.addWidget(self.preview_summary)
        layout.addWidget(summary_card)

        self.preview_card = QFrame()
        self.preview_card.setObjectName("Card")
        preview_layout = QVBoxLayout(self.preview_card)
        preview_layout.setContentsMargins(18, 18, 18, 18)
        preview_layout.setSpacing(10)
        preview_title = QLabel("Import Preview")
        preview_title.setObjectName("SectionTitle")
        preview_layout.addWidget(preview_title)
        configure_table(
            self.preview_table,
            ["Row", "Name", "Company", "Email", "Validation"],
            column_widths=[82, 170, 170, 240, 220],
        )
        preview_layout.addWidget(self.preview_table)

        self.recruiters_card = QFrame()
        self.recruiters_card.setObjectName("Card")
        recruiters_layout = QVBoxLayout(self.recruiters_card)
        recruiters_layout.setContentsMargins(18, 18, 18, 18)
        recruiters_layout.setSpacing(10)
        imported_title = QLabel("Imported Recruiters")
        imported_title.setObjectName("SectionTitle")
        recruiters_layout.addWidget(imported_title)
        configure_table(
            self.recruiters_table,
            ["Name", "Company", "Email", "Initial", "Reply", "Follow-Ups", "Updated"],
            column_widths=[180, 160, 250, 90, 90, 110, 150],
        )
        recruiters_layout.addWidget(self.recruiters_table)

        self.tables_layout.setContentsMargins(0, 0, 0, 0)
        self.tables_layout.setHorizontalSpacing(18)
        self.tables_layout.setVerticalSpacing(18)
        self.tables_host.setLayout(self.tables_layout)
        layout.addWidget(self.tables_host)
        layout.addStretch(1)
        self._apply_table_layout()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_table_layout()

    def _apply_table_layout(self) -> None:
        columns = 2 if self.width() >= 1560 else 1
        if columns == self._table_columns:
            return
        self._table_columns = columns
        while self.tables_layout.count():
            item = self.tables_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        cards = [self.preview_card, self.recruiters_card]
        for index, card in enumerate(cards):
            self.tables_layout.addWidget(card, index // columns, index % columns)
            card.show()

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
                    "Sent" if row["initial_sent"] else "Pending",
                    "Yes" if row["reply_status"] else "No",
                    str(row["followup_count"]),
                    format_timestamp(row["updated_at"]),
                ]
                for row in recruiters
            ],
        )
