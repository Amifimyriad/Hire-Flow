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
    QScrollArea,
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
from ui.styles import apply_shadow, build_palette, build_stylesheet, resolve_theme_name
from ui.widgets.page_scroll_area import PageScrollArea


class MainWindow(QMainWindow):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.reply_worker = None
        self.page_buttons: dict[str, QPushButton] = {}
        self.section_labels: list[QLabel] = []
        self.page_title = QLabel("Dashboard")
        self.page_subtitle = QLabel("Track outreach volume, recruiter responses, and the follow-up queue.")
        self.sync_state = QLabel("Idle")
        self.stack = QStackedWidget()
        self.pages = {}
        self.page_containers = {}
        self.tray_icon = QSystemTrayIcon(self)
        self._message_boxes: list[QMessageBox] = []
        self._page_meta = {
            "Dashboard": {
                "title": "Dashboard",
                "subtitle": "Track outreach volume, recruiter responses, and the follow-up queue.",
            },
            "Send Emails": {
                "title": "Send Emails",
                "subtitle": "Compose high-signal outreach with a controlled delivery queue.",
            },
            "Follow-Ups": {
                "title": "Follow-Ups",
                "subtitle": "Review due reminders and keep the cadence disciplined.",
            },
            "Inbox Replies": {
                "title": "Inbox Replies",
                "subtitle": "Triage recruiter conversations in a split-view productivity inbox.",
            },
            "Recruiters": {
                "title": "Recruiters",
                "subtitle": "Import, enrich, and manage your recruiter pipeline cleanly.",
            },
            "Logs": {
                "title": "Logs",
                "subtitle": "Audit delivery events, runtime diagnostics, and operational health.",
            },
            "Settings": {
                "title": "Settings",
                "subtitle": "Configure mail delivery, sync, theme, and workspace behavior.",
            },
        }
        self._nav_groups = [
            ("Workspace", ["Dashboard", "Send Emails", "Follow-Ups", "Inbox Replies", "Recruiters"]),
            ("Control", ["Logs", "Settings"]),
        ]
        self._build_ui()
        self._connect_bus()
        self.apply_theme(self.context.database.get_settings().get("theme", "system"))
        self.refresh_all()

    def _build_ui(self) -> None:
        self.setWindowTitle(f"{self.context.config.app_name} {self.context.config.version}")
        self.resize(1480, 920)
        self.setMinimumSize(1180, 760)

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
        root_layout.setContentsMargins(22, 18, 22, 18)
        root_layout.setSpacing(18)

        self.sidebar_card = QFrame()
        self.sidebar_card.setObjectName("Sidebar")
        self.sidebar_card.setFixedWidth(332)
        sidebar_shell = QVBoxLayout(self.sidebar_card)
        sidebar_shell.setContentsMargins(16, 18, 16, 18)
        sidebar_shell.setSpacing(14)

        sidebar_top = QWidget()
        sidebar_top_layout = QVBoxLayout(sidebar_top)
        sidebar_top_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_top_layout.setSpacing(14)

        brand_block = QVBoxLayout()
        brand_block.setSpacing(4)
        workspace_label = QLabel("Outbound Workspace")
        workspace_label.setObjectName("Eyebrow")
        brand_label = QLabel("HireFlow")
        brand_label.setStyleSheet("font-size: 28px; font-weight: 700;")
        brand_subtitle = QLabel("Recruiter ops cockpit")
        brand_subtitle.setObjectName("Muted")
        brand_block.addWidget(workspace_label)
        brand_block.addWidget(brand_label)
        brand_block.addWidget(brand_subtitle)
        sidebar_top_layout.addLayout(brand_block)

        status_card = QFrame()
        status_card.setObjectName("Card")
        status_card.setProperty("variant", "accent")
        self.status_card = status_card
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(16, 14, 16, 14)
        status_layout.setSpacing(8)
        status_eyebrow = QLabel("Sync Status")
        status_eyebrow.setObjectName("Eyebrow")
        self.sync_state.setObjectName("StatusPill")
        self.sync_detail = QLabel("Inbox monitoring ready.")
        self.sync_detail.setObjectName("Muted")
        self.sync_detail.setWordWrap(True)
        status_layout.addWidget(status_eyebrow)
        status_layout.addWidget(self.sync_state, 0, Qt.AlignmentFlag.AlignLeft)
        status_layout.addWidget(self.sync_detail)
        sidebar_top_layout.addWidget(status_card)

        sidebar_shell.addWidget(sidebar_top)

        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        nav_content = QWidget()
        nav_layout = QVBoxLayout(nav_content)
        nav_layout.setContentsMargins(0, 0, 6, 0)
        nav_layout.setSpacing(12)

        for section_title, names in self._nav_groups:
            label = QLabel(section_title)
            label.setObjectName("Eyebrow")
            self.section_labels.append(label)
            nav_layout.addWidget(label)
            for name in names:
                button = QPushButton(name)
                button.setObjectName("SidebarButton")
                button.setProperty("active", name == "Dashboard")
                button.clicked.connect(lambda _, value=name: self.switch_page(value))
                self.page_buttons[name] = button
                nav_layout.addWidget(button)
        nav_layout.addStretch(1)

        nav_scroll.setWidget(nav_content)
        sidebar_shell.addWidget(nav_scroll, 1)

        profile_card = QFrame()
        profile_card.setObjectName("Card")
        profile_card.setProperty("variant", "subtle")
        self.profile_card = profile_card
        profile_layout = QVBoxLayout(profile_card)
        profile_layout.setContentsMargins(16, 14, 16, 14)
        profile_layout.setSpacing(4)
        profile_eyebrow = QLabel("Profile")
        profile_eyebrow.setObjectName("Eyebrow")
        self.profile_name = QLabel()
        self.profile_email = QLabel()
        self.profile_email.setObjectName("Muted")
        self.profile_email.setWordWrap(True)
        profile_layout.addWidget(profile_eyebrow)
        profile_layout.addWidget(self.profile_name)
        profile_layout.addWidget(self.profile_email)
        sidebar_shell.addWidget(profile_card)
        root_layout.addWidget(self.sidebar_card, 0)

        self.content_shell = QFrame()
        self.content_shell.setObjectName("ContentShell")
        content_layout = QVBoxLayout(self.content_shell)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(16)

        self.header_card = QFrame()
        self.header_card.setObjectName("Card")
        self.header_card.setProperty("variant", "hero")
        header_layout = QHBoxLayout(self.header_card)
        header_layout.setContentsMargins(24, 20, 24, 20)
        header_layout.setSpacing(18)

        title_block = QVBoxLayout()
        title_block.setSpacing(6)
        page_context = QLabel("Recruiter Operations")
        page_context.setObjectName("Eyebrow")
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle.setObjectName("HeroBody")
        self.page_subtitle.setWordWrap(True)
        title_block.addWidget(page_context)
        title_block.addWidget(self.page_title)
        title_block.addWidget(self.page_subtitle)

        action_block = QVBoxLayout()
        action_block.setSpacing(10)
        self.header_status = QLabel("Ready for sync")
        self.header_status.setObjectName("Pill")
        sync_button = QPushButton("Sync Replies")
        sync_button.setObjectName("PrimaryButton")
        sync_button.clicked.connect(self.sync_replies_manually)
        action_block.addWidget(self.header_status, 0, Qt.AlignmentFlag.AlignRight)
        action_block.addWidget(sync_button, 0, Qt.AlignmentFlag.AlignRight)
        action_block.addStretch(1)

        header_layout.addLayout(title_block, 1)
        header_layout.addLayout(action_block)
        content_layout.addWidget(self.header_card)

        self.pages = {
            "Dashboard": DashboardPage(self.context, self.sync_replies_manually),
            "Send Emails": SendEmailsPage(self.context),
            "Follow-Ups": FollowUpsPage(self.context),
            "Inbox Replies": InboxRepliesPage(self.context),
            "Recruiters": RecruitersPage(self.context),
            "Logs": LogsPage(self.context),
            "Settings": SettingsPage(self.context),
        }
        min_widths = {
            "Dashboard": 1320,
            "Send Emails": 1180,
            "Follow-Ups": 1180,
            "Inbox Replies": 1360,
            "Recruiters": 1320,
            "Logs": 1440,
            "Settings": 1040,
        }
        for name in self._page_meta:
            container = PageScrollArea(self.pages[name], min_width=min_widths[name])
            self.page_containers[name] = container
            self.stack.addWidget(container)

        content_layout.addWidget(self.stack, 1)
        root_layout.addWidget(self.content_shell, 1)

        self.refresh_profile()

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
        meta = self._page_meta[name]
        self.page_title.setText(meta["title"])
        self.page_subtitle.setText(meta["subtitle"])
        for page_name, button in self.page_buttons.items():
            button.setProperty("active", page_name == name)
            button.style().unpolish(button)
            button.style().polish(button)

    def _set_sync_state(self, text: str) -> None:
        self.sync_state.setText(text)
        detail_map = {
            "Idle": "Inbox monitoring ready.",
            "Syncing": "Fetching recruiter replies.",
            "Updated": "New reply data applied.",
            "Failed": "Reply sync requires attention.",
        }
        header_map = {
            "Idle": "Ready for sync",
            "Syncing": "Sync in progress",
            "Updated": "Replies updated",
            "Failed": "Sync failed",
        }
        self.sync_detail.setText(detail_map.get(text, detail_map["Idle"]))
        self.header_status.setText(header_map.get(text, text))

    def refresh_profile(self) -> None:
        settings = self.context.database.get_settings()
        self.profile_name.setText(settings.get("sender_name", "") or "Configure sender")
        self.profile_email.setText(settings.get("sender_email", "") or "No sender configured")

    def apply_theme(self, theme: str) -> None:
        theme_name = resolve_theme_name(theme)
        app = QApplication.instance()
        app.setPalette(build_palette(theme_name))
        app.setStyleSheet(build_stylesheet(theme_name))
        apply_shadow(self.sidebar_card, theme_name, blur=54, y_offset=18, alpha=0.30)
        apply_shadow(self.content_shell, theme_name, blur=56, y_offset=20, alpha=0.32)
        apply_shadow(self.header_card, theme_name, blur=28, y_offset=10, alpha=0.22)

    def refresh_all(self) -> None:
        self.refresh_profile()
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

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
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
