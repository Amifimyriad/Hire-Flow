from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget


class PageScrollArea(QScrollArea):
    def __init__(self, page: QWidget, *, min_width: int):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        viewport = QWidget()
        viewport_layout = QVBoxLayout(viewport)
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.setSpacing(0)

        page.setMinimumWidth(min_width)
        viewport_layout.addWidget(page)
        viewport_layout.addStretch(1)

        self.setWidget(viewport)
