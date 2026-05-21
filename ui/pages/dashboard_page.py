from __future__ import annotations

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
        self.activity_table = QTableWidget()
        self.followup_table = QTableWidget()
        self.reply_table = QTableWidget()
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

        hero_card = QFrame()
        hero_card.setObjectName("Card")
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(22, 18, 22, 18)
        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(4)
        eyebrow = QLabel("Overview")
        eyebrow.setObjectName("Eyebrow")
        intro = QLabel("Track outreach volume, recruiter responses, and the follow-up queue.")
        intro.setObjectName("SectionTitle")
        caption = QLabel("Live pipeline health, follow-up pressure, and recruiter response visibility.")
        caption.setObjectName("HeroBody")
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_data)
        sync_button = QPushButton("Sync Inbox Replies")
        sync_button.setObjectName("PrimaryButton")
        sync_button.clicked.connect(self.sync_callback)
        hero_copy.addWidget(eyebrow)
        hero_copy.addWidget(intro)
        hero_copy.addWidget(caption)
        hero_actions = QHBoxLayout()
        hero_actions.addStretch(1)
        hero_actions.addWidget(refresh_button)
        hero_actions.addWidget(sync_button)
        hero_layout.addLayout(hero_copy, 1)
        hero_layout.addLayout(hero_actions)
        layout.addWidget(hero_card)

        cards_layout = QGridLayout()
        cards_layout.setHorizontalSpacing(14)
        cards_layout.setVerticalSpacing(14)
        card_specs = [
            ("sent_total", "Total Emails Sent", "0", "All successful outreach emails."),
            ("replies_received", "Replies Received", "0", "Recruiter replies detected through IMAP."),
            ("pending_followups", "Pending Follow-Ups", "0", "Follow-ups currently due for action."),
            ("failed_emails", "Failed Emails", "0", "Messages that exhausted retries."),
            ("followups_sent", "Follow-Ups Sent", "0", "Successful reminder emails."),
        ]
        for index, (key, title, value, subtitle) in enumerate(card_specs):
            card = StatCard(title, value, subtitle)
            self.cards[key] = card
            cards_layout.addWidget(card, index // 3, index % 3)
        layout.addLayout(cards_layout)

        splitter = QSplitter()

        activity_card = QFrame()
        activity_card.setObjectName("Card")
        activity_layout = QVBoxLayout(activity_card)
        title = QLabel("Recent Activity")
        title.setObjectName("SectionTitle")
        activity_layout.addWidget(title)
        configure_table(
            self.activity_table,
            ["When", "Type", "Recruiter", "Company", "Status"],
        )
        activity_layout.addWidget(self.activity_table)

        followup_card = QFrame()
        followup_card.setObjectName("Card")
        followup_layout = QVBoxLayout(followup_card)
        followup_title = QLabel("Follow-Ups Due")
        followup_title.setObjectName("SectionTitle")
        followup_layout.addWidget(followup_title)
        configure_table(
            self.followup_table,
            ["Due", "Attempt", "Recruiter", "Company", "Email"],
        )
        followup_layout.addWidget(self.followup_table)

        splitter.addWidget(activity_card)
        splitter.addWidget(followup_card)
        splitter.setSizes([700, 600])
        layout.addWidget(splitter, 1)

        reply_card = QFrame()
        reply_card.setObjectName("Card")
        reply_layout = QVBoxLayout(reply_card)
        reply_title = QLabel("Inbox Replies")
        reply_title.setObjectName("SectionTitle")
        reply_layout.addWidget(reply_title)
        configure_table(
            self.reply_table,
            ["Recruiter", "Subject", "Received", "Status"],
        )
        reply_layout.addWidget(self.reply_table)
        layout.addWidget(reply_card, 1)

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
