import sys
import os
import subprocess
import ctypes
import webbrowser

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QScrollArea,
    QSizePolicy, QSpacerItem, QMessageBox, QProgressBar, QDialog
)
from PyQt6.QtCore import Qt, QTimer, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QColor

from themes import get_stylesheet, DARK, LIGHT
from config import APP_NAME, APP_VERSION, GITHUB_API_URL, load_settings, save_settings
from translations import tr
from workers import UpdateChecker, UpdateDownloader


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def relaunch_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join(f'"{a}"' for a in sys.argv), None, 1
    )
    sys.exit(0)


# ── Sidebar Navigation ────────────────────────────────────────────────────────
NAV = [
    ("monitor",      [
        ("dashboard",   "⊞",  "DashboardPage"),
        ("ram",         "◉",  "RamPage"),
        ("cpu",         "▲",  "CpuPage"),
        ("network",     "⇄",  "NetworkPage"),
        ("battery",     "▮",  "BatteryPage"),
    ]),
    ("system_tools", [
        ("startup",     "↗",  "StartupPage"),
        ("services",    "⚙",  "ServicesPage"),
        ("tasks",       "⏱",  "TasksPage"),
        ("drivers",     "⌁",  "DriversPage"),
        ("winfeatures", "✦",  "WinFeaturesPage"),
    ]),
    ("cleanup",      [
        ("uninstall",   "✕",  "UninstallPage"),
        ("cleaner",     "⌫",  "CleanerPage"),
        ("registry",    "⚿",  "RegistryPage"),
        ("disk",        "◫",  "DiskPage"),
        ("fonts",       "A",  "FontsPage"),
    ]),
    ("advanced",     [
        ("updates",     "↓",  "UpdatesPage"),
        ("hosts",       "⊟",  "HostsPage"),
        ("envvars",     "≡",  "EnvVarsPage"),
        ("tweaks",      "⚒",  "TweaksPage"),
        ("specs",       "ℹ",  "SpecsPage"),
    ]),
    ("",             [
        ("settings",    "◈",  "SettingsPage"),
    ]),
]


class Sidebar(QWidget):
    page_changed = pyqtSignal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(210)
        self.settings = settings
        self._btns = {}
        self._active = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Logo area
        logo_frame = QWidget()
        logo_frame.setFixedHeight(60)
        logo_lay = QHBoxLayout(logo_frame)
        logo_lay.setContentsMargins(16, 0, 16, 0)
        logo_icon = QLabel("⬛")
        logo_icon.setStyleSheet("color: #e05c2a; font-size: 18px;")
        logo_text = QLabel(APP_NAME)
        logo_text.setStyleSheet("font-size: 14px; font-weight: bold; letter-spacing: 1px;")
        logo_lay.addWidget(logo_icon)
        logo_lay.addWidget(logo_text)
        logo_lay.addStretch()
        lay.addWidget(logo_frame)

        # Divider
        div = QFrame()
        div.setObjectName("divider")
        div.setFixedHeight(1)
        lay.addWidget(div)

        # Scrollable nav
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_widget = QWidget()
        nav_lay = QVBoxLayout(nav_widget)
        nav_lay.setContentsMargins(0, 8, 0, 8)
        nav_lay.setSpacing(0)

        lang = settings.get("language", "en")
        for category, pages in NAV:
            if category:
                cat_btn = QPushButton(tr(category, lang).upper())
                cat_btn.setObjectName("navCategory")
                nav_lay.addWidget(cat_btn)
            for key, icon, cls in pages:
                btn = QPushButton(f"  {icon}  {tr(key, lang)}")
                btn.setObjectName("navBtn")
                btn.setProperty("active", False)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked, k=key: self._select(k))
                nav_lay.addWidget(btn)
                self._btns[key] = btn

        nav_lay.addStretch()
        scroll.setWidget(nav_widget)
        lay.addWidget(scroll, 1)

        # Bottom: version label
        ver_lbl = QLabel(f"v{APP_VERSION}")
        ver_lbl.setStyleSheet("color: #444; font-size: 10px; padding: 8px 16px;")
        lay.addWidget(ver_lbl)

    def _select(self, key):
        if self._active and self._active in self._btns:
            self._btns[self._active].setProperty("active", False)
            self._btns[self._active].style().unpolish(self._btns[self._active])
            self._btns[self._active].style().polish(self._btns[self._active])
        self._active = key
        self._btns[key].setProperty("active", True)
        self._btns[key].style().unpolish(self._btns[key])
        self._btns[key].style().polish(self._btns[key])
        self.page_changed.emit(key)

    def select_first(self):
        self._select("dashboard")

    def refresh_labels(self, lang):
        for category, pages in NAV:
            for key, icon, cls in pages:
                if key in self._btns:
                    self._btns[key].setText(f"  {icon}  {tr(key, lang)}")


# ── Top Bar ───────────────────────────────────────────────────────────────────
class TopBar(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setFixedHeight(50)
        self.settings = settings

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(10)

        self.title_lbl = QLabel("Dashboard")
        self.title_lbl.setStyleSheet("font-size: 14px; font-weight: bold;")
        lay.addWidget(self.title_lbl)
        lay.addStretch()

        # Admin badge
        if is_admin():
            admin_badge = QLabel("ADMIN")
            admin_badge.setStyleSheet(
                "background:#1a3a1a;color:#2ecc71;border:1px solid #2ecc71;"
                "border-radius:3px;padding:2px 8px;font-size:10px;font-weight:bold;")
            lay.addWidget(admin_badge)
        else:
            admin_badge = QLabel("NOT ADMIN")
            admin_badge.setStyleSheet(
                "background:#3a1a1a;color:#e74c3c;border:1px solid #e74c3c;"
                "border-radius:3px;padding:2px 8px;font-size:10px;font-weight:bold;")
            lay.addWidget(admin_badge)

        # Update indicator
        self.upd_lbl = QLabel("")
        self.upd_lbl.setStyleSheet("color:#f39c12;font-size:11px;")
        lay.addWidget(self.upd_lbl)

    def set_title(self, t):
        self.title_lbl.setText(t)

    def set_update_msg(self, msg):
        self.upd_lbl.setText(msg)


# ── Donate Button (floating) ──────────────────────────────────────────────────
class DonateButton(QPushButton):
    def __init__(self, settings, parent=None):
        super().__init__("☕  Support", parent)
        self.settings = settings
        self.setObjectName("donateBtn")
        self.setFixedSize(110, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Support AlagorCore development via PayPal")
        self.clicked.connect(self._open)

    def _open(self):
        url = self.settings.get("paypal_url", "https://paypal.me/")
        if url and url != "https://paypal.me/YOUR_PAYPAL":
            webbrowser.open(url)
        else:
            dlg = QDialog(self.parent())
            dlg.setWindowTitle("Support AlagorCore")
            dlg.setMinimumWidth(340)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(24, 24, 24, 16)
            lay.setSpacing(12)
            lbl = QLabel("Thank you for considering a donation!\nSet your PayPal link in Settings to enable this button.")
            lbl.setWordWrap(True)
            lbl.setObjectName("subText")
            lay.addWidget(lbl)
            ok = QPushButton("OK")
            ok.setObjectName("accentBtn")
            ok.clicked.connect(dlg.accept)
            lay.addWidget(ok)
            dlg.exec()


# ── Status Bar ────────────────────────────────────────────────────────────────
class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(12)
        self._msg = QLabel("Ready")
        self._msg.setStyleSheet("font-size: 11px; color: #888;")
        self._prog = QProgressBar()
        self._prog.setFixedWidth(120)
        self._prog.setFixedHeight(6)
        self._prog.setVisible(False)
        lay.addWidget(self._msg)
        lay.addStretch()
        lay.addWidget(self._prog)

    def set_message(self, msg):
        self._msg.setText(msg)

    def show_progress(self, val=None):
        self._prog.setVisible(True)
        if val is None:
            self._prog.setRange(0, 0)
        else:
            self._prog.setRange(0, 100)
            self._prog.setValue(val)

    def hide_progress(self):
        self._prog.setVisible(False)
        self._prog.setRange(0, 100)


# ── Main Window ───────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self._pages   = {}

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        # Central widget
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # Top bar
        self.topbar = TopBar(self.settings)
        main_lay.addWidget(self.topbar)

        # Body: sidebar + content
        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        self.sidebar  = Sidebar(self.settings)
        self.stack    = QStackedWidget()
        self.stack.setObjectName("content_area")

        body_lay.addWidget(self.sidebar)
        body_lay.addWidget(self.stack, 1)
        main_lay.addWidget(body, 1)

        # Status bar
        self.statusbar_widget = StatusBar()
        main_lay.addWidget(self.statusbar_widget)

        # Floating donate button (overlaid in topbar area)
        self._donate_btn = DonateButton(self.settings, self.topbar)
        self._donate_btn.move(self.topbar.width() - 130, 8)

        # Apply theme
        self._apply_theme(self.settings.get("theme", "dark"))

        # Build pages lazily
        self._build_pages()

        # Connect sidebar
        self.sidebar.page_changed.connect(self._switch_page)
        self.sidebar.select_first()

        # Connect settings page signals
        settings_page = self._pages.get("settings")
        if settings_page:
            settings_page.theme_changed.connect(self._apply_theme)
            settings_page.language_changed.connect(self._apply_language)
            settings_page.check_update_now.connect(self._check_updates)

        # Auto update check
        if self.settings.get("auto_update_check", True):
            QTimer.singleShot(3000, self._check_updates)

    def _build_pages(self):
        from pages import (DashboardPage, StartupPage, RamPage, CpuPage,
                           ServicesPage, UninstallPage, SpecsPage, DiskPage,
                           NetworkPage, CleanerPage, DriversPage, TasksPage,
                           WinFeaturesPage, BatteryPage, UpdatesPage,
                           RegistryPage, HostsPage, EnvVarsPage, FontsPage,
                           TweaksPage, SettingsPage)
        PAGE_MAP = {
            "dashboard":   DashboardPage,
            "startup":     StartupPage,
            "ram":         RamPage,
            "cpu":         CpuPage,
            "services":    ServicesPage,
            "uninstall":   UninstallPage,
            "specs":       SpecsPage,
            "disk":        DiskPage,
            "network":     NetworkPage,
            "cleaner":     CleanerPage,
            "drivers":     DriversPage,
            "tasks":       TasksPage,
            "winfeatures": WinFeaturesPage,
            "battery":     BatteryPage,
            "updates":     UpdatesPage,
            "registry":    RegistryPage,
            "hosts":       HostsPage,
            "envvars":     EnvVarsPage,
            "fonts":       FontsPage,
            "tweaks":      TweaksPage,
            "settings":    SettingsPage,
        }
        for key, cls in PAGE_MAP.items():
            page = cls(self.settings)
            page.status_message.connect(self.statusbar_widget.set_message)
            self.stack.addWidget(page)
            self._pages[key] = page

    def _switch_page(self, key):
        page = self._pages.get(key)
        if page:
            self.stack.setCurrentWidget(page)
            lang = self.settings.get("language", "en")
            self.topbar.set_title(tr(key, lang))

    def _apply_theme(self, mode):
        self.settings["theme"] = mode
        self.setStyleSheet(get_stylesheet(mode))
        save_settings(self.settings)

    def _apply_language(self, lang):
        self.settings["language"] = lang
        self.sidebar.refresh_labels(lang)
        save_settings(self.settings)

    def _check_updates(self):
        self._upd_checker = UpdateChecker(APP_VERSION, GITHUB_API_URL)
        self._upd_checker.update_available.connect(self._on_update_available)
        self._upd_checker.up_to_date.connect(lambda: self.statusbar_widget.set_message("Up to date"))
        self._upd_checker.start()

    def _on_update_available(self, version, url):
        self.topbar.set_update_msg(f"⬇ v{version} available")
        self.statusbar_widget.set_message(f"Update available: v{version} — downloading...")
        self.statusbar_widget.show_progress()
        self._downloader = UpdateDownloader(url)
        self._downloader.progress.connect(self.statusbar_widget.show_progress)
        self._downloader.done.connect(self._on_download_done)
        self._downloader.error.connect(lambda e: self.statusbar_widget.set_message(f"Update error: {e}"))
        self._downloader.start()

    def _on_download_done(self, path):
        self.statusbar_widget.hide_progress()
        self.statusbar_widget.set_message("Update downloaded — restart to apply")
        msg = QMessageBox(self)
        msg.setWindowTitle("Update Ready")
        msg.setText(f"AlagorCore update downloaded.\nRestart now to install?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            subprocess.Popen([path])
            QApplication.quit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, '_donate_btn') and hasattr(self, 'topbar'):
            self._donate_btn.move(self.topbar.width() - 130, 8)

    def closeEvent(self, e):
        save_settings(self.settings)
        e.accept()


# ── Entry Point ───────────────────────────────────────────────────────────────
def main():
    # Request admin on Windows
    if sys.platform == "win32" and not is_admin():
        try:
            relaunch_as_admin()
        except Exception:
            pass  # If UAC is cancelled, run without admin

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # High DPI
    try:
        from PyQt6.QtCore import Qt
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    except Exception:
        pass

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
