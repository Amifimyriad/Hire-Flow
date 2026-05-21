from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QGuiApplication, QPalette
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QWidget


THEMES = {
    "light": {
        "window": "#0B111A",
        "window_alt": "#101A27",
        "surface": "rgba(15, 24, 37, 0.80)",
        "surface_alt": "rgba(21, 34, 50, 0.92)",
        "surface_strong": "rgba(25, 39, 57, 0.96)",
        "sidebar": "rgba(10, 18, 27, 0.90)",
        "sidebar_alt": "rgba(18, 29, 43, 0.96)",
        "card_border": "rgba(122, 149, 196, 0.18)",
        "card_border_strong": "rgba(140, 170, 224, 0.34)",
        "hairline": "rgba(120, 145, 190, 0.16)",
        "hairline_strong": "rgba(138, 165, 210, 0.28)",
        "text": "#F4F8FF",
        "text_muted": "#B3C2DA",
        "text_soft": "#8CA2C4",
        "accent": "#4C9BFF",
        "accent_pressed": "#2E7EE6",
        "accent_soft": "rgba(76, 155, 255, 0.16)",
        "accent_glow": "rgba(76, 155, 255, 0.24)",
        "selection": "rgba(76, 155, 255, 0.22)",
        "success": "#38CF97",
        "warning": "#FFBC57",
        "danger": "#FF7B82",
        "row_alt": "rgba(18, 29, 44, 0.48)",
        "row_hover": "rgba(76, 155, 255, 0.10)",
        "row_selected": "rgba(76, 155, 255, 0.18)",
        "shadow": "#02060D",
    },
    "dark": {
        "window": "#081018",
        "window_alt": "#0D1723",
        "surface": "rgba(14, 22, 34, 0.78)",
        "surface_alt": "rgba(18, 29, 44, 0.92)",
        "surface_strong": "rgba(22, 36, 54, 0.96)",
        "sidebar": "rgba(11, 18, 28, 0.88)",
        "sidebar_alt": "rgba(18, 29, 44, 0.94)",
        "card_border": "rgba(129, 155, 201, 0.16)",
        "card_border_strong": "rgba(140, 171, 223, 0.34)",
        "hairline": "rgba(123, 147, 186, 0.14)",
        "hairline_strong": "rgba(135, 164, 212, 0.26)",
        "text": "#F4F8FF",
        "text_muted": "#A1B2CD",
        "text_soft": "#7E93B4",
        "accent": "#5AA2FF",
        "accent_pressed": "#3D85E0",
        "accent_soft": "rgba(90, 162, 255, 0.16)",
        "accent_glow": "rgba(90, 162, 255, 0.24)",
        "selection": "rgba(90, 162, 255, 0.22)",
        "success": "#37D39B",
        "warning": "#FFB84D",
        "danger": "#FF7A7A",
        "row_alt": "rgba(18, 28, 42, 0.46)",
        "row_hover": "rgba(90, 162, 255, 0.10)",
        "row_selected": "rgba(90, 162, 255, 0.18)",
        "shadow": "#02060D",
    },
}


def resolve_theme_name(theme: str) -> str:
    if theme in THEMES:
        return theme
    if theme == "system":
        return "dark"
    app = QGuiApplication.instance()
    if app is not None:
        try:
            if app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
                return "dark"
        except Exception:
            pass
    return "light"


def theme_tokens(theme: str) -> dict[str, str]:
    return THEMES[resolve_theme_name(theme)]


def build_palette(theme: str) -> QPalette:
    colors = theme_tokens(theme)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["surface_strong"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["surface_alt"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["surface_alt"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["surface_strong"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["text"]))
    return palette


def apply_shadow(widget: QWidget, theme: str, *, blur: int = 42, y_offset: int = 14, alpha: float = 0.34) -> None:
    colors = theme_tokens(theme)
    effect = QGraphicsDropShadowEffect(widget)
    shadow = QColor(colors["shadow"])
    shadow.setAlphaF(alpha)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    effect.setColor(shadow)
    widget.setGraphicsEffect(effect)


def build_stylesheet(theme: str) -> str:
    colors = theme_tokens(theme)
    return f"""
    QWidget {{
        background: transparent;
        color: {colors["text"]};
        font-family: ".AppleSystemUIFont", "SF Pro Display", "Segoe UI", "Helvetica Neue", sans-serif;
        font-size: 14px;
        outline: none;
    }}
    QMainWindow {{
        background: {colors["window"]};
    }}
    QWidget#RootShell {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {colors["window"]}, stop:0.45 {colors["window_alt"]}, stop:1 {colors["window"]});
    }}
    QFrame#Sidebar {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {colors["sidebar"]}, stop:1 {colors["sidebar_alt"]});
        border: 1px solid {colors["card_border"]};
        border-radius: 30px;
    }}
    QFrame#ContentShell, QFrame#Card {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {colors["surface"]}, stop:1 {colors["surface_alt"]});
        border: 1px solid {colors["card_border"]};
        border-radius: 28px;
    }}
    QFrame#Card[variant="hero"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {colors["surface_strong"]}, stop:1 {colors["surface_alt"]});
        border: 1px solid {colors["card_border_strong"]};
    }}
    QFrame#Card[variant="metric"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {colors["surface_alt"]}, stop:1 {colors["surface"]});
        border: 1px solid {colors["card_border"]};
    }}
    QFrame#Card[variant="subtle"] {{
        background: rgba(0, 0, 0, 0.04);
        border: 1px solid {colors["hairline"]};
    }}
    QFrame#Card[variant="accent"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {colors["accent_soft"]}, stop:1 {colors["surface_alt"]});
        border: 1px solid {colors["card_border_strong"]};
    }}
    QLabel#PageTitle {{
        font-size: 32px;
        font-weight: 700;
    }}
    QLabel#SectionTitle {{
        font-size: 18px;
        font-weight: 700;
    }}
    QLabel#CardTitle {{
        font-size: 16px;
        font-weight: 700;
    }}
    QLabel#MetricValue {{
        font-size: 34px;
        font-weight: 700;
    }}
    QLabel#MetricDelta {{
        color: {colors["accent"]};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#HeroBody, QLabel#Muted, QLabel#MetaText {{
        color: {colors["text_muted"]};
    }}
    QLabel#Muted {{
        font-size: 13px;
    }}
    QLabel#Eyebrow {{
        color: {colors["text_soft"]};
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
    }}
    QLabel#Pill, QLabel#StatusPill, QLabel#SuccessPill, QLabel#WarningPill, QLabel#DangerPill {{
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 700;
        border: 1px solid {colors["card_border_strong"]};
    }}
    QLabel#Pill, QLabel#StatusPill {{
        background: {colors["accent_soft"]};
        color: {colors["accent"]};
    }}
    QLabel#SuccessPill {{
        background: rgba(55, 211, 155, 0.14);
        color: {colors["success"]};
    }}
    QLabel#WarningPill {{
        background: rgba(255, 184, 77, 0.14);
        color: {colors["warning"]};
    }}
    QLabel#DangerPill {{
        background: rgba(255, 122, 122, 0.14);
        color: {colors["danger"]};
    }}
    QPushButton {{
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid {colors["hairline_strong"]};
        border-radius: 16px;
        padding: 11px 16px;
        font-size: 13px;
        font-weight: 600;
        color: {colors["text"]};
    }}
    QPushButton:hover {{
        background: {colors["row_hover"]};
        border-color: {colors["card_border_strong"]};
    }}
    QPushButton:pressed {{
        background: rgba(0, 0, 0, 0.10);
    }}
    QPushButton:focus {{
        border-color: {colors["accent"]};
    }}
    QPushButton#PrimaryButton {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {colors["accent"]}, stop:1 {colors["accent_pressed"]});
        color: #FFFFFF;
        border: 1px solid {colors["accent_glow"]};
    }}
    QPushButton#PrimaryButton:hover {{
        background: {colors["accent"]};
        border-color: {colors["accent"]};
    }}
    QPushButton#GhostButton {{
        background: transparent;
    }}
    QPushButton#DangerButton {{
        background: rgba(255, 122, 122, 0.16);
        color: {colors["danger"]};
        border: 1px solid rgba(255, 122, 122, 0.30);
    }}
    QPushButton#SidebarButton {{
        text-align: left;
        padding: 14px 16px;
        border-radius: 18px;
        background: transparent;
        border: 1px solid transparent;
        color: {colors["text_muted"]};
        font-size: 14px;
    }}
    QPushButton#SidebarButton:hover {{
        background: {colors["row_hover"]};
        border-color: {colors["hairline_strong"]};
        color: {colors["text"]};
    }}
    QPushButton#SidebarButton[active="true"] {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {colors["accent_soft"]}, stop:1 rgba(255, 255, 255, 0.02));
        border-color: {colors["card_border_strong"]};
        color: {colors["text"]};
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QComboBox, QSpinBox {{
        background: rgba(0, 0, 0, 0.07);
        border: 1px solid {colors["hairline_strong"]};
        border-radius: 18px;
        padding: 11px 14px;
        selection-background-color: {colors["accent"]};
        selection-color: #FFFFFF;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QTextBrowser:focus, QComboBox:focus, QSpinBox:focus {{
        border-color: {colors["accent"]};
        background: rgba(0, 0, 0, 0.10);
    }}
    QTextEdit, QPlainTextEdit, QTextBrowser {{
        padding: 14px;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QScrollArea, QTabWidget::pane {{
        border: none;
        background: transparent;
    }}
    QTableWidget, QListWidget {{
        background: rgba(0, 0, 0, 0.08);
        alternate-background-color: {colors["row_alt"]};
        border: 1px solid {colors["hairline_strong"]};
        border-radius: 20px;
        gridline-color: transparent;
        padding: 6px;
    }}
    QTableWidget {{
        font-size: 13px;
    }}
    QTableWidget::item {{
        padding: 10px 12px;
        border-bottom: 1px solid {colors["hairline"]};
    }}
    QTableWidget::item:selected {{
        background: {colors["row_selected"]};
        color: {colors["text"]};
    }}
    QTableWidget::item:hover, QListWidget::item:hover {{
        background: {colors["row_hover"]};
    }}
    QHeaderView::section {{
        background: rgba(0, 0, 0, 0.10);
        color: {colors["text_muted"]};
        border: none;
        border-bottom: 1px solid {colors["hairline_strong"]};
        padding: 12px 14px;
        font-size: 12px;
        font-weight: 700;
    }}
    QTableCornerButton::section {{
        background: rgba(0, 0, 0, 0.10);
        border: none;
    }}
    QListWidget {{
        padding: 8px;
    }}
    QListWidget::item {{
        padding: 14px;
        margin: 4px 0;
        border-radius: 16px;
        color: {colors["text_muted"]};
    }}
    QListWidget::item:selected {{
        background: {colors["row_selected"]};
        color: {colors["text"]};
    }}
    QTabBar::tab {{
        background: rgba(0, 0, 0, 0.08);
        border: 1px solid {colors["hairline"]};
        padding: 10px 16px;
        margin-right: 6px;
        border-top-left-radius: 14px;
        border-top-right-radius: 14px;
        color: {colors["text_muted"]};
    }}
    QTabBar::tab:selected {{
        background: {colors["surface_alt"]};
        color: {colors["text"]};
        border-color: {colors["card_border_strong"]};
    }}
    QSplitter::handle {{
        background: transparent;
    }}
    QSplitter::handle:horizontal {{
        width: 12px;
    }}
    QSplitter::handle:vertical {{
        height: 12px;
    }}
    QProgressBar {{
        background: rgba(0, 0, 0, 0.08);
        border: 1px solid {colors["hairline"]};
        border-radius: 10px;
        min-height: 12px;
    }}
    QProgressBar::chunk {{
        background: {colors["accent"]};
        border-radius: 9px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 12px;
        margin: 10px 4px;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 12px;
        margin: 4px 10px;
    }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background: rgba(127, 147, 186, 0.38);
        border-radius: 6px;
        min-height: 30px;
        min-width: 30px;
    }}
    QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
        background: rgba(127, 147, 186, 0.54);
    }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
        background: none;
        border: none;
    }}
    QStatusBar {{
        background: transparent;
        color: {colors["text_muted"]};
        border-top: 1px solid {colors["hairline"]};
    }}
    QMenu, QMessageBox {{
        background: {colors["surface_strong"]};
        border: 1px solid {colors["card_border_strong"]};
        color: {colors["text"]};
    }}
    QToolTip {{
        background: {colors["surface_strong"]};
        color: {colors["text"]};
        border: 1px solid {colors["card_border_strong"]};
        padding: 6px 8px;
    }}
    """
