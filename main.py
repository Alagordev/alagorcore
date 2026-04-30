import sys, os, subprocess, webbrowser, ctypes, base64
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QScrollArea,
    QMessageBox, QProgressBar, QDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QIcon

from themes import get_stylesheet
from config import APP_NAME, APP_VERSION, GITHUB_API_URL, PAYPAL_DONATE_URL, load_settings, save_settings
from translations import tr
from workers import UpdateChecker, UpdateDownloader

CREATE_NO_WINDOW = 0x08000000

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def relaunch_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None,"runas",sys.executable," ".join(f'"{a}"' for a in sys.argv),None,1)
    sys.exit(0)

def get_logo_pixmap(size=32):
    here = os.path.dirname(os.path.abspath(__file__))
    b64_path = os.path.join(here,"logo_b64.txt")
    if os.path.exists(b64_path):
        try:
            with open(b64_path,"r") as f:
                data = base64.b64decode(f.read().strip())
            px = QPixmap()
            px.loadFromData(data)
            return px.scaled(size,size,Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        except: pass
    return QPixmap()

NAV = [
    ("monitor",[
        ("dashboard",  "⊞","DashboardPage"),
        ("ram",        "◉","RamPage"),
        ("cpu",        "▲","CpuPage"),
        ("network",    "⇄","NetworkPage"),
        ("battery",    "▮","BatteryPage"),
    ]),
    ("system_tools",[
        ("startup",    "↗","StartupPage"),
        ("services",   "⚙","ServicesPage"),
        ("tasks",      "⏱","TasksPage"),
        ("drivers",    "⌁","DriversPage"),
        ("winfeatures","✦","WinFeaturesPage"),
    ]),
    ("cleanup",[
        ("uninstall",  "✕","UninstallPage"),
        ("cleaner",    "⌫","CleanerPage"),
        ("registry",   "⚿","RegistryPage"),
        ("disk",       "◫","DiskPage"),
        ("fonts",      "A","FontsPage"),
    ]),
    ("advanced",[
        ("updates",    "↓","UpdatesPage"),
        ("hosts",      "⊟","HostsPage"),
        ("envvars",    "≡","EnvVarsPage"),
        ("tweaks",     "⚒","TweaksPage"),
        ("specs",      "ℹ","SpecsPage"),
    ]),
    ("",[
        ("settings",   "◈","SettingsPage"),
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
        lay.setContentsMargins(0,0,0,0)
        lay.setSpacing(0)

        # Logo
        logo_frame = QWidget(); logo_frame.setFixedHeight(62)
        logo_lay = QHBoxLayout(logo_frame)
        logo_lay.setContentsMargins(14,0,14,0)

        logo_icon = QLabel()
        px = get_logo_pixmap(36)
        if not px.isNull():
            logo_icon.setPixmap(px)
        else:
            logo_icon.setText("⬛")
            logo_icon.setStyleSheet("color:#e05c2a;font-size:20px;")
        logo_icon.setFixedSize(36,36)

        logo_text = QLabel(APP_NAME)
        logo_text.setStyleSheet("font-size:15px;font-weight:bold;letter-spacing:1px;")
        logo_lay.addWidget(logo_icon)
        logo_lay.addWidget(logo_text)
        logo_lay.addStretch()
        lay.addWidget(logo_frame)

        div = QFrame(); div.setObjectName("divider"); div.setFixedHeight(1)
        lay.addWidget(div)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_widget = QWidget()
        nav_lay = QVBoxLayout(nav_widget)
        nav_lay.setContentsMargins(0,8,0,8)
        nav_lay.setSpacing(0)

        lang = settings.get("language","en")
        for category, pages in NAV:
            if category:
                cat_btn = QPushButton(tr(category,lang).upper())
                cat_btn.setObjectName("navCategory")
                nav_lay.addWidget(cat_btn)
            for key, icon, cls in pages:
                btn = QPushButton(f"  {icon}  {tr(key,lang)}")
                btn.setObjectName("navBtn")
                btn.setProperty("active",False)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked,k=key: self._select(k))
                nav_lay.addWidget(btn)
                self._btns[key] = btn

        nav_lay.addStretch()
        scroll.setWidget(nav_widget)
        lay.addWidget(scroll,1)

        ver_lbl = QLabel(f"v{APP_VERSION}")
        ver_lbl.setStyleSheet("color:#444;font-size:10px;padding:8px 16px;")
        lay.addWidget(ver_lbl)

    def _select(self, key):
        if self._active and self._active in self._btns:
            self._btns[self._active].setProperty("active",False)
            self._btns[self._active].style().unpolish(self._btns[self._active])
            self._btns[self._active].style().polish(self._btns[self._active])
        self._active = key
        self._btns[key].setProperty("active",True)
        self._btns[key].style().unpolish(self._btns[key])
        self._btns[key].style().polish(self._btns[key])
        self.page_changed.emit(key)

    def select_first(self): self._select("dashboard")

    def refresh_labels(self, lang):
        for category, pages in NAV:
            for key, icon, cls in pages:
                if key in self._btns:
                    self._btns[key].setText(f"  {icon}  {tr(key,lang)}")

class TopBar(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setFixedHeight(50)
        self.settings = settings

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16,0,16,0)
        lay.setSpacing(10)

        self.title_lbl = QLabel("Dashboard")
        self.title_lbl.setStyleSheet("font-size:14px;font-weight:bold;")
        lay.addWidget(self.title_lbl)
        lay.addStretch()

        self.upd_lbl = QLabel("")
        self.upd_lbl.setStyleSheet("color:#f39c12;font-size:11px;")
        lay.addWidget(self.upd_lbl)

        # Donate button
        self._donate = QPushButton("❤  Donate")
        self._donate.setObjectName("donateBtn")
        self._donate.setFixedHeight(32)
        self._donate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._donate.setToolTip("Support AlCore development")
        self._donate.clicked.connect(lambda: webbrowser.open(PAYPAL_DONATE_URL))
        lay.addWidget(self._donate)

    def set_title(self, t): self.title_lbl.setText(t)
    def set_update_msg(self, msg): self.upd_lbl.setText(msg)

class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16,0,16,0)
        self._msg = QLabel("Ready")
        self._msg.setStyleSheet("font-size:11px;color:#888;")
        self._prog = QProgressBar()
        self._prog.setFixedWidth(120)
        self._prog.setFixedHeight(6)
        self._prog.setVisible(False)
        lay.addWidget(self._msg)
        lay.addStretch()
        lay.addWidget(self._prog)

    def set_message(self, msg): self._msg.setText(msg)
    def show_progress(self, val=None):
        self._prog.setVisible(True)
        if val is None: self._prog.setRange(0,0)
        else: self._prog.setRange(0,100); self._prog.setValue(val)
    def hide_progress(self):
        self._prog.setVisible(False)
        self._prog.setRange(0,100)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self._pages   = {}

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1100,700)
        self.resize(1280,800)

        # Set window icon
        px = get_logo_pixmap(64)
        if not px.isNull():
            self.setWindowIcon(QIcon(px))

        central = QWidget(); central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(0,0,0,0)
        main_lay.setSpacing(0)

        self.topbar = TopBar(self.settings)
        main_lay.addWidget(self.topbar)

        body = QWidget()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0,0,0,0)
        body_lay.setSpacing(0)

        self.sidebar = Sidebar(self.settings)
        self.stack   = QStackedWidget()
        self.stack.setObjectName("content_area")

        body_lay.addWidget(self.sidebar)
        body_lay.addWidget(self.stack,1)
        main_lay.addWidget(body,1)

        self.statusbar_widget = StatusBar()
        main_lay.addWidget(self.statusbar_widget)

        self._apply_theme(self.settings.get("theme","dark"))
        self._build_pages()

        self.sidebar.page_changed.connect(self._switch_page)
        self.sidebar.select_first()

        settings_page = self._pages.get("settings")
        if settings_page:
            settings_page.theme_changed.connect(self._apply_theme)
            settings_page.language_changed.connect(self._apply_language)
            settings_page.check_update_now.connect(self._check_updates)

        if self.settings.get("auto_update_check",True):
            QTimer.singleShot(3000, self._check_updates)

    def _build_pages(self):
        from pages import (DashboardPage,StartupPage,RamPage,CpuPage,
                           ServicesPage,UninstallPage,SpecsPage,DiskPage,
                           NetworkPage,CleanerPage,DriversPage,TasksPage,
                           WinFeaturesPage,BatteryPage,UpdatesPage,
                           RegistryPage,HostsPage,EnvVarsPage,FontsPage,
                           TweaksPage,SettingsPage)
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
            page.status_message.connect(self._on_status_message)
            self.stack.addWidget(page)
            self._pages[key] = page

    def _on_status_message(self, msg):
        if msg.startswith("__nav:"):
            key = msg.replace("__nav:","")
            self.sidebar._select(key)
            return
        self.statusbar_widget.set_message(msg)

    def _switch_page(self, key):
        page = self._pages.get(key)
        if page:
            self.stack.setCurrentWidget(page)
            lang = self.settings.get("language","en")
            self.topbar.set_title(tr(key,lang))

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
        self.statusbar_widget.set_message(f"Update v{version} found — downloading...")
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
        msg.setText(f"AlCore update downloaded.\nRestart now to install?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            subprocess.Popen([path])
            QApplication.quit()

    def closeEvent(self, e):
        save_settings(self.settings)
        e.accept()

def main():
    if sys.platform=="win32" and not is_admin():
        try: relaunch_as_admin()
        except: pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # Set app icon
    px = get_logo_pixmap(64)
    if not px.isNull():
        app.setWindowIcon(QIcon(px))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
