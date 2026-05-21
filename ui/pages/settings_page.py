from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.workers import ConnectivityTestWorker
from services.mail_utils import is_gmail_host, normalize_security_mode


class SettingsPage(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.fields: dict[str, object] = {}
        self.test_worker = None
        self._build_ui()
        self.load_settings()

    def _line_edit(self, password: bool = False) -> QLineEdit:
        widget = QLineEdit()
        if password:
            widget.setEchoMode(QLineEdit.EchoMode.Password)
        return widget

    def _spin_box(self, minimum: int, maximum: int) -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        return widget

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(18)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(18)

        hero_card = QFrame()
        hero_card.setObjectName("Card")
        hero_layout = QVBoxLayout(hero_card)
        eyebrow = QLabel("Workspace")
        eyebrow.setObjectName("Eyebrow")
        title = QLabel("Tune the delivery stack, sync rules, and appearance.")
        title.setObjectName("SectionTitle")
        body = QLabel("Keep secrets local, validate connectivity quickly, and switch themes without restarting.")
        body.setObjectName("HeroBody")
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(body)
        layout.addWidget(hero_card)

        mail_card = QFrame()
        mail_card.setObjectName("Card")
        mail_layout = QGridLayout(mail_card)
        mail_layout.addWidget(QLabel("Mail Identity"), 0, 0, 1, 2)

        sender_name = self._line_edit()
        sender_email = self._line_edit()
        smtp_host = self._line_edit()
        smtp_port = self._spin_box(1, 65535)
        smtp_security = QComboBox()
        smtp_security.addItems(["ssl", "starttls", "tls", "plain"])
        smtp_username = self._line_edit()
        smtp_password = self._line_edit(password=True)
        imap_host = self._line_edit()
        imap_port = self._spin_box(1, 65535)
        imap_security = QComboBox()
        imap_security.addItems(["ssl", "plain"])
        imap_username = self._line_edit()
        imap_password = self._line_edit(password=True)

        widgets = [
            ("Sender Name", sender_name),
            ("Sender Email", sender_email),
            ("SMTP Host", smtp_host),
            ("SMTP Port", smtp_port),
            ("SMTP Security", smtp_security),
            ("SMTP Username", smtp_username),
            ("SMTP Password", smtp_password),
            ("IMAP Host", imap_host),
            ("IMAP Port", imap_port),
            ("IMAP Security", imap_security),
            ("IMAP Username", imap_username),
            ("IMAP Password", imap_password),
        ]
        for row_index, (label, widget) in enumerate(widgets, start=1):
            mail_layout.addWidget(QLabel(label), row_index, 0)
            mail_layout.addWidget(widget, row_index, 1)

        self.fields.update(
            {
                "sender_name": sender_name,
                "sender_email": sender_email,
                "smtp_host": smtp_host,
                "smtp_port": smtp_port,
                "smtp_security": smtp_security,
                "smtp_username": smtp_username,
                "smtp_password": smtp_password,
                "imap_host": imap_host,
                "imap_port": imap_port,
                "imap_security": imap_security,
                "imap_username": imap_username,
                "imap_password": imap_password,
            }
        )
        layout.addWidget(mail_card)

        delivery_card = QFrame()
        delivery_card.setObjectName("Card")
        delivery_layout = QFormLayout(delivery_card)
        daily_limit = self._spin_box(1, 500)
        delay_min = self._spin_box(1, 120)
        delay_max = self._spin_box(1, 300)
        retry_count = self._spin_box(1, 10)
        followup_delay_days = self._spin_box(1, 30)
        theme = QComboBox()
        theme.addItems(["system", "light", "dark"])
        signature = QTextEdit()
        signature.setMinimumHeight(140)
        delivery_layout.addRow("Daily Send Limit", daily_limit)
        delivery_layout.addRow("Min Delay (seconds)", delay_min)
        delivery_layout.addRow("Max Delay (seconds)", delay_max)
        delivery_layout.addRow("Retry Count", retry_count)
        delivery_layout.addRow("Follow-Up Delay (days)", followup_delay_days)
        delivery_layout.addRow("Theme", theme)
        delivery_layout.addRow("Signature HTML", signature)
        self.fields.update(
            {
                "daily_send_limit": daily_limit,
                "delay_min_seconds": delay_min,
                "delay_max_seconds": delay_max,
                "retry_count": retry_count,
                "followup_delay_days": followup_delay_days,
                "theme": theme,
                "signature_html": signature,
            }
        )
        layout.addWidget(delivery_card)

        actions = QHBoxLayout()
        helper = QLabel("Passwords are stored in macOS Keychain when saved through the app.")
        helper.setObjectName("Muted")
        save_button = QPushButton("Save Settings")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self.save_settings)
        test_smtp_button = QPushButton("Test SMTP")
        test_smtp_button.clicked.connect(self.test_smtp)
        test_imap_button = QPushButton("Test IMAP")
        test_imap_button.clicked.connect(self.test_imap)
        self.save_button = save_button
        self.test_smtp_button = test_smtp_button
        self.test_imap_button = test_imap_button
        actions.addWidget(helper, 1)
        actions.addWidget(test_smtp_button)
        actions.addWidget(test_imap_button)
        actions.addWidget(save_button)
        layout.addLayout(actions)

    def load_settings(self) -> None:
        settings = self.context.database.get_settings()
        sender_email = settings.get("sender_email", "")
        smtp_username = settings.get("smtp_username", "") or sender_email
        imap_username = settings.get("imap_username", "") or sender_email
        smtp_password = self.context.email_service.get_password(
            smtp_username,
            "smtp",
            self.context.config.env_defaults.get("smtp_password", ""),
        )
        imap_password = self.context.email_service.get_password(
            imap_username,
            "imap",
            self.context.config.env_defaults.get("imap_password", ""),
        )

        values = {
            "sender_name": settings.get("sender_name", ""),
            "sender_email": settings.get("sender_email", ""),
            "smtp_host": settings.get("smtp_host", ""),
            "smtp_port": int(settings.get("smtp_port", "465")),
            "smtp_security": normalize_security_mode(
                settings.get("smtp_security", "ssl"),
                int(settings.get("smtp_port", "465")),
                "smtp",
            ),
            "smtp_username": smtp_username,
            "smtp_password": smtp_password,
            "imap_host": settings.get("imap_host", ""),
            "imap_port": int(settings.get("imap_port", "993")),
            "imap_security": normalize_security_mode(
                settings.get("imap_security", "ssl"),
                int(settings.get("imap_port", "993")),
                "imap",
            ),
            "imap_username": imap_username,
            "imap_password": imap_password,
            "daily_send_limit": int(settings.get("daily_send_limit", "40")),
            "delay_min_seconds": int(settings.get("delay_min_seconds", "5")),
            "delay_max_seconds": int(settings.get("delay_max_seconds", "15")),
            "retry_count": int(settings.get("retry_count", "3")),
            "followup_delay_days": int(settings.get("followup_delay_days", "3")),
            "theme": settings.get("theme", "system"),
            "signature_html": settings.get("signature_html", ""),
        }

        for key, widget in self.fields.items():
            value = values[key]
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value))
            elif isinstance(widget, QComboBox):
                with QSignalBlocker(widget):
                    widget.setCurrentText(str(value))
            elif isinstance(widget, QTextEdit):
                widget.setPlainText(str(value))

    def _settings_payload(self) -> tuple[dict[str, str], dict[str, str]]:
        sender_email = self.fields["sender_email"].text().strip()
        smtp_username = self.fields["smtp_username"].text().strip() or sender_email
        imap_username = self.fields["imap_username"].text().strip() or sender_email
        settings = {
            "sender_name": self.fields["sender_name"].text().strip(),
            "sender_email": sender_email,
            "smtp_host": self.fields["smtp_host"].text().strip(),
            "smtp_port": str(self.fields["smtp_port"].value()),
            "smtp_security": self.fields["smtp_security"].currentText(),
            "smtp_username": smtp_username,
            "imap_host": self.fields["imap_host"].text().strip(),
            "imap_port": str(self.fields["imap_port"].value()),
            "imap_security": self.fields["imap_security"].currentText(),
            "imap_username": imap_username,
            "daily_send_limit": str(self.fields["daily_send_limit"].value()),
            "delay_min_seconds": str(self.fields["delay_min_seconds"].value()),
            "delay_max_seconds": str(self.fields["delay_max_seconds"].value()),
            "retry_count": str(self.fields["retry_count"].value()),
            "followup_delay_days": str(self.fields["followup_delay_days"].value()),
            "theme": self.fields["theme"].currentText(),
            "signature_html": self.fields["signature_html"].toPlainText(),
        }
        secrets = {
            "smtp_password": self.fields["smtp_password"].text(),
            "imap_password": self.fields["imap_password"].text(),
        }
        return settings, secrets

    def _validate_settings(self, settings: dict[str, str]) -> str | None:
        if int(settings["delay_min_seconds"]) > int(settings["delay_max_seconds"]):
            return "Minimum delay cannot be greater than maximum delay."
        if not settings["sender_email"]:
            return "Sender Email is required."
        if not settings["smtp_host"]:
            return "SMTP Host is required."
        if not settings["imap_host"]:
            return "IMAP Host is required."
        if is_gmail_host(settings["smtp_host"]) and "@" not in settings["smtp_username"]:
            return "SMTP Username must be the full Gmail address when using Gmail."
        if is_gmail_host(settings["imap_host"]) and "@" not in settings["imap_username"]:
            return "IMAP Username must be the full Gmail address when using Gmail."
        return None

    def _store_passwords(self, settings: dict[str, str], secrets: dict[str, str]) -> None:
        if settings["smtp_username"] and secrets["smtp_password"]:
            self.context.email_service.save_password(settings["smtp_username"], secrets["smtp_password"], "smtp")
        if settings["imap_username"] and secrets["imap_password"]:
            self.context.email_service.save_password(settings["imap_username"], secrets["imap_password"], "imap")

    def save_settings(self) -> None:
        settings, secrets = self._settings_payload()
        validation_error = self._validate_settings(settings)
        if validation_error:
            self.context.bus.notification_requested.emit(
                "Settings Error",
                validation_error,
                "error",
            )
            return

        self.context.database.save_settings(settings)
        self._store_passwords(settings, secrets)
        self.context.bus.theme_changed.emit(settings["theme"])
        self.context.bus.notification_requested.emit("Settings Saved", "Configuration updated successfully.", "success")

    def test_smtp(self) -> None:
        settings, secrets = self._settings_payload()
        self._store_passwords(settings, secrets)
        test_settings = settings | {"__smtp_password__": secrets["smtp_password"]}
        self._start_test(
            label="SMTP",
            callback=lambda: self.context.email_service.test_smtp_connection(test_settings),
        )

    def test_imap(self) -> None:
        settings, secrets = self._settings_payload()
        self._store_passwords(settings, secrets)
        test_settings = settings | {"__imap_password__": secrets["imap_password"]}
        self._start_test(
            label="IMAP",
            callback=lambda: self.context.imap_service.test_connection(test_settings),
        )

    def _start_test(self, label: str, callback) -> None:
        if self.test_worker and self.test_worker.isRunning():
            return
        self.save_button.setEnabled(False)
        self.test_smtp_button.setEnabled(False)
        self.test_imap_button.setEnabled(False)
        self.test_worker = ConnectivityTestWorker(label, callback)
        self.test_worker.completed.connect(self._test_completed)
        self.test_worker.failed.connect(self._test_failed)
        self.test_worker.finished.connect(self.test_worker.deleteLater)
        self.test_worker.start()

    def _test_completed(self, label: str) -> None:
        self.test_worker = None
        self.save_button.setEnabled(True)
        self.test_smtp_button.setEnabled(True)
        self.test_imap_button.setEnabled(True)
        self.context.bus.notification_requested.emit(f"{label} Ready", f"{label} connection succeeded.", "success")

    def _test_failed(self, message: str) -> None:
        self.test_worker = None
        self.save_button.setEnabled(True)
        self.test_smtp_button.setEnabled(True)
        self.test_imap_button.setEnabled(True)
        self.context.bus.notification_requested.emit("Connection Test Failed", message, "error")

    def shutdown(self) -> None:
        if self.test_worker and self.test_worker.isRunning():
            self.test_worker.wait(3000)
