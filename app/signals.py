from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal


class EventBus(QObject):
    """Thread-safe application signal hub."""

    stats_updated = pyqtSignal()
    recruiters_updated = pyqtSignal()
    logs_updated = pyqtSignal()
    followups_updated = pyqtSignal()
    replies_updated = pyqtSignal()
    theme_changed = pyqtSignal(str)
    notification_requested = pyqtSignal(str, str, str)
    background_status = pyqtSignal(str)
