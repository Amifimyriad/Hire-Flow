from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class StatCard(QFrame):
    def __init__(self, title: str, value: str, subtitle: str = "", detail: str = "Live"):
        super().__init__()
        self.setObjectName("Card")
        self.setProperty("variant", "metric")
        self.setMinimumHeight(132)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("Eyebrow")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        detail_label = QLabel(detail)
        detail_label.setObjectName("Pill")
        detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header.addWidget(title_label, 1)
        header.addWidget(detail_label, 0, Qt.AlignmentFlag.AlignRight)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("Muted")
        subtitle_label.setWordWrap(True)

        layout.addLayout(header)
        layout.addWidget(self.value_label)
        layout.addWidget(subtitle_label)
        layout.addStretch(1)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)
