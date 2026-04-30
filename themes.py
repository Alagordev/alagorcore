DARK = {
    "bg_primary":    "#0d0d0d",
    "bg_secondary":  "#141414",
    "bg_tertiary":   "#1c1c1c",
    "bg_card":       "#1e1e1e",
    "bg_hover":      "#252525",
    "bg_selected":   "#2a2a2a",
    "accent":        "#e05c2a",
    "accent_hover":  "#f06a35",
    "accent_dim":    "#3a1a0a",
    "text_primary":  "#f0f0f0",
    "text_secondary":"#888888",
    "text_muted":    "#444444",
    "border":        "#2a2a2a",
    "success":       "#2ecc71",
    "warning":       "#f39c12",
    "danger":        "#e74c3c",
    "info":          "#3498db",
}

LIGHT = {
    "bg_primary":    "#f4f4f4",
    "bg_secondary":  "#ffffff",
    "bg_tertiary":   "#ececec",
    "bg_card":       "#ffffff",
    "bg_hover":      "#e8e8e8",
    "bg_selected":   "#dcdcdc",
    "accent":        "#e05c2a",
    "accent_hover":  "#c94e22",
    "accent_dim":    "#fde8df",
    "text_primary":  "#111111",
    "text_secondary":"#555555",
    "text_muted":    "#aaaaaa",
    "border":        "#dddddd",
    "success":       "#27ae60",
    "warning":       "#e67e22",
    "danger":        "#c0392b",
    "info":          "#2980b9",
}

def get_stylesheet(mode="dark"):
    c = DARK if mode == "dark" else LIGHT
    return f"""
* {{ font-family: 'Segoe UI', Arial, sans-serif; outline: none; }}
QMainWindow, QDialog {{ background-color: {c['bg_primary']}; color: {c['text_primary']}; }}
QWidget {{ background-color: transparent; color: {c['text_primary']}; }}
QWidget#sidebar {{ background-color: {c['bg_secondary']}; border-right: 1px solid {c['border']}; }}
QWidget#topbar {{ background-color: {c['bg_secondary']}; border-bottom: 1px solid {c['border']}; }}
QWidget#content_area {{ background-color: {c['bg_primary']}; }}
QWidget#card {{ background-color: {c['bg_card']}; border: 1px solid {c['border']}; border-radius: 8px; }}
QWidget#page {{ background-color: {c['bg_primary']}; }}

QPushButton#navBtn {{
    background-color: transparent; color: {c['text_secondary']};
    border: none; text-align: left; padding: 9px 14px;
    font-size: 12px; border-radius: 6px; margin: 1px 6px;
}}
QPushButton#navBtn:hover {{ background-color: {c['bg_hover']}; color: {c['text_primary']}; }}
QPushButton#navBtn[active=true] {{
    background-color: {c['bg_selected']}; color: {c['accent']};
    font-weight: bold; border-left: 3px solid {c['accent']}; padding-left: 11px;
}}
QPushButton#navCategory {{
    background-color: transparent; color: {c['text_muted']};
    border: none; text-align: left; padding: 14px 14px 4px 14px;
    font-size: 10px; letter-spacing: 1px;
}}
QPushButton#accentBtn {{
    background-color: {c['accent']}; color: #ffffff; border: none;
    padding: 8px 18px; border-radius: 6px; font-size: 12px; font-weight: bold;
}}
QPushButton#accentBtn:hover {{ background-color: {c['accent_hover']}; }}
QPushButton#accentBtn:disabled {{ background-color: {c['text_muted']}; color: {c['bg_tertiary']}; }}
QPushButton#dangerBtn {{
    background-color: transparent; color: {c['danger']};
    border: 1px solid {c['danger']}; padding: 7px 16px; border-radius: 6px; font-size: 12px;
}}
QPushButton#dangerBtn:hover {{ background-color: {c['danger']}; color: #ffffff; }}
QPushButton#flatBtn {{
    background-color: {c['bg_hover']}; color: {c['text_primary']};
    border: 1px solid {c['border']}; padding: 7px 14px; border-radius: 6px; font-size: 12px;
}}
QPushButton#flatBtn:hover {{ background-color: {c['bg_selected']}; }}
QPushButton#iconBtn {{
    background-color: transparent; color: {c['text_secondary']};
    border: none; padding: 5px 10px; border-radius: 4px; font-size: 13px;
}}
QPushButton#iconBtn:hover {{ background-color: {c['bg_hover']}; color: {c['text_primary']}; }}
QPushButton#donateBtn {{
    background-color: #0070ba; color: #ffffff; border: none;
    padding: 8px 14px; border-radius: 20px; font-size: 12px; font-weight: bold;
}}
QPushButton#donateBtn:hover {{ background-color: #005ea6; }}

QTableWidget {{
    background-color: {c['bg_card']}; border: 1px solid {c['border']};
    border-radius: 8px; gridline-color: {c['border']};
    font-size: 12px; color: {c['text_primary']};
}}
QTableWidget::item {{ padding: 6px 10px; border: none; }}
QTableWidget::item:selected {{ background-color: {c['accent_dim']}; color: {c['text_primary']}; }}
QTableWidget::item:hover {{ background-color: {c['bg_hover']}; }}
QHeaderView::section {{
    background-color: {c['bg_tertiary']}; color: {c['text_secondary']};
    padding: 8px 10px; border: none; border-bottom: 1px solid {c['border']};
    font-size: 11px; font-weight: bold; letter-spacing: 0.5px;
}}

QScrollBar:vertical {{ background: transparent; width: 6px; border-radius: 3px; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 3px; min-height: 20px; }}
QScrollBar::handle:vertical:hover {{ background: {c['text_muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{ background: transparent; height: 6px; }}
QScrollBar::handle:horizontal {{ background: {c['border']}; border-radius: 3px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {c['bg_tertiary']}; color: {c['text_primary']};
    border: 1px solid {c['border']}; border-radius: 6px; padding: 7px 10px; font-size: 12px;
}}
QLineEdit:focus, QTextEdit:focus {{ border-color: {c['accent']}; }}
QComboBox {{
    background-color: {c['bg_tertiary']}; color: {c['text_primary']};
    border: 1px solid {c['border']}; border-radius: 6px; padding: 6px 10px; font-size: 12px;
}}
QComboBox:hover {{ border-color: {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {c['bg_card']}; color: {c['text_primary']};
    border: 1px solid {c['border']}; selection-background-color: {c['accent_dim']};
}}
QProgressBar {{
    background-color: {c['bg_tertiary']}; border: none;
    border-radius: 4px; height: 8px; color: transparent;
}}
QProgressBar::chunk {{ background-color: {c['accent']}; border-radius: 4px; }}
QCheckBox {{ color: {c['text_primary']}; font-size: 12px; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1px solid {c['border']};
    border-radius: 4px; background: {c['bg_tertiary']};
}}
QCheckBox::indicator:checked {{ background-color: {c['accent']}; border-color: {c['accent']}; }}
QLabel#pageTitle {{ font-size: 20px; font-weight: bold; color: {c['text_primary']}; }}
QLabel#sectionTitle {{ font-size: 13px; font-weight: bold; color: {c['text_primary']}; }}
QLabel#subText {{ font-size: 11px; color: {c['text_secondary']}; }}
QLabel#statValue {{ font-size: 24px; font-weight: bold; color: {c['accent']}; }}
QLabel#statLabel {{ font-size: 10px; color: {c['text_muted']}; letter-spacing: 1px; }}
QFrame#divider {{ background-color: {c['border']}; max-height: 1px; min-height: 1px; }}
QTabWidget::pane {{ border: 1px solid {c['border']}; border-radius: 6px; background: {c['bg_card']}; top: -1px; }}
QTabBar::tab {{
    background: {c['bg_tertiary']}; color: {c['text_secondary']};
    padding: 8px 16px; border: none; font-size: 12px;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{ background: {c['bg_card']}; color: {c['accent']}; font-weight: bold; border-bottom: 2px solid {c['accent']}; }}
QTabBar::tab:hover {{ background: {c['bg_hover']}; color: {c['text_primary']}; }}
QToolTip {{
    background-color: {c['bg_card']}; color: {c['text_primary']};
    border: 1px solid {c['border']}; padding: 4px 8px; border-radius: 4px; font-size: 11px;
}}
QMenu {{
    background-color: {c['bg_card']}; color: {c['text_primary']};
    border: 1px solid {c['border']}; border-radius: 6px; padding: 4px;
}}
QMenu::item {{ padding: 7px 20px; border-radius: 4px; }}
QMenu::item:selected {{ background-color: {c['accent_dim']}; color: {c['accent']}; }}
QSplitter::handle {{ background-color: {c['border']}; }}
"""
