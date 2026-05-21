from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QCloseEvent, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from app.workers import ReplySyncWorker
from ui.pages import (
    DashboardPage,
    FollowUpsPage,
    InboxRepliesPage,
    LogsPage,
    RecruitersPage,
    SendEmailsPage,
    SettingsPage,
)
from ui.styles import build_palette, build_stylesheet, resolve_theme_name


class MainWindow(QMainWindow):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.reply_worker = None
        self.sidebar_expanded = True
        self.page_buttons: dict[str, QPushButton] = {}
        self.page_title = QLabel("Dashboard")
        self.page_subtitle = QLabel("Track outreach volume, recruiter responses, and the follow-up queue.")
        self.sync_state = QLabel("Idle")
        self.stack = QStackedWidget()
        self.pages = {}
        self.tray_icon = QSystemTrayIcon(self)
        self._message_boxes: list[QMessageBox] = []
        self._page_meta = {
            "Dashboard": ("Dashboard", "Track outreach volume, recruiter responses, and the follow-up queue."),
            "Send Emails": ("Send Emails", "Compose high-signal outreach with a clean delivery queue."),
            "Follow-Ups": ("Follow-Ups", "Review due reminders and keep the cadence controlled."),
            "Inbox Replies": ("Inbox Replies", "Triage recruiter conversations in a split-view inbox."),
            "Recruiters": ("Recruiters", "Import, enrich, and curate your outreach pipeline."),
            "Logs": ("Logs", "Audit delivery events and runtime diagnostics."),
            "Settings": ("Settings", "Configure mail delivery, sync, and workspace behavior."),
        }
        self._build_ui()
        self._connect_bus()
        self.apply_theme(self.context.database.get_settings().get("theme", "system"))
        self.refresh_all()

    def _build_ui(self) -> None:
        self.setWindowTitle(f"{self.context.config.app_name} {self.context.config.version}")
        self.resize(1540, 960)
        self.setMinimumSize(1280, 800)

        icon_path = self.context.config.paths.assets_dir / "hireflow_icon.png"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            self.setWindowIcon(icon)
            self.tray_icon.setIcon(icon)

        self.tray_icon.setVisible(True)
        show_action = QAction("Show HireFlow", self)
        show_action.triggered.connect(self.showNormal)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        tray_menu = QMenu(self)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        root = QWidget()
        root.setObjectName("RootShell")
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(18)

        sidebar_card = QFrame()
        sidebar_card.setObjectName("Sidebar")
        sidebar_card.setFixedWidth(264)
        self.sidebar_card = sidebar_card
        sidebar_layout = QVBoxLayout(sidebar_card)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(12)

        shell_header = QHBoxLayout()
        brand_block = QVBoxLayout()
        brand_block.setSpacing(2)
        brand = QLabel("HireFlow")
        brand.setStyleSheet("font-size: 24px; font-weight: 700; letter-spacing: -0.5px;")
        workspace = QLabel("Outbound Workspace")
        workspace.setObjectName("Eyebrow")
        brand_block.addWidget(workspace)
        brand_block.addWidget(brand)
        collapse_button = QPushButton("Collapse")
        collapse_button.setObjectName("GhostButton")
        collapse_button.clicked.connect(self.toggle_sidebar)
        self.collapse_button = collapse_button
        shell_header.addLayout(brand_block, 1)
        shell_header.addWidget(collapse_button)
        sidebar_layout.addLayout(shell_header)

        status_card = QFrame()
        status_card.setObjectName("Card")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(6)
        status_eyebrow = QLabel("Sync Status")
        status_eyebrow.setObjectName("Eyebrow")
        self.sync_state.setObjectName("StatusPill")
        status_layout.addWidget(status_eyebrow)
        status_layout.addWidget(self.sync_state, 0, Qt.AlignmentFlag.AlignLeft)
        sidebar_layout.addWidget(status_card)

        nav_section = QLabel("Workspace")
        nav_section.setObjectName("Eyebrow")
        sidebar_layout.addWidget(nav_section)
        page_names = list(self._page_meta.keys())
        for name in page_names:
            button = QPushButton(name)
            button.setObjectName("SidebarButton")
            button.setProperty("active", name == "Dashboard")
            button.clicked.connect(lambda _, value=name: self.switch_page(value))
            self.page_buttons[name] = button
            sidebar_layout.addWidget(button)
        sidebar_layout.addStretch(1)

        profile_card = QFrame()
        profile_card.setObjectName("Card")
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(14, 12, 14, 12)
        profile_layout.setSpacing(4)
        profile_eyebrow = QLabel("Profile")
        profile_eyebrow.setObjectName("Eyebrow")
        profile_name = QLabel(self.context.database.get_settings().get("sender_name", "") or "Configure sender")
        profile_email = QLabel(self.context.database.get_settings().get("sender_email", "") or "No sender configured")
        profile_email.setObjectName("Muted")
        profile_layout.addWidget(profile_eyebrow)
        profile_layout.addWidget(profile_name)
        profile_layout.addWidget(profile_email)
        sidebar_layout.addWidget(profile_card)
        root_layout.addWidget(sidebar_card, 0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        header_card = QFrame()
        header_card.setObjectName("Card")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(22, 18, 22, 18)
        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        eyebrow = QLabel("Recruiter Outreach")
        eyebrow.setObjectName("Eyebrow")
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle.setObjectName("HeroBody")
        self.page_subtitle.setWordWrap(True)
        title_block.addWidget(eyebrow)
        title_block.addWidget(self.page_title)
        title_block.addWidget(self.page_subtitle)
        sync_button = QPushButton("Sync Replies")
        sync_button.setObjectName("PrimaryButton")
        sync_button.clicked.connect(self.sync_replies_manually)
        header_layout.addLayout(title_block, 1)
        header_layout.addWidget(sync_button)
        content_layout.addWidget(header_card)

        self.pages = {
            "Dashboard": DashboardPage(self.context, self.sync_replies_manually),
            "Send Emails": SendEmailsPage(self.context),
            "Follow-Ups": FollowUpsPage(self.context),
            "Inbox Replies": InboxRepliesPage(self.context),
            "Recruiters": RecruitersPage(self.context),
            "Logs": LogsPage(self.context),
            "Settings": SettingsPage(self.context),
        }
        for name in page_names:
            self.stack.addWidget(self.pages[name])
        content_layout.addWidget(self.stack, 1)
        root_layout.addWidget(content, 1)

        status_bar = QStatusBar()
        status_bar.showMessage("Ready")
        self.setStatusBar(status_bar)
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.sync_replies_manually)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self.switch_page("Dashboard"))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self.switch_page("Inbox Replies"))

    def _connect_bus(self) -> None:
        self.context.bus.theme_changed.connect(self.apply_theme)
        self.context.bus.notification_requested.connect(self.show_notification)
        self.context.bus.background_status.connect(self.statusBar().showMessage)
        self.context.bus.replies_updated.connect(lambda: self._set_sync_state("Updated"))

    def switch_page(self, name: str) -> None:
        page_names = list(self._page_meta.keys())
        if name not in self.pages:
            return
        self.stack.setCurrentIndex(page_names.index(name))
        title, subtitle = self._page_meta[name]
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        for page_name, button in self.page_buttons.items():
            button.setProperty("active", page_name == name)
            button.style().unpolish(button)
            button.style().polish(button)

    def toggle_sidebar(self) -> None:
        self.sidebar_expanded = not self.sidebar_expanded
        width = 264 if self.sidebar_expanded else 112
        self.sidebar_card.setFixedWidth(width)
        self.collapse_button.setText("Collapse" if self.sidebar_expanded else "Expand")
        for name, button in self.page_buttons.items():
            button.setText(name if self.sidebar_expanded else name.split()[0])

    def _set_sync_state(self, text: str) -> None:
        self.sync_state.setText(text)

    def apply_theme(self, theme: str) -> None:
        theme_name = resolve_theme_name(theme)
        app = QApplication.instance()
        app.setPalette(build_palette(theme_name))
        app.setStyleSheet(build_stylesheet(theme_name))

    def refresh_all(self) -> None:
        for page in self.pages.values():
            refresh = getattr(page, "refresh_data", None)
            if callable(refresh):
                refresh()

    def sync_replies_manually(self) -> None:
        if self.reply_worker and self.reply_worker.isRunning():
            return
        settings = self.context.database.get_settings()
        self.statusBar().showMessage("Syncing inbox replies...")
        self._set_sync_state("Syncing")
        self.reply_worker = ReplySyncWorker(
            settings=settings,
            database=self.context.database,
            imap_service=self.context.imap_service,
        )
        self.reply_worker.completed.connect(self._reply_sync_finished)
        self.reply_worker.failed.connect(self._reply_sync_failed)
        self.reply_worker.start()

    def _reply_sync_finished(self, matched: int) -> None:
        self.reply_worker = None
        self.context.bus.stats_updated.emit()
        self.context.bus.followups_updated.emit()
        self.context.bus.recruiters_updated.emit()
        self.context.bus.logs_updated.emit()
        self.context.bus.replies_updated.emit()
        self._set_sync_state("Idle")
        self.statusBar().showMessage("Inbox sync complete.", 5000)
        self.show_notification(
            "Replies Synced",
            f"Matched {matched} recruiter repl{'y' if matched == 1 else 'ies'}.",
            "success",
        )

    def _reply_sync_failed(self, message: str) -> None:
        self.reply_worker = None
        self._set_sync_state("Failed")
        self.statusBar().showMessage("Inbox sync failed.", 5000)
        self.show_notification("Reply Sync Failed", message, "error")

    def show_notification(self, title: str, message: str, level: str) -> None:
        icon = {
            "success": QSystemTrayIcon.MessageIcon.Information,
            "info": QSystemTrayIcon.MessageIcon.Information,
            "warning": QSystemTrayIcon.MessageIcon.Warning,
            "error": QSystemTrayIcon.MessageIcon.Critical,
        }.get(level, QSystemTrayIcon.MessageIcon.NoIcon)
        if self.tray_icon.isVisible():
            self.tray_icon.showMessage(title, message, icon, 4000)
        self.statusBar().showMessage(f"{title}: {message}", 7000)
        if level == "error":
            dialog = QMessageBox(self)
            dialog.setIcon(QMessageBox.Icon.Critical)
            dialog.setWindowTitle(title)
            dialog.setText(title)
            dialog.setInformativeText(message)
            dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
            dialog.finished.connect(lambda _: self._message_boxes.remove(dialog) if dialog in self._message_boxes else None)
            self._message_boxes.append(dialog)
            dialog.open()

    def closeEvent(self, event: QCloseEvent) -> None:
        for page in self.pages.values():
            shutdown = getattr(page, "shutdown", None)
            if callable(shutdown):
                shutdown()
        if self.reply_worker and self.reply_worker.isRunning():
            self.reply_worker.wait(5000)
        try:
            self.context.scheduler.stop()
        except Exception:
            pass
        try:
            self.context.email_service.disconnect()
        except Exception:
            pass
        try:
            self.context.database.close()
        except Exception:
            pass
        super().closeEvent(event)
