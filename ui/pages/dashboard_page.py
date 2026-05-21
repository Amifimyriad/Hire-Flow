from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.stat_card import StatCard
from ui.widgets.table_utils import configure_table, format_timestamp, set_table_rows


class DashboardPage(QWidget):
    def __init__(self, context, sync_callback):
        super().__init__()
        self.context = context
        self.sync_callback = sync_callback
        self.cards: dict[str, StatCard] = {}
        self.card_specs = [
            ("sent_total", "Total Emails Sent", "0", "All successful outreach emails.", "Delivery"),
            ("replies_received", "Replies Received", "0", "Recruiter replies detected through IMAP.", "Inbox"),
            ("pending_followups", "Pending Follow-Ups", "0", "Follow-ups currently due for action.", "Queue"),
            ("failed_emails", "Failed Emails", "0", "Messages that exhausted retries.", "Risk"),
            ("followups_sent", "Follow-Ups Sent", "0", "Successful reminder emails.", "Cadence"),
        ]
        self.activity_table = QTableWidget()
        self.followup_table = QTableWidget()
        self.reply_table = QTableWidget()
        self.cards_layout = QGridLayout()
        self.cards_host = QWidget()
        self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._build_ui()
        self.context.bus.stats_updated.connect(self.refresh_data)
        self.context.bus.logs_updated.connect(self.refresh_data)
        self.context.bus.followups_updated.connect(self.refresh_data)
        self.context.bus.replies_updated.connect(self.refresh_data)
        self.refresh_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        self.setMinimumWidth(1320)

        hero_card = QFrame()
        hero_card.setObjectName("Card")
        hero_card.setProperty("variant", "hero")
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(22, 20, 22, 20)
        hero_layout.setSpacing(16)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(6)
        eyebrow = QLabel("Overview")
        eyebrow.setObjectName("Eyebrow")
        intro = QLabel("Command your outreach pipeline with clearer signals and faster triage.")
        intro.setObjectName("SectionTitle")
        caption = QLabel("Monitor sends, pressure from due follow-ups, and recruiter conversations without losing density.")
        caption.setObjectName("HeroBody")
        caption.setWordWrap(True)
        hero_copy.addWidget(eyebrow)
        hero_copy.addWidget(intro)
        hero_copy.addWidget(caption)

        hero_actions = QHBoxLayout()
        hero_actions.addStretch(1)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_data)
        sync_button = QPushButton("Sync Inbox Replies")
        sync_button.setObjectName("PrimaryButton")
        sync_button.clicked.connect(self.sync_callback)
        hero_actions.addWidget(refresh_button)
        hero_actions.addWidget(sync_button)

        hero_layout.addLayout(hero_copy, 1)
        hero_layout.addLayout(hero_actions)
        layout.addWidget(hero_card)

        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setHorizontalSpacing(14)
        self.cards_layout.setVerticalSpacing(14)
        self.cards_host.setLayout(self.cards_layout)
        for key, title, value, subtitle, detail in self.card_specs:
            card = StatCard(title, value, subtitle, detail=detail)
            card.setMinimumWidth(340)
            self.cards[key] = card
        self._relayout_cards()
        layout.addWidget(self.cards_host)

        activity_card = QFrame()
        activity_card.setObjectName("Card")
        activity_card.setMinimumWidth(700)
        activity_layout = QVBoxLayout(activity_card)
        activity_layout.setContentsMargins(18, 18, 18, 18)
        activity_layout.setSpacing(10)
        title = QLabel("Recent Activity")
        title.setObjectName("SectionTitle")
        summary = QLabel("Latest delivery events with status visibility.")
        summary.setObjectName("Muted")
        activity_layout.addWidget(title)
        activity_layout.addWidget(summary)
        configure_table(
            self.activity_table,
            ["When", "Type", "Recruiter", "Company", "Status"],
            column_widths=[140, 110, 220, 170, 120],
        )
        activity_layout.addWidget(self.activity_table)

        followup_card = QFrame()
        followup_card.setObjectName("Card")
        followup_card.setMinimumWidth(820)
        followup_layout = QVBoxLayout(followup_card)
        followup_layout.setContentsMargins(18, 18, 18, 18)
        followup_layout.setSpacing(10)
        followup_title = QLabel("Follow-Ups Due")
        followup_title.setObjectName("SectionTitle")
        followup_summary = QLabel("Actionable reminders ordered by due time.")
        followup_summary.setObjectName("Muted")
        followup_layout.addWidget(followup_title)
        followup_layout.addWidget(followup_summary)
        configure_table(
            self.followup_table,
            ["Due", "Attempt", "Recruiter", "Company", "Email"],
            column_widths=[140, 92, 180, 160, 240],
        )
        followup_layout.addWidget(self.followup_table)

        self.top_splitter.addWidget(activity_card)
        self.top_splitter.addWidget(followup_card)
        self.top_splitter.setChildrenCollapsible(False)
        self.top_splitter.setStretchFactor(0, 1)
        self.top_splitter.setStretchFactor(1, 1)
        self.top_splitter.setSizes([700, 620])
        layout.addWidget(self.top_splitter)

        reply_card = QFrame()
        reply_card.setObjectName("Card")
        reply_card.setMinimumWidth(1180)
        reply_layout = QVBoxLayout(reply_card)
        reply_layout.setContentsMargins(18, 18, 18, 18)
        reply_layout.setSpacing(10)
        reply_title = QLabel("Inbox Replies")
        reply_title.setObjectName("SectionTitle")
        reply_summary = QLabel("Newest recruiter conversations surfaced for fast handoff into the inbox workspace.")
        reply_summary.setObjectName("Muted")
        reply_layout.addWidget(reply_title)
        reply_layout.addWidget(reply_summary)
        configure_table(
            self.reply_table,
            ["Recruiter", "Subject", "Received", "Status"],
            column_widths=[220, 520, 140, 180],
        )
        reply_layout.addWidget(self.reply_table)
        layout.addWidget(reply_card)
        layout.addStretch(1)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._relayout_cards()

    def _relayout_cards(self) -> None:
        available_width = max(self.width(), self.minimumWidth())
        columns = 3 if available_width >= 1620 else 2 if available_width >= 1120 else 1
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        for index, (key, *_rest) in enumerate(self.card_specs):
            card = self.cards[key]
            self.cards_layout.addWidget(card, index // columns, index % columns)
            card.show()
        rows = (len(self.card_specs) + columns - 1) // columns
        self.cards_host.setMinimumWidth(columns * 340 + max(columns - 1, 0) * 14)
        self.cards_host.setMinimumHeight(rows * 132 + max(rows - 1, 0) * 14)

    def refresh_data(self) -> None:
        stats = self.context.database.get_stats()
        for key, value in stats.items():
            self.cards[key].set_value(str(value))

        activity_rows = self.context.database.recent_activity(limit=8)
        set_table_rows(
            self.activity_table,
            [
                [
                    format_timestamp(row["sent_at"] or row["created_at"]),
                    row["email_type"].title(),
                    row["recruiter_name"] or row["recruiter_email"],
                    row["company"] or "-",
                    row["status"].title(),
                ]
                for row in activity_rows
            ],
        )

        due_rows = self.context.database.get_due_followups()[:8]
        set_table_rows(
            self.followup_table,
            [
                [
                    format_timestamp(row["due_at"]),
                    f"#{row['attempt_number']}",
                    row["name"],
                    row["company"] or "-",
                    row["email"],
                ]
                for row in due_rows
            ],
        )

        reply_rows = self.context.database.list_inbox_replies()[:8]
        set_table_rows(
            self.reply_table,
            [
                [
                    row["name"],
                    row["latest_subject"] or "-",
                    format_timestamp(row["last_received_at"]),
                    f"{row['status']} / {row['interest_status']}",
                ]
                for row in reply_rows
            ],
        )
