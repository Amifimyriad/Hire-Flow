from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtGui import QColor, QPalette


THEMES = {
    "light": {
        "background": "#EEF2F7",
        "background_alt": "#E8EDF4",
        "surface": "#FCFDFF",
        "surface_alt": "#F6F9FC",
        "sidebar": "rgba(250, 252, 255, 0.78)",
        "sidebar_text": "#425266",
        "text": "#162033",
        "muted": "#6B7B92",
        "border": "rgba(113, 132, 161, 0.18)",
        "border_strong": "rgba(113, 132, 161, 0.32)",
        "accent": "#1667FF",
        "accent_pressed": "#0D4FC8",
        "accent_soft": "rgba(22, 103, 255, 0.12)",
        "success": "#159A6D",
        "warning": "#D68A00",
        "danger": "#D9534F",
        "shadow": "rgba(10, 25, 46, 0.10)",
        "selection": "rgba(22, 103, 255, 0.16)",
    },
    "dark": {
        "background": "#0E1116",
        "background_alt": "#141923",
        "surface": "#171D27",
        "surface_alt": "#111722",
        "sidebar": "rgba(20, 26, 37, 0.88)",
        "sidebar_text": "#C4D1E2",
        "text": "#F5F7FB",
        "muted": "#8EA0B8",
        "border": "rgba(167, 184, 211, 0.12)",
        "border_strong": "rgba(167, 184, 211, 0.24)",
        "accent": "#6FA5FF",
        "accent_pressed": "#4D83DB",
        "accent_soft": "rgba(111, 165, 255, 0.14)",
        "success": "#3CCB8B",
        "warning": "#FFB648",
        "danger": "#FF7B72",
        "shadow": "rgba(0, 0, 0, 0.28)",
        "selection": "rgba(111, 165, 255, 0.18)",
    },
}


def resolve_theme_name(theme: str) -> str:
    if theme in THEMES:
        return theme
    app = QGuiApplication.instance()
    if app is not None:
        try:
            scheme = app.styleHints().colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return "dark"
        except Exception:
            pass
    return "light"


def build_palette(theme: str) -> QPalette:
    colors = THEMES[resolve_theme_name(theme)]
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["background"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["surface_alt"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["surface"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    return palette


def build_stylesheet(theme: str) -> str:
    colors = THEMES[resolve_theme_name(theme)]
    return f"""
    QWidget {{
        background: {colors["background"]};
        color: {colors["text"]};
        font-family: ".AppleSystemUIFont", "SF Pro Display", "Segoe UI", "Helvetica Neue";
        font-size: 13px;
        outline: none;
    }}
    QMainWindow {{
        background: {colors["background"]};
    }}
    QWidget#RootShell {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {colors["background"]}, stop:1 {colors["background_alt"]});
    }}
    QFrame#Card {{
        background: {colors["surface"]};
        border: 1px solid {colors["border"]};
        border-radius: 22px;
    }}
    QFrame#Sidebar {{
        background: {colors["sidebar"]};
        border: 1px solid {colors["border"]};
        border-radius: 28px;
    }}
    QLabel#PageTitle {{
        font-size: 30px;
        font-weight: 700;
        letter-spacing: -0.4px;
    }}
    QLabel#Muted {{
        color: {colors["muted"]};
    }}
    QLabel#Eyebrow {{
        color: {colors["muted"]};
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1.1px;
    }}
    QLabel#SectionTitle {{
        font-size: 16px;
        font-weight: 650;
    }}
    QLabel#HeroBody {{
        color: {colors["muted"]};
        font-size: 14px;
        line-height: 1.4em;
    }}
    QLabel#Pill, QLabel#StatusPill {{
        background: {colors["accent_soft"]};
        color: {colors["accent"]};
        border: 1px solid {colors["border"]};
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 700;
    }}
    QLabel#SuccessPill {{
        background: rgba(21, 154, 109, 0.12);
        color: {colors["success"]};
        border: 1px solid rgba(21, 154, 109, 0.22);
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 700;
    }}
    QLabel#WarningPill {{
        background: rgba(214, 138, 0, 0.12);
        color: {colors["warning"]};
        border: 1px solid rgba(214, 138, 0, 0.22);
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 700;
    }}
    QLabel#DangerPill {{
        background: rgba(217, 83, 79, 0.12);
        color: {colors["danger"]};
        border: 1px solid rgba(217, 83, 79, 0.22);
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: 700;
    }}
    QPushButton {{
        background: {colors["surface"]};
        border: 1px solid {colors["border"]};
        border-radius: 14px;
        padding: 10px 14px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {colors["surface_alt"]};
        border-color: {colors["border_strong"]};
    }}
    QPushButton:pressed {{
        background: {colors["background_alt"]};
    }}
    QPushButton#PrimaryButton {{
        background: {colors["accent"]};
        color: white;
        border-color: {colors["accent"]};
        font-weight: 600;
    }}
    QPushButton#GhostButton {{
        background: transparent;
    }}
    QPushButton#PrimaryButton:pressed {{
        background: {colors["accent_pressed"]};
    }}
    QPushButton#DangerButton {{
        background: {colors["danger"]};
        color: white;
        border-color: {colors["danger"]};
    }}
    QPushButton#SidebarButton {{
        border-radius: 16px;
        padding: 12px 14px;
        text-align: left;
        background: transparent;
        border: 1px solid transparent;
        color: {colors["sidebar_text"]};
    }}
    QPushButton#SidebarButton:hover {{
        background: {colors["accent_soft"]};
        border-color: {colors["border"]};
    }}
    QPushButton#SidebarButton[active="true"] {{
        background: {colors["surface"]};
        color: {colors["text"]};
        border-color: {colors["border_strong"]};
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{
        background: {colors["surface"]};
        border: 1px solid {colors["border"]};
        border-radius: 16px;
        padding: 10px 12px;
        selection-background-color: {colors["accent"]};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border-color: {colors["accent"]};
    }}
    QTableWidget, QListWidget, QTabWidget::pane, QScrollArea {{
        background: {colors["surface"]};
        border: 1px solid {colors["border"]};
        border-radius: 18px;
    }}
    QTableWidget {{
        gridline-color: transparent;
        alternate-background-color: {colors["surface_alt"]};
        border-radius: 20px;
        padding: 4px;
    }}
    QTableWidget::item {{
        padding: 8px;
        border-bottom: 1px solid {colors["border"]};
    }}
    QHeaderView::section {{
        background: {colors["surface_alt"]};
        border: none;
        border-bottom: 1px solid {colors["border"]};
        padding: 10px 12px;
        font-weight: 600;
        color: {colors["muted"]};
    }}
    QListWidget {{
        outline: none;
        padding: 8px;
        background: transparent;
        border: none;
    }}
    QListWidget::item {{
        padding: 12px 14px;
        margin: 4px 0;
        border-radius: 14px;
        color: {colors["sidebar_text"]};
    }}
    QListWidget::item:selected {{
        background: {colors["surface"]};
        color: {colors["text"]};
        border: 1px solid {colors["border_strong"]};
    }}
    QTextBrowser {{
        background: transparent;
        border: none;
        padding: 4px;
    }}
    QProgressBar {{
        border: 1px solid {colors["border"]};
        border-radius: 999px;
        background: {colors["surface_alt"]};
        text-align: center;
        min-height: 10px;
    }}
    QProgressBar::chunk {{
        background: {colors["accent"]};
        border-radius: 999px;
    }}
    QTabBar::tab {{
        background: transparent;
        border: none;
        border-radius: 12px;
        padding: 8px 12px;
        margin-right: 6px;
        color: {colors["muted"]};
        font-weight: 600;
    }}
    QTabBar::tab:selected {{
        background: {colors["accent_soft"]};
        color: {colors["accent"]};
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 8px 2px 8px 0;
    }}
    QScrollBar::handle:vertical {{
        background: {colors["border_strong"]};
        border-radius: 5px;
        min-height: 36px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
    QScrollBar:horizontal, QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal, QScrollBar::add-page:horizontal,
    QScrollBar::sub-page:horizontal {{
        background: transparent;
        border: none;
        height: 0px;
        width: 0px;
    }}
    QStatusBar {{
        background: transparent;
        color: {colors["muted"]};
    }}
    QSplitter::handle {{
        background: transparent;
    }}
    """
