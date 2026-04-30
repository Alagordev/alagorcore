import os, sys, subprocess, webbrowser, datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QLineEdit, QScrollArea, QFrame, QTextEdit, QComboBox,
    QCheckBox, QTabWidget, QFileDialog, QMenu, QApplication,
    QSizePolicy, QGridLayout, QSpacerItem, QDialog, QSlider,
    QAbstractItemView, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QUrl
from PyQt6.QtGui import QFont, QColor, QDesktopServices, QPixmap
from widgets import (StatCard, SectionHeader, SmartTable, SearchBar,
                     ActionBar, ConfirmDialog, ToggleSwitch, TweakRow,
                     InfoRow, Card, Divider, ProgressRow, StatusBadge)
from workers import (StartupWorker, BootTimeWorker, RamWorker, CpuWorker, _ProcScanWorker, _DriveScanWorker,
                     ServicesWorker, InstalledAppsWorker, SpecsWorker,
                     DiskWorker, NetworkWorker, SpeedTestWorker,
                     JunkScanWorker, JunkCleanWorker, DriversWorker,
                     TasksWorker, WinFeaturesWorker, BatteryWorker,
                     UpdatesWorker, RegistryWorker, FontsWorker)

CREATE_NO_WINDOW = 0x08000000

def _ps_hidden(cmd):
    try:
        r = subprocess.run(
            ["powershell","-NoProfile","-NonInteractive","-WindowStyle","Hidden","-Command",cmd],
            capture_output=True, text=True, timeout=30,
            creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0
        )
        return r.stdout.strip()
    except: return ""

# ── Base Page ─────────────────────────────────────────────────────────────────
class BasePage(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setObjectName("page")
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(24,20,24,20)
        self._root.setSpacing(12)

    def tr(self, key, **kw):
        from translations import tr
        return tr(key, self.settings.get("language","en"), **kw)

    def confirm(self, action_text):
        dlg = ConfirmDialog(self.tr("confirm_title"),
                            self.tr("confirm_msg", action=action_text), self)
        return dlg.exec() == dlg.DialogCode.Accepted

    def open_location(self, path):
        if not path: return
        if os.path.isfile(path):
            subprocess.Popen(f'explorer /select,"{path}"',
                creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0)
        elif os.path.isdir(path):
            subprocess.Popen(f'explorer "{path}"',
                creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0)
        else:
            parent = os.path.dirname(path)
            if os.path.isdir(parent):
                subprocess.Popen(f'explorer "{parent}"',
                    creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0)

    def export_report(self, title, content):
        path, _ = QFileDialog.getSaveFileName(self, f"Export {title}",
                    f"{title}.txt", "Text Files (*.txt);;All Files (*)")
        if path:
            with open(path,"w",encoding="utf-8") as f:
                f.write(content)
            self.status_message.emit(f"Exported to {path}")

    def _ps(self, cmd, confirm_msg=""):
        if confirm_msg and not self.confirm(confirm_msg): return
        _ps_hidden(cmd)

# ── Dashboard ─────────────────────────────────────────────────────────────────
class DashboardPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.setContentsMargins(20,16,20,16)
        self._root.setSpacing(10)
        self._drive_bars = {}
        self._spd_running = False

        # ── Header ──────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel("AlCore")
        title.setStyleSheet("font-size:22px;font-weight:bold;color:#f0f0f0;")
        sub = QLabel("System Overview")
        sub.setObjectName("subText")
        sub.setStyleSheet("font-size:11px;color:#888;")
        title_col = QVBoxLayout(); title_col.setSpacing(2)
        title_col.addWidget(title); title_col.addWidget(sub)
        hdr.addLayout(title_col); hdr.addStretch()
        self._refresh_btn = QPushButton("⟳  Refresh")
        self._refresh_btn.setObjectName("flatBtn")
        self._refresh_btn.clicked.connect(self._manual_refresh)
        hdr.addWidget(self._refresh_btn)
        self._root.addLayout(hdr)
        self._root.addWidget(Divider())

        # ── Row 1: 6 stat cards ──────────────────────────────────────────
        row1 = QHBoxLayout(); row1.setSpacing(10)
        self.cpu_card    = StatCard("CPU",       "—%",   "#e05c2a")
        self.ram_card    = StatCard("RAM",        "—%",   "#3498db")
        self.gpu_card    = StatCard("GPU",        "—",    "#9b59b6")
        self.procs_card  = StatCard("Processes",  "—",    "#f39c12")
        self.uptime_card = StatCard("Uptime",     "—",    "#2ecc71")
        self.net_card    = StatCard("Network",    "—",    "#1abc9c")
        for c in [self.cpu_card,self.ram_card,self.gpu_card,
                  self.procs_card,self.uptime_card,self.net_card]:
            row1.addWidget(c)
        self._root.addLayout(row1)

        # ── Row 2: Left panel + Right panel ──────────────────────────────
        row2 = QHBoxLayout(); row2.setSpacing(10)

        # LEFT: System info + progress bars
        left_col = QVBoxLayout(); left_col.setSpacing(10)

        # System info card
        self._info_card = Card()
        info_hdr = QHBoxLayout()
        info_lbl = QLabel("System"); info_lbl.setObjectName("sectionTitle")
        self._specs_btn = QPushButton("View Full Specs →")
        self._specs_btn.setObjectName("iconBtn")
        self._specs_btn.setStyleSheet("color:#e05c2a;font-size:11px;")
        self._specs_btn.clicked.connect(lambda: self.status_message.emit("__nav:specs"))
        info_hdr.addWidget(info_lbl); info_hdr.addStretch()
        info_hdr.addWidget(self._specs_btn)
        self._info_card.add_layout(info_hdr)
        self._info_card.add(Divider())
        self._cpu_info  = InfoRow("CPU",  "Scanning...")
        self._gpu_info  = InfoRow("GPU",  "Scanning...")
        self._ram_info  = InfoRow("RAM",  "Scanning...")
        self._os_info   = InfoRow("OS",   "Scanning...")
        self._board_info= InfoRow("Board","Scanning...")
        for w in [self._cpu_info,self._gpu_info,self._ram_info,
                  self._os_info,self._board_info]:
            self._info_card.add(w)
        left_col.addWidget(self._info_card)

        # Resource bars card
        self._bars_card = Card()
        bars_lbl = QLabel("Live Usage"); bars_lbl.setObjectName("sectionTitle")
        self._bars_card.add(bars_lbl)
        self._bars_card.add(Divider())
        self.cpu_bar = ProgressRow("CPU", 0, 100, "#e05c2a")
        self.ram_bar = ProgressRow("RAM", 0, 100, "#3498db")
        self._bars_card.add(self.cpu_bar)
        self._bars_card.add(self.ram_bar)
        self._bars_lay = self._bars_card.layout()
        left_col.addWidget(self._bars_card)

        row2.addLayout(left_col, 5)

        # RIGHT: Speed test + top processes
        right_col = QVBoxLayout(); right_col.setSpacing(10)

        # Speed test card
        spd_card = Card()
        spd_hdr = QHBoxLayout()
        spd_lbl = QLabel("Speed Test"); spd_lbl.setObjectName("sectionTitle")
        self._spd_btn = QPushButton("▶  Run Test")
        self._spd_btn.setObjectName("accentBtn")
        self._spd_btn.setFixedHeight(28)
        self._spd_btn.clicked.connect(self._run_speedtest)
        spd_hdr.addWidget(spd_lbl); spd_hdr.addStretch()
        spd_hdr.addWidget(self._spd_btn)
        spd_card.add_layout(spd_hdr)
        spd_card.add(Divider())
        spd_stats = QHBoxLayout(); spd_stats.setSpacing(8)
        self._dl_card  = StatCard("Download", "—",    "#2ecc71")
        self._ul_card  = StatCard("Upload",   "—",    "#3498db")
        self._ping_card= StatCard("Ping",     "—",    "#f39c12")
        self._jit_card = StatCard("Jitter",   "—",    "#e05c2a")
        for c in [self._dl_card,self._ul_card,self._ping_card,self._jit_card]:
            spd_stats.addWidget(c)
        spd_card.add_layout(spd_stats)
        self._spd_prog = QProgressBar()
        self._spd_prog.setFixedHeight(4)
        self._spd_prog.setVisible(False)
        self._spd_prog.setTextVisible(False)
        spd_card.add(self._spd_prog)
        self._spd_status = QLabel("Press Run Test to measure your connection")
        self._spd_status.setObjectName("subText")
        spd_card.add(self._spd_status)
        right_col.addWidget(spd_card)

        # Top processes card
        top_card = Card()
        top_hdr = QHBoxLayout()
        top_lbl = QLabel("Top Processes"); top_lbl.setObjectName("sectionTitle")
        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["By RAM","By CPU"])
        self._sort_combo.setFixedWidth(90)
        self._sort_combo.currentTextChanged.connect(self._sort_cached_procs)
        top_hdr.addWidget(top_lbl); top_hdr.addStretch()
        top_hdr.addWidget(self._sort_combo)
        top_card.add_layout(top_hdr)
        top_card.add(Divider())
        self._top_table = SmartTable(["Process","RAM (MB)","CPU %","PID","Status"])
        self._top_table.setFixedHeight(200)
        self._top_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        top_card.add(self._top_table)
        right_col.addWidget(top_card, 1)

        row2.addLayout(right_col, 4)
        self._root.addLayout(row2, 1)

        # ── Row 3: All drives ─────────────────────────────────────────────
        drives_card = Card()
        drives_hdr = QLabel("Storage"); drives_hdr.setObjectName("sectionTitle")
        drives_card.add(drives_hdr)
        drives_card.add(Divider())
        self._drives_lay = QHBoxLayout(); self._drives_lay.setSpacing(16)
        drives_card.add_layout(self._drives_lay)
        self._root.addWidget(drives_card)

        # ── Timers & workers ──────────────────────────────────────────────
        # Fast timer: CPU/RAM/net only (every 2s) — truly non-blocking
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_fast)
        self._timer.start(2000)

        # Medium timer: processes (every 6s) — background thread
        self._proc_timer = QTimer(self)
        self._proc_timer.timeout.connect(self._refresh_procs)
        self._proc_timer.start(6000)

        # Slow timer: drives (every 15s) — background thread, disk I/O
        self._drive_timer = QTimer(self)
        self._drive_timer.timeout.connect(self._refresh_drives)
        self._drive_timer.start(15000)

        self._procs_data = []

        self._uptime_worker = BootTimeWorker()
        self._uptime_worker.result.connect(self._on_uptime)
        self._uptime_worker.start()

        # Specs scan once on load only
        self._specs_worker = SpecsWorker()
        self._specs_worker.result.connect(self._on_specs)
        self._specs_worker.start()

        self._refresh_fast()
        self._refresh_procs()
        self._refresh_drives()

    def _on_uptime(self, data):
        self.uptime_card.set_value(data.get("uptime_str","N/A"))

    def _on_specs(self, data):
        def short(s, n=40): return s[:n]+"..." if len(s)>n else s
        cpu = data.get("cpu","N/A")
        gpu = data.get("gpu","N/A")
        ram = f"{data.get('ram_total','')} GB"
        sticks = data.get("ram_sticks",[])
        if sticks:
            ram += f"  {sticks[0].get('type','')}  {sticks[0].get('speed','')} MHz"
        os_str = data.get("os","N/A")
        board  = data.get("motherboard","N/A")
        # Update InfoRow value labels safely
        for info_row, val in [
            (self._cpu_info,  short(cpu)),
            (self._gpu_info,  short(gpu)),
            (self._ram_info,  short(ram)),
            (self._os_info,   short(os_str)),
            (self._board_info,short(board)),
        ]:
            labels = info_row.findChildren(QLabel)
            if len(labels) >= 2:
                labels[1].setText(val)
                labels[1].setToolTip(val)  # full text on hover
        self.gpu_card.set_value(gpu[:16]+"..." if len(gpu)>16 else gpu)
        self._specs_data = data  # cache for quick access button

    def _manual_refresh(self):
        self._refresh_fast()
        self._refresh_procs()
        self._refresh_drives()

    def _refresh_fast(self):
        """ONLY non-blocking psutil calls. No disk, no WMI, no PowerShell."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            vm  = psutil.virtual_memory()
            self.cpu_card.set_value(f"{cpu:.1f}%")
            self.ram_card.set_value(f"{vm.percent:.1f}%")
            self.cpu_bar.set_value(cpu)
            self.ram_bar.set_value(vm.percent)
        except: pass
        try:
            import psutil
            io = psutil.net_io_counters()
            if hasattr(self, '_prev_io'):
                rx = round((io.bytes_recv - self._prev_io.bytes_recv)/1024/2.0, 0)
                tx = round((io.bytes_sent - self._prev_io.bytes_sent)/1024/2.0, 0)
                self.net_card.set_value(f"↓{rx:.0f} ↑{tx:.0f} KB/s")
            self._prev_io = io
        except: pass
        try:
            import psutil
            self.procs_card.set_value(str(len(psutil.pids())))
        except: pass

    def _refresh_drives(self):
        """Called in background thread — disk I/O can block, keep off main thread."""
        self._drive_worker = _DriveScanWorker()
        self._drive_worker.result.connect(self._on_drives)
        self._drive_worker.start()

    def _on_drives(self, drives):
        """Update drive display on main thread with already-scanned data."""
        while self._drives_lay.count():
            item = self._drives_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for d in drives:
            color = "#e74c3c" if d['pct']>85 else "#e05c2a" if d['pct']>70 else "#2ecc71"
            col = QVBoxLayout(); col.setSpacing(4)
            name_lbl = QLabel(f"{d['dev']}  ({d['fs']})")
            name_lbl.setObjectName("sectionTitle")
            size_lbl = QLabel(f"{d['used']} / {d['total']} GB")
            size_lbl.setObjectName("subText")
            bar = ProgressRow("", int(d['pct']), 100, color)
            pct_lbl = QLabel(f"{d['pct']:.1f}% used")
            pct_lbl.setStyleSheet(f"color:{color};font-size:11px;")
            col.addWidget(name_lbl); col.addWidget(size_lbl)
            col.addWidget(bar); col.addWidget(pct_lbl)
            w = QWidget(); w.setLayout(col)
            w.setMinimumWidth(180)
            self._drives_lay.addWidget(w)
        self._drives_lay.addStretch()

    def _refresh_procs(self):
        """Scan processes in background thread — called every 6s."""
        self._proc_scan = _ProcScanWorker()
        self._proc_scan.result.connect(self._on_procs)
        self._proc_scan.start()

    def _on_procs(self, procs):
        self._cached_procs = procs
        self._sort_cached_procs()

    def _sort_cached_procs(self):
        """Sort already-cached process data — instant, no scanning."""
        procs = getattr(self, '_cached_procs', [])
        if not procs: return
        sort_by = self._sort_combo.currentText()
        if sort_by == "By RAM":
            procs = sorted(procs, key=lambda x: x['ram'], reverse=True)
        else:
            procs = sorted(procs, key=lambda x: x['cpu'], reverse=True)
        self._top_table.clear_rows()
        for p in procs[:10]:
            r = self._top_table.add_row([p['name'],str(p['ram']),
                                          str(p['cpu']),str(p['pid']),p['status']])
            if p['cpu'] > 20 or p['ram'] > 500:
                for c in range(self._top_table.columnCount()):
                    item = self._top_table.item(r,c)
                    if item: item.setForeground(QColor("#e05c2a"))

    def _run_speedtest(self):
        if self._spd_running: return
        self._spd_running = True
        self._spd_btn.setEnabled(False)
        self._spd_btn.setText("Running...")
        self._dl_card.set_value("—")
        self._ul_card.set_value("—")
        self._ping_card.set_value("—")
        self._jit_card.set_value("—")
        self._spd_prog.setVisible(True)
        self._spd_prog.setRange(0,0)
        self._spd_status.setText("Testing connection...")
        self._spd_worker = SpeedTestWorker()
        self._spd_worker.progress.connect(lambda m: self._spd_status.setText(m))
        self._spd_worker.result.connect(self._on_speedtest)
        self._spd_worker.error.connect(lambda e: (
            self._spd_status.setText(f"Error: {e}"),
            self._spd_btn.setEnabled(True),
            self._spd_btn.setText("▶  Run Test"),
            self._spd_prog.setVisible(False),
            setattr(self, '_spd_running', False)
        ))
        self._spd_worker.start()

    def _on_speedtest(self, data):
        self._dl_card.set_value(f"{data['download_mbps']} Mbps")
        self._ul_card.set_value(f"{data['upload_mbps']} Mbps")
        self._ping_card.set_value(f"{data['ping_ms']} ms")
        self._jit_card.set_value(f"{data['jitter_ms']} ms")
        server = data.get("server","")
        isp    = data.get("isp","")
        info   = f"Server: {server}" if server else ""
        if isp: info += f"  |  ISP: {isp}"
        self._spd_status.setText(info or f"↓ {data['download_mbps']} Mbps  ↑ {data['upload_mbps']} Mbps")
        self._spd_prog.setVisible(False)
        self._spd_btn.setEnabled(True)
        self._spd_btn.setText("▶  Run Test")
        self._spd_running = False

# ── Startup Manager ───────────────────────────────────────────────────────────
class StartupPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._entries = []
        self._root.addWidget(SectionHeader(self.tr("startup"),
            "Programs that run when Windows starts"))
        self._root.addWidget(Divider())

        # Boot time card
        self._boot_card = Card()
        boot_row = QHBoxLayout()
        self._boot_lbl   = QLabel("Boot time: scanning...")
        self._boot_lbl.setObjectName("subText")
        self._uptime_lbl = QLabel("")
        self._uptime_lbl.setObjectName("subText")
        boot_row.addWidget(self._boot_lbl)
        boot_row.addStretch()
        boot_row.addWidget(self._uptime_lbl)
        self._boot_card.add_layout(boot_row)
        self._root.addWidget(self._boot_card)

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
        bar.add_button("Export PS1", "flatBtn", self._export_all)
        self._search = SearchBar("Search startup entries...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_stretch()
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Name","Impact","Command","Location","Status"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)
        self._scan()
        self._boot_worker = BootTimeWorker()
        self._boot_worker.result.connect(self._on_boot)
        self._boot_worker.start()

    def _on_boot(self, data):
        self._boot_lbl.setText(f"Last boot: {data.get('boot_time','N/A')}")
        self._uptime_lbl.setText(f"Uptime: {data.get('uptime_str','N/A')}")

    def _scan(self):
        self._table.clear_rows()
        self.status_message.emit("Scanning startup entries...")
        self._worker = StartupWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, entries):
        self._entries = entries
        self._table.clear_rows()
        for e in entries:
            r = self._table.add_row([e['name'], e['impact'], e['command'],
                                      e['location'], "Enabled"])
            color = {"Heavy":"#e74c3c","Medium":"#f39c12","Light":"#2ecc71"}.get(e['impact'],"#888")
            item = QTableWidgetItem(e['impact'])
            item.setForeground(QColor(color))
            self._table.setItem(r, 1, item)
        self.status_message.emit(f"Found {len(entries)} startup entries")

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._entries): return
        entry = self._entries[row]
        menu  = QMenu(self)
        menu.addAction("Disable Entry", lambda: self._disable(entry, row))
        menu.addAction("Open File Location", lambda: self.open_location(
            entry['command'].split('"')[1] if '"' in entry['command'] else entry['command'].split()[0]))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _disable(self, entry, row):
        if not self.confirm(f"disable '{entry['name']}' from startup"): return
        try:
            import winreg
            if entry['hive'] and entry['path']:
                key = winreg.OpenKey(entry['hive'], entry['path'], 0, winreg.KEY_WRITE)
                winreg.DeleteValue(key, entry['name'])
                winreg.CloseKey(key)
            elif os.path.exists(os.path.join(entry['path'], entry['name'])):
                os.remove(os.path.join(entry['path'], entry['name']))
            self._entries.pop(row)
            self._table.removeRow(row)
            self.status_message.emit(f"Disabled: {entry['name']}")
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

    def _export_all(self):
        content = "# AlCore — Disable All Startup Entries\n"
        for e in self._entries:
            content += f'Remove-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name "{e["name"]}" -Force -ErrorAction SilentlyContinue\n'
        self.export_report("startup_disable_all", content)

# ── RAM Monitor ───────────────────────────────────────────────────────────────
class RamPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._procs = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._scan)
        self._live = False

        self._root.addWidget(SectionHeader(self.tr("ram"),"Memory usage and process breakdown"))
        self._root.addWidget(Divider())

        stats = QHBoxLayout(); stats.setSpacing(12)
        self.total_card = StatCard("Total RAM","—")
        self.used_card  = StatCard("Used","—","#e05c2a")
        self.free_card  = StatCard("Available","—","#2ecc71")
        self.pct_card   = StatCard("Usage %","—","#3498db")
        for c in [self.total_card,self.used_card,self.free_card,self.pct_card]:
            stats.addWidget(c)
        self._root.addLayout(stats)

        # RAM sticks info
        self._sticks_card = Card()
        sticks_lbl = QLabel("Installed Memory")
        sticks_lbl.setObjectName("sectionTitle")
        self._sticks_card.add(sticks_lbl)
        self._sticks_lay = QVBoxLayout()
        self._sticks_lay.setSpacing(4)
        self._sticks_card.add_layout(self._sticks_lay)
        self._root.addWidget(self._sticks_card)

        bar = ActionBar()
        bar.add_button("Scan / Refresh","accentBtn",self._scan)
        self._live_btn = bar.add_button("Live OFF","flatBtn",self._toggle_live)
        self._live_btn.setStyleSheet("color:#e74c3c;border-color:#e74c3c;")
        bar.add_stretch()
        self._search = SearchBar("Filter processes...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["PID","Process","RAM (MB)","RAM %","Status","Path"])
        self._table.horizontalHeader().setSectionResizeMode(5,QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)
        self._scan()

    def _toggle_live(self):
        self._live = not self._live
        if self._live:
            self._timer.start(self.settings.get("polling_interval",2)*1000)
            self._live_btn.setText("Live ON")
            self._live_btn.setStyleSheet("color:#2ecc71;border-color:#2ecc71;background:#0d2b1a;")
        else:
            self._timer.stop()
            self._live_btn.setText("Live OFF")
            self._live_btn.setStyleSheet("color:#e74c3c;border-color:#e74c3c;")

    def _scan(self):
        self._worker = RamWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, data):
        self.total_card.set_value(f"{data['total_gb']} GB")
        self.used_card.set_value(f"{data['used_gb']} GB")
        self.free_card.set_value(f"{data['free_gb']} GB")
        self.pct_card.set_value(f"{data['pct']}%")

        # Clear sticks
        while self._sticks_lay.count():
            item = self._sticks_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for s in data.get("sticks",[]):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Slot: {s['slot']}"))
            row.addWidget(QLabel(f"{s['capacity']} GB"))
            row.addWidget(QLabel(f"{s['type']}"))
            row.addWidget(QLabel(f"{s['speed']} MHz"))
            row.addWidget(QLabel(f"{s['manufacturer']}"))
            row.addWidget(QLabel(f"{s['part']}"))
            row.addStretch()
            w = QWidget()
            w.setLayout(row)
            self._sticks_lay.addWidget(w)

        # Cache — sort never rescans
        self._procs = data['processes']
        self._cached_ram_procs = data['processes']
        self._render_procs()
        self.status_message.emit(f"RAM: {data['used_gb']}/{data['total_gb']} GB ({data['pct']}%)")

    def _render_procs(self):
        procs = sorted(getattr(self,'_cached_ram_procs',[]), key=lambda x: x['rss_mb'], reverse=True)
        self._procs = procs
        self._table.clear_rows()
        for p in procs:
            self._table.add_row([str(p['pid']),p['name'],str(p['rss_mb']),
                                  str(p['pct']),p['status'],p['exe']])

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._procs): return
        proc = self._procs[row]
        menu = QMenu(self)
        menu.addAction("Kill Process",       lambda: self._kill(proc,row))
        menu.addAction("Open File Location", lambda: self.open_location(proc['exe']))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _kill(self, proc, row):
        if not self.confirm(f"kill '{proc['name']}' (PID {proc['pid']})"): return
        try:
            import psutil
            psutil.Process(proc['pid']).kill()
            self._procs.pop(row)
            self._table.removeRow(row)
            self.status_message.emit(f"Killed: {proc['name']}")
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

# ── CPU Processes ─────────────────────────────────────────────────────────────
class CpuPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._procs = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._scan)
        self._live = False

        self._root.addWidget(SectionHeader(self.tr("cpu"),"CPU usage per process"))
        self._root.addWidget(Divider())

        stats = QHBoxLayout(); stats.setSpacing(12)
        self.cpu_card    = StatCard("CPU Usage","—%","#e05c2a")
        self.name_card   = StatCard("Processor","—")
        self.cores_card  = StatCard("Cores/Threads","—")
        self.freq_card   = StatCard("Frequency","—")
        for c in [self.cpu_card,self.name_card,self.cores_card,self.freq_card]:
            stats.addWidget(c)
        self._root.addLayout(stats)

        # CPU detail card
        self._cpu_info_card = Card()
        cpu_info_lbl = QLabel("Processor Details")
        cpu_info_lbl.setObjectName("sectionTitle")
        self._cpu_info_card.add(cpu_info_lbl)
        self._cpu_info_lay = QVBoxLayout()
        self._cpu_info_lay.setSpacing(4)
        self._cpu_info_card.add_layout(self._cpu_info_lay)
        self._root.addWidget(self._cpu_info_card)

        bar = ActionBar()
        bar.add_button("Scan / Refresh","accentBtn",self._scan)
        self._live_btn = bar.add_button("Live OFF","flatBtn",self._toggle_live)
        self._live_btn.setStyleSheet("color:#e74c3c;border-color:#e74c3c;")
        bar.add_stretch()
        self._search = SearchBar("Filter processes...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["PID","Process","CPU %","Status","User","Path"])
        self._table.horizontalHeader().setSectionResizeMode(5,QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)
        self._scan()

    def _toggle_live(self):
        self._live = not self._live
        if self._live:
            self._timer.start(self.settings.get("polling_interval",2)*1000)
            self._live_btn.setText("Live ON")
            self._live_btn.setStyleSheet("color:#2ecc71;border-color:#2ecc71;background:#0d2b1a;")
        else:
            self._timer.stop()
            self._live_btn.setText("Live OFF")
            self._live_btn.setStyleSheet("color:#e74c3c;border-color:#e74c3c;")

    def _scan(self):
        self._worker = CpuWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, data):
        self.cpu_card.set_value(f"{data['total_pct']}%")
        name = data.get('name','N/A')
        self.name_card.set_value(name[:20] + "..." if len(name)>20 else name)
        self.cores_card.set_value(f"{data['cores']}C / {data['threads']}T")
        self.freq_card.set_value(f"{data['freq_mhz']} MHz")

        # Detail info
        while self._cpu_info_lay.count():
            item = self._cpu_info_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        details = [
            ("Model",        data.get('name','N/A')),
            ("Manufacturer", data.get('manufacturer','N/A')),
            ("Cores",        f"{data.get('cores','N/A')} Physical / {data.get('threads','N/A')} Logical"),
            ("Max Clock",    f"{data.get('freq_max',0)} MHz"),
            ("Current Clock",f"{data.get('freq_mhz',0)} MHz"),
            ("L2 Cache",     f"{data.get('l2_kb','N/A')} KB"),
            ("L3 Cache",     f"{data.get('l3_kb','N/A')} KB"),
            ("Socket",       data.get('socket','N/A')),
            ("Architecture", data.get('arch','N/A')),
        ]
        row_lay = QHBoxLayout()
        col1 = QVBoxLayout()
        col2 = QVBoxLayout()
        for i, (label, val) in enumerate(details):
            target = col1 if i < 5 else col2
            target.addWidget(InfoRow(label, val))
        row_lay.addLayout(col1)
        row_lay.addLayout(col2)
        w = QWidget(); w.setLayout(row_lay)
        self._cpu_info_lay.addWidget(w)

        self._procs = data['processes']
        self._table.clear_rows()
        for p in self._procs:
            r = self._table.add_row([str(p['pid']),p['name'],str(p['cpu_pct']),
                                      p['status'],p['user'],p['exe']])
            if p['cpu_pct'] > 20:
                for c in range(self._table.columnCount()):
                    item = self._table.item(r,c)
                    if item: item.setForeground(QColor("#e05c2a"))

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._procs): return
        proc = self._procs[row]
        menu = QMenu(self)
        menu.addAction("Kill Process",       lambda: self._kill(proc,row))
        menu.addAction("Open File Location", lambda: self.open_location(proc['exe']))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _kill(self, proc, row):
        if not self.confirm(f"kill '{proc['name']}' (PID {proc['pid']})"): return
        try:
            import psutil
            psutil.Process(proc['pid']).kill()
            self._procs.pop(row)
            self._table.removeRow(row)
            self.status_message.emit(f"Killed: {proc['name']}")
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

# ── Services ──────────────────────────────────────────────────────────────────
class ServicesPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._svcs = []
        self._root.addWidget(SectionHeader(self.tr("services"),"Windows services — view, start, stop, disable"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan","accentBtn",self._scan)
        self._filter = QComboBox()
        self._filter.addItems(["All","Running","Stopped","Disabled","Auto Start","Manual"])
        self._filter.currentTextChanged.connect(self._apply_filter)
        bar.add_widget(self._filter)
        bar.add_stretch()
        self._search = SearchBar("Search services...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Name","Display Name","Status","Start Type","PID","Path"])
        self._table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)
        self._scan()

    def _scan(self):
        self._worker = ServicesWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()
        self.status_message.emit("Scanning services...")

    def _on_result(self, svcs):
        self._svcs = svcs
        self._table.clear_rows()
        for s in svcs:
            r = self._table.add_row([s['name'],s['display'],s['status'],
                                      s['start_type'],str(s['pid']),s['exe']])
            color = "#2ecc71" if s['status']=="running" else "#e74c3c" if s['status']=="stopped" else "#888"
            item = QTableWidgetItem(s['status'])
            item.setForeground(QColor(color))
            self._table.setItem(r,2,item)
        self.status_message.emit(f"Found {len(svcs)} services")

    def _apply_filter(self, f):
        f = f.lower()
        for row in range(self._table.rowCount()):
            show = True
            if f=="running":   show = (self._table.item(row,2) or QTableWidgetItem()).text().lower()=="running"
            elif f=="stopped": show = (self._table.item(row,2) or QTableWidgetItem()).text().lower()=="stopped"
            elif f=="disabled":show = "disabled" in (self._table.item(row,3) or QTableWidgetItem()).text().lower()
            elif f=="auto start":show = "auto" in (self._table.item(row,3) or QTableWidgetItem()).text().lower()
            elif f=="manual":  show = "manual" in (self._table.item(row,3) or QTableWidgetItem()).text().lower()
            self._table.setRowHidden(row, not show)

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._svcs): return
        svc = self._svcs[row]
        menu = QMenu(self)
        menu.addAction("Stop Service",    lambda: self._svc_action(svc,"stop"))
        menu.addAction("Start Service",   lambda: self._svc_action(svc,"start"))
        menu.addAction("Disable Service", lambda: self._svc_action(svc,"disable"))
        menu.addAction("Enable (Manual)", lambda: self._svc_action(svc,"enable"))
        menu.addAction("Open File Location", lambda: self.open_location(svc['exe']))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _svc_action(self, svc, action):
        if not self.confirm(f"{action} service '{svc['display']}'"): return
        cmds = {
            "stop":    f"Stop-Service -Name '{svc['name']}' -Force",
            "start":   f"Start-Service -Name '{svc['name']}'",
            "disable": f"Set-Service -Name '{svc['name']}' -StartupType Disabled",
            "enable":  f"Set-Service -Name '{svc['name']}' -StartupType Manual",
        }
        _ps_hidden(cmds[action])
        self.status_message.emit(f"{action.title()}ed: {svc['name']}")
        self._scan()

# ── Uninstall Manager ─────────────────────────────────────────────────────────
class UninstallPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._apps = []
        self._root.addWidget(SectionHeader(self.tr("uninstall"),"All installed applications"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan","accentBtn",self._scan)
        bar.add_button("Batch Uninstall Selected","dangerBtn",self._batch_uninstall)
        self._filter = QComboBox()
        self._filter.addItems(["All","Bloatware","Win32","Store/UWP","C: Drive","D: Drive"])
        self._filter.currentTextChanged.connect(self._apply_filter)
        bar.add_widget(self._filter)
        bar.add_stretch()
        self._search = SearchBar("Search applications...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["","Name","Publisher","Version","Size (MB)","Drive","Type","Install Date"])
        self._table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0,30)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)
        self._scan()

    def _scan(self):
        self._worker = InstalledAppsWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()
        self.status_message.emit("Scanning installed apps...")

    def _on_result(self, apps):
        self._apps = apps
        self._table.clear_rows()
        for a in apps:
            r = self._table.add_row(["",a['name'],a['publisher'],a['version'],
                                      str(a['size_mb']),a['drive'],a['type'],a['install_date']])
            if a['bloat']:
                for c in range(self._table.columnCount()):
                    item = self._table.item(r,c)
                    if item: item.setForeground(QColor("#f39c12"))
            chk = QCheckBox()
            self._table.setCellWidget(r,0,chk)
        self.status_message.emit(f"Found {len(apps)} installed apps  |  {sum(1 for a in apps if a['bloat'])} flagged as bloatware")

    def _apply_filter(self, f):
        for row in range(self._table.rowCount()):
            show = True
            if row >= len(self._apps): continue
            a = self._apps[row]
            if f=="Bloatware":    show = a['bloat']
            elif f=="Win32":      show = a['type']=="Win32"
            elif f=="Store/UWP":  show = a['type']=="Store"
            elif f=="C: Drive":   show = a['drive'].upper().startswith("C")
            elif f=="D: Drive":   show = a['drive'].upper().startswith("D")
            self._table.setRowHidden(row, not show)

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._apps): return
        app = self._apps[row]
        menu = QMenu(self)
        menu.addAction("Uninstall",           lambda: self._uninstall(app))
        menu.addAction("Force Uninstall",     lambda: self._force_uninstall(app))
        menu.addAction("Open Install Location",lambda: self.open_location(app['location']))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _uninstall(self, app):
        if not self.confirm(f"uninstall '{app['name']}'"): return
        if app['uninstall']:
            subprocess.Popen(app['uninstall'], shell=True,
                creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0)
            self.status_message.emit(f"Uninstall launched: {app['name']}")

    def _force_uninstall(self, app):
        if not self.confirm(f"force uninstall '{app['name']}'"): return
        _ps_hidden(f"$app = Get-WmiObject Win32_Product | Where {{$_.Name -like '*{app['name']}*'}}; if($app){{$app.Uninstall()}}")
        self.status_message.emit(f"Force uninstall sent for: {app['name']}")

    def _batch_uninstall(self):
        selected = [self._apps[r] for r in range(self._table.rowCount())
                    if r < len(self._apps) and
                    isinstance(self._table.cellWidget(r,0), QCheckBox) and
                    self._table.cellWidget(r,0).isChecked()]
        if not selected:
            self.status_message.emit("No apps selected"); return
        if not self.confirm(f"uninstall {len(selected)} applications"): return
        for app in selected:
            if app['uninstall']:
                subprocess.Popen(app['uninstall'], shell=True,
                    creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0)
        self.status_message.emit(f"Launched uninstall for {len(selected)} apps")

# ── PC Specs ──────────────────────────────────────────────────────────────────
class SpecsPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("specs"),"Hardware and system information"))
        self._root.addWidget(Divider())
        bar = ActionBar()
        bar.add_button("Scan","accentBtn",self._scan)
        bar.add_button("Export Report","flatBtn",self._export)
        self._root.addWidget(bar)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content = QWidget()
        self._lay = QVBoxLayout(self._content)
        self._lay.setSpacing(12)
        scroll.setWidget(self._content)
        self._root.addWidget(scroll)
        self._data = {}
        self._scan()

    def _scan(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        lbl = QLabel("Scanning hardware — this may take a moment...")
        lbl.setObjectName("subText")
        self._lay.addWidget(lbl)
        self._worker = SpecsWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, data):
        self._data = data
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        def section(title, rows):
            card = Card()
            t = QLabel(title); t.setObjectName("sectionTitle")
            card.add(t); card.add(Divider())
            for label, val in rows:
                card.add(InfoRow(label, str(val)))
            self._lay.addWidget(card)

        section("Operating System",[
            ("OS",          data.get("os","")),
            ("Build",       data.get("os_build","")),
            ("Architecture",data.get("os_arch","")),
            ("Hostname",    data.get("hostname","")),
        ])
        section("Processor",[
            ("CPU Model",   data.get("cpu","")),
            ("Cores",       f"{data.get('cpu_cores','')} Physical / {data.get('cpu_threads','')} Logical"),
            ("Max Clock",   f"{data.get('cpu_max_mhz','')} MHz"),
            ("Current",     f"{data.get('cpu_cur_mhz','')} MHz"),
            ("L2 Cache",    f"{data.get('cpu_l2','')} KB"),
            ("L3 Cache",    f"{data.get('cpu_l3','')} KB"),
            ("Socket",      data.get("cpu_socket","")),
        ])
        section("Graphics",[
            ("GPU",         data.get("gpu","")),
            ("VRAM",        data.get("gpu_vram","")),
            ("Driver",      data.get("gpu_driver","")),
            ("Resolution",  data.get("gpu_res","")),
        ])
        section("Motherboard & BIOS",[
            ("Motherboard", data.get("motherboard","")),
            ("BIOS Version",data.get("bios","")),
            ("BIOS Vendor", data.get("bios_mfr","")),
            ("BIOS Date",   data.get("bios_date","")),
        ])

        # RAM
        ram_card = Card()
        t2 = QLabel("Memory (RAM)"); t2.setObjectName("sectionTitle")
        ram_card.add(t2); ram_card.add(Divider())
        ram_card.add(InfoRow("Total RAM", f"{data.get('ram_total','')} GB"))
        for i,s in enumerate(data.get("ram_sticks",[])):
            ram_card.add(InfoRow(f"Slot {i+1}",
                f"{s['capacity']} GB  {s['type']}  {s['speed']} MHz  {s['manufacturer']}  {s['part']}"))
        self._lay.addWidget(ram_card)

        # Storage
        disk_card = Card()
        t3 = QLabel("Storage"); t3.setObjectName("sectionTitle")
        disk_card.add(t3); disk_card.add(Divider())
        for d in data.get("disks",[]):
            disk_card.add(InfoRow(f"{d['model']}",
                f"{d['size_gb']} GB  |  {d['interface']}  |  {d['type']}  |  S/N: {d['serial']}"))
        disk_card.add(Divider())
        for p in data.get("partitions",[]):
            disk_card.add(InfoRow(f"{p['device']} ({p['fstype']})",
                f"{p['used_gb']} / {p['total_gb']} GB  ({p['pct']}% used)"))
            disk_card.add(ProgressRow(p['mountpoint'], int(p['pct']),100,
                "#e74c3c" if p['pct']>85 else "#e05c2a"))
        self._lay.addWidget(disk_card)

        # Network
        if data.get("adapters"):
            net_card = Card()
            t4 = QLabel("Network Adapters"); t4.setObjectName("sectionTitle")
            net_card.add(t4); net_card.add(Divider())
            for a in data["adapters"]:
                net_card.add(InfoRow(a['name'],
                    f"{a['description']}  |  {a['speed']}  |  MAC: {a['mac']}"))
            self._lay.addWidget(net_card)

        if data.get("monitors"):
            section("Monitors", [(f"Monitor {i+1}",m) for i,m in enumerate(data['monitors'])])

        self._lay.addStretch()
        self.status_message.emit("Specs loaded")

    def _export(self):
        if not self._data: return
        lines = ["AlCore — PC Specs Report","="*40,""]
        for k,v in self._data.items():
            if isinstance(v,list):
                lines.append(f"\n{k}:")
                for item in v: lines.append(f"  {item}")
            else:
                lines.append(f"{k}: {v}")
        self.export_report("PC_Specs","\n".join(lines))

# ── Disk Analyzer ─────────────────────────────────────────────────────────────
class DiskPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("disk"),"Storage usage by drive and folder"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        self._path_box = QLineEdit("C:\\")
        self._path_box.setFixedWidth(140)
        bar.add_widget(self._path_box)
        bar.add_button("Analyze","accentBtn",self._scan)
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("subText")
        bar.add_widget(self._status_lbl)
        bar.add_stretch()
        self._root.addWidget(bar)

        # Drive overview cards
        self._drives_layout = QHBoxLayout()
        self._drives_layout.setSpacing(12)
        self._root.addLayout(self._drives_layout)

        tabs = QTabWidget()
        self._folder_table = SmartTable(["Name","Type","Size (MB)","Path"])
        self._folder_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)
        self._folder_table.customContextMenuRequested.connect(self._folder_ctx)

        self._largest_table = SmartTable(["File Name","Size (MB)","Path"])
        self._largest_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)

        tabs.addTab(self._folder_table,"Folder Breakdown")
        tabs.addTab(self._largest_table,"Top 20 Largest Files")
        self._root.addWidget(tabs)
        self._load_drives()

    def _load_drives(self):
        try:
            import psutil
            while self._drives_layout.count():
                item = self._drives_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            for p in psutil.disk_partitions():
                try:
                    u = psutil.disk_usage(p.mountpoint)
                    c = StatCard(p.device, f"{u.percent:.1f}%",
                        "#e74c3c" if u.percent>85 else "#2ecc71")
                    c.setCursor(Qt.CursorShape.PointingHandCursor)
                    dev = p.device
                    c.mousePressEvent = lambda e, d=dev: self._select_drive(d)
                    self._drives_layout.addWidget(c)
                except: pass
        except: pass

    def _select_drive(self, device):
        path = device if device.endswith("\\") else device + "\\"
        self._path_box.setText(path)
        self._scan()

    def _scan(self):
        self._folder_table.clear_rows()
        self._largest_table.clear_rows()
        path = self._path_box.text() or "C:\\"
        self._status_lbl.setText("Scanning...")
        self._worker = DiskWorker(path)
        self._worker.progress.connect(lambda m: self._status_lbl.setText(m))
        self._worker.result.connect(self._on_result)
        self._worker.start()
        self._load_drives()

    def _on_result(self, data):
        self._items = data.get("folders",[])
        self._folder_table.clear_rows()
        for item in self._items:
            self._folder_table.add_row([item['name'],item['type'],
                                         str(item['size_mb']),item['path']])
        self._largest_table.clear_rows()
        for f in data.get("largest",[]):
            self._largest_table.add_row([f['name'],str(f['size_mb']),f['path']])
        self._status_lbl.setText(f"{len(self._items)} items")

    def _folder_ctx(self, pos):
        row = self._folder_table.rowAt(pos.y())
        if row < 0 or not hasattr(self,'_items') or row >= len(self._items): return
        item = self._items[row]
        menu = QMenu(self)
        menu.addAction("Open in Explorer", lambda: self.open_location(item['path']))
        menu.exec(self._folder_table.viewport().mapToGlobal(pos))

# ── Network Monitor ───────────────────────────────────────────────────────────
class NetworkPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._conns = []
        self._root.addWidget(SectionHeader(self.tr("network"),"Active connections and bandwidth usage"))
        self._root.addWidget(Divider())

        # Adapter info card
        self._adapter_card = Card()
        albl = QLabel("Network Adapters"); albl.setObjectName("sectionTitle")
        self._adapter_card.add(albl)
        self._adapter_lay = QVBoxLayout(); self._adapter_lay.setSpacing(4)
        self._adapter_card.add_layout(self._adapter_lay)
        self._root.addWidget(self._adapter_card)

        # Speed test card
        spd_card = Card()
        slbl = QLabel("Speed Test"); slbl.setObjectName("sectionTitle")
        spd_card.add(slbl)
        spd_row = QHBoxLayout(); spd_row.setSpacing(12)
        self._dl_card  = StatCard("Download","—","#2ecc71")
        self._ul_card  = StatCard("Upload","—","#3498db")
        self._ping_card= StatCard("Ping","—","#f39c12")
        self._jit_card = StatCard("Jitter","—","#e05c2a")
        for c in [self._dl_card,self._ul_card,self._ping_card,self._jit_card]:
            spd_row.addWidget(c)
        spd_card.add_layout(spd_row)
        self._spd_btn = QPushButton("Run Speed Test")
        self._spd_btn.setObjectName("accentBtn")
        self._spd_btn.clicked.connect(self._run_speedtest)
        self._spd_status = QLabel(""); self._spd_status.setObjectName("subText")
        spd_card.add(self._spd_btn)
        spd_card.add(self._spd_status)
        self._root.addWidget(spd_card)

        bar = ActionBar()
        bar.add_button("Scan","accentBtn",self._scan)
        bar.add_stretch()
        self._search = SearchBar("Filter by process or address...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["PID","Process","Local Address","Remote Address","Status","Type","Path"])
        self._table.horizontalHeader().setSectionResizeMode(6,QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)
        self._scan()

    def _scan(self):
        self._worker = NetworkWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, data):
        self._conns = data['connections']

        # Adapters
        while self._adapter_lay.count():
            item = self._adapter_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for a in data.get("adapters",[]):
            t = "📶 WiFi" if "wireless" in a.get("type","").lower() or "wi-fi" in a.get("name","").lower() else "🔌 LAN"
            self._adapter_lay.addWidget(InfoRow(
                f"{t} {a['name']}", f"{a['desc']}  |  {a['speed']}  |  MAC: {a['mac']}"))

        self._table.clear_rows()
        for c in self._conns:
            self._table.add_row([str(c['pid']),c['name'],c['laddr'],
                                  c['raddr'],c['status'],c['type'],c['exe']])
        self.status_message.emit(f"{len(self._conns)} active connections")

    def _run_speedtest(self):
        self._spd_btn.setEnabled(False)
        self._spd_status.setText("Running speed test...")
        self._dl_card.set_value("—")
        self._ul_card.set_value("—")
        self._ping_card.set_value("—")
        self._jit_card.set_value("—")
        self._spd_worker = SpeedTestWorker()
        self._spd_worker.progress.connect(lambda m: self._spd_status.setText(m))
        self._spd_worker.result.connect(self._on_speedtest)
        self._spd_worker.error.connect(lambda e: (self._spd_status.setText(f"Error: {e}"), self._spd_btn.setEnabled(True)))
        self._spd_worker.start()

    def _on_speedtest(self, data):
        self._dl_card.set_value(f"{data['download_mbps']} Mbps")
        self._ul_card.set_value(f"{data['upload_mbps']} Mbps")
        self._ping_card.set_value(f"{data['ping_ms']} ms")
        self._jit_card.set_value(f"{data['jitter_ms']} ms")
        self._spd_status.setText("Speed test complete")
        self._spd_btn.setEnabled(True)

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._conns): return
        c = self._conns[row]
        menu = QMenu(self)
        if c['pid']:
            menu.addAction("Kill Process", lambda: self._kill_pid(c['pid']))
        menu.addAction("Open File Location", lambda: self.open_location(c['exe']))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _kill_pid(self, pid):
        if not self.confirm(f"kill process {pid}"): return
        try:
            import psutil
            psutil.Process(pid).kill()
            self.status_message.emit(f"Killed PID {pid}")
            self._scan()
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

# ── Junk Cleaner ──────────────────────────────────────────────────────────────
class CleanerPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._items = []
        self._last_cleaned = None
        self._root.addWidget(SectionHeader(self.tr("cleaner"),"Clear temp files, cache, crash dumps"))
        self._root.addWidget(Divider())

        # Summary cards
        stats = QHBoxLayout(); stats.setSpacing(12)
        self._total_card  = StatCard("Total Junk","—","#e05c2a")
        self._files_card  = StatCard("Files Found","—","#f39c12")
        self._cats_card   = StatCard("Categories","—","#3498db")
        self._freed_card  = StatCard("Last Freed","—","#2ecc71")
        for c in [self._total_card,self._files_card,self._cats_card,self._freed_card]:
            stats.addWidget(c)
        self._root.addLayout(stats)

        bar = ActionBar()
        bar.add_button("Scan","accentBtn",self._scan)
        self._clean_btn = bar.add_button("Clean Selected","dangerBtn",self._clean)
        self._clean_btn.setEnabled(False)
        bar.add_button("Select All","flatBtn",self._select_all)
        bar.add_button("Deselect All","flatBtn",self._deselect_all)
        self._status_lbl = QLabel(""); self._status_lbl.setObjectName("subText")
        bar.add_widget(self._status_lbl)
        self._root.addWidget(bar)

        self._prog = QProgressBar()
        self._prog.setVisible(False)
        self._prog.setFixedHeight(6)
        self._root.addWidget(self._prog)

        self._table = SmartTable(["","Icon","Location","Description","Files","Size (MB)","Path"])
        self._table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0,30)
        self._table.setColumnWidth(1,40)
        self._root.addWidget(self._table)

    def _scan(self):
        self._table.clear_rows()
        self._status_lbl.setText("Scanning...")
        self._prog.setVisible(True); self._prog.setRange(0,0)
        self._worker = JunkScanWorker()
        self._worker.progress.connect(lambda m: self._status_lbl.setText(m))
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, items):
        self._items = items
        self._prog.setVisible(False)
        self._table.clear_rows()
        total_mb = total_files = 0
        for item in items:
            r = self._table.add_row(["",item['icon'],item['label'],item['desc'],
                                      str(item['files']),str(item['size_mb']),item['path']])
            chk = QCheckBox(); chk.setChecked(item['selected'])
            self._table.setCellWidget(r,0,chk)
            total_mb    += item['size_mb']
            total_files += item['files']
        self._total_card.set_value(f"{total_mb:.1f} MB")
        self._files_card.set_value(str(total_files))
        self._cats_card.set_value(str(len(items)))
        self._clean_btn.setEnabled(True)
        self._status_lbl.setText(f"Found {total_mb:.1f} MB of junk in {len(items)} categories")

    def _select_all(self):
        for r in range(self._table.rowCount()):
            chk = self._table.cellWidget(r,0)
            if chk: chk.setChecked(True)

    def _deselect_all(self):
        for r in range(self._table.rowCount()):
            chk = self._table.cellWidget(r,0)
            if chk: chk.setChecked(False)

    def _clean(self):
        selected = [self._items[r] for r in range(self._table.rowCount())
                    if r < len(self._items) and
                    isinstance(self._table.cellWidget(r,0),QCheckBox) and
                    self._table.cellWidget(r,0).isChecked()]
        if not selected: return
        if not self.confirm(f"delete junk from {len(selected)} locations"): return
        self._prog.setVisible(True); self._prog.setRange(0,0)
        self._clean_btn.setEnabled(False)
        self._worker2 = JunkCleanWorker(selected)
        self._worker2.progress.connect(lambda m: self._status_lbl.setText(m))
        self._worker2.done.connect(self._on_done)
        self._worker2.start()

    def _on_done(self, deleted, freed):
        freed_mb = round(freed/1024**2,1)
        self._prog.setVisible(False)
        self._freed_card.set_value(f"{freed_mb} MB")
        self._status_lbl.setText(f"✓ Cleaned {deleted} files — freed {freed_mb} MB")
        self._clean_btn.setEnabled(True)
        self._scan()

# ── Drivers ───────────────────────────────────────────────────────────────────
class DriversPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._drivers = []
        self._root.addWidget(SectionHeader(self.tr("drivers"),"Installed drivers — signed/unsigned/status"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan","accentBtn",self._scan)
        bar.add_button("Open Device Manager","flatBtn",
            lambda: subprocess.Popen("devmgmt.msc",shell=True,
                creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0))
        self._filter = QComboBox()
        self._filter.addItems(["All","Unsigned Only","Signed Only","Error Status"])
        self._filter.currentTextChanged.connect(self._apply_filter)
        bar.add_widget(self._filter)
        bar.add_stretch()
        self._search = SearchBar("Search drivers...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Device","Class","Version","Manufacturer","Date","Signed","Status"])
        self._table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)

    def _scan(self):
        self._worker = DriversWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()
        self.status_message.emit("Scanning drivers...")

    def _on_result(self, drivers):
        self._drivers = drivers
        self._render(drivers)
        unsigned = sum(1 for d in drivers if not d['signed'])
        self.status_message.emit(f"{len(drivers)} drivers — {unsigned} unsigned")

    def _render(self, drivers):
        self._table.clear_rows()
        for d in drivers:
            r = self._table.add_row([d['name'],d['class'],d['version'],
                                      d['manufacturer'],d['date'],
                                      "✓ Signed" if d['signed'] else "✗ Unsigned",
                                      d.get('status','')])
            if not d['signed']:
                item = QTableWidgetItem("✗ Unsigned ⚠")
                item.setForeground(QColor("#e74c3c"))
                self._table.setItem(r,5,item)

    def _apply_filter(self, f):
        for row in range(self._table.rowCount()):
            item = self._table.item(row,5)
            signed = item and "Signed" in item.text() and "Unsigned" not in item.text()
            status = (self._table.item(row,6) or QTableWidgetItem()).text()
            if f=="Unsigned Only":  self._table.setRowHidden(row, signed)
            elif f=="Signed Only":  self._table.setRowHidden(row, not signed)
            elif f=="Error Status": self._table.setRowHidden(row, "error" not in status.lower())
            else:                   self._table.setRowHidden(row, False)

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._drivers): return
        d = self._drivers[row]
        menu = QMenu(self)
        menu.addAction("Uninstall Driver", lambda: self._uninstall(d))
        menu.addAction("Update Driver (Device Manager)", lambda: subprocess.Popen(
            "devmgmt.msc", shell=True,
            creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0))
        menu.addAction("Disable Driver",   lambda: self._toggle(d,"disable"))
        menu.addAction("Enable Driver",    lambda: self._toggle(d,"enable"))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _uninstall(self, d):
        if not self.confirm(f"uninstall driver '{d['name']}'"): return
        _ps_hidden(f"pnputil /remove-device \"{d['device_id']}\"")
        self.status_message.emit(f"Driver uninstall sent: {d['name']}")
        self._scan()

    def _toggle(self, d, action):
        cmd = "Disable" if action=="disable" else "Enable"
        _ps_hidden(f"Get-PnpDevice | Where-Object {{$_.FriendlyName -like '*{d['name']}*'}} | {cmd}-PnpDevice -Confirm:$false")
        self.status_message.emit(f"{action.title()}d: {d['name']}")

# ── Scheduled Tasks ───────────────────────────────────────────────────────────
class TasksPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._tasks = []
        self._root.addWidget(SectionHeader(self.tr("tasks"),"View and manage scheduled tasks"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan","accentBtn",self._scan)
        self._filter = QComboBox()
        self._filter.addItems(["All","Ready","Running","Disabled"])
        self._filter.currentTextChanged.connect(self._apply_filter)
        bar.add_widget(self._filter)
        bar.add_stretch()
        self._search = SearchBar("Search tasks...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Task Name","Path","State","Last Run","Next Run","Author"])
        self._table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)
        self._scan()

    def _scan(self):
        self._worker = TasksWorker()
        self._worker.result.connect(self._on_result)
        self._worker.error.connect(lambda e: self.status_message.emit(f"Error: {e}"))
        self._worker.start()
        self.status_message.emit("Scanning scheduled tasks...")

    def _on_result(self, tasks):
        self._tasks = tasks
        self._table.clear_rows()
        for t in tasks:
            r = self._table.add_row([t['name'],t['path'],t['state'],
                                      t.get('last_run',''),t.get('next_run',''),t['author']])
            color = "#2ecc71" if t['state']=="Ready" else "#e74c3c" if t['state']=="Running" else "#888"
            item = QTableWidgetItem(t['state'])
            item.setForeground(QColor(color))
            self._table.setItem(r,2,item)
        self.status_message.emit(f"{len(tasks)} scheduled tasks")

    def _apply_filter(self, f):
        for row in range(self._table.rowCount()):
            state = (self._table.item(row,2) or QTableWidgetItem()).text()
            if f=="All": self._table.setRowHidden(row,False)
            else: self._table.setRowHidden(row, state!=f)

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._tasks): return
        task = self._tasks[row]
        menu = QMenu(self)
        menu.addAction("Disable Task", lambda: self._action(task,"disable"))
        menu.addAction("Enable Task",  lambda: self._action(task,"enable"))
        menu.addAction("Run Now",      lambda: self._action(task,"run"))
        menu.addAction("Delete Task",  lambda: self._delete(task))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _action(self, t, action):
        cmds = {
            "disable": f"Disable-ScheduledTask -TaskName '{t['name']}' -TaskPath '{t['path']}'",
            "enable":  f"Enable-ScheduledTask  -TaskName '{t['name']}' -TaskPath '{t['path']}'",
            "run":     f"Start-ScheduledTask   -TaskName '{t['name']}' -TaskPath '{t['path']}'",
        }
        _ps_hidden(cmds[action])
        self._scan()

    def _delete(self, t):
        if self.confirm(f"delete task '{t['name']}'"):
            _ps_hidden(f"Unregister-ScheduledTask -TaskName '{t['name']}' -Confirm:$false")
            self._scan()

# ── Windows Features ──────────────────────────────────────────────────────────
class WinFeaturesPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._features = []
        self._root.addWidget(SectionHeader(self.tr("winfeatures"),"Enable or disable optional Windows components"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan","accentBtn",self._scan)
        self._filter = QComboBox()
        self._filter.addItems(["All","Enabled","Disabled"])
        self._filter.currentTextChanged.connect(self._apply_filter)
        bar.add_widget(self._filter)
        bar.add_stretch()
        self._search = SearchBar("Search features...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Feature Name","State","Plain English Description"])
        self._table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)

    def _scan(self):
        self._worker = WinFeaturesWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()
        self.status_message.emit("Scanning Windows features...")

    def _on_result(self, features):
        self._features = features
        self._table.clear_rows()
        for f in features:
            r = self._table.add_row([f['name'], f['state'], f['description']])
            color = "#2ecc71" if f['enabled'] else "#888"
            item = QTableWidgetItem(f['state'])
            item.setForeground(QColor(color))
            self._table.setItem(r,1,item)
        enabled = sum(1 for f in features if f['enabled'])
        self.status_message.emit(f"{len(features)} features — {enabled} enabled")

    def _apply_filter(self, f):
        for row in range(self._table.rowCount()):
            state = (self._table.item(row,1) or QTableWidgetItem()).text()
            if f=="Enabled":  self._table.setRowHidden(row, state!="Enabled")
            elif f=="Disabled":self._table.setRowHidden(row, state=="Enabled")
            else: self._table.setRowHidden(row, False)

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._features): return
        feat = self._features[row]
        menu = QMenu(self)
        if feat['enabled']:
            menu.addAction("Disable Feature", lambda: self._toggle(feat,False))
        else:
            menu.addAction("Enable Feature",  lambda: self._toggle(feat,True))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _toggle(self, feat, enable):
        if not self.confirm(f"{'enable' if enable else 'disable'} '{feat['name']}'"): return
        cmd = "Enable-WindowsOptionalFeature" if enable else "Disable-WindowsOptionalFeature"
        _ps_hidden(f"{cmd} -Online -FeatureName '{feat['name']}' -NoRestart")
        self.status_message.emit("Requires restart to take effect.")
        self._scan()

# ── Battery ───────────────────────────────────────────────────────────────────
class BatteryPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("battery"),"Battery health and capacity"))
        self._root.addWidget(Divider())
        bar = ActionBar()
        bar.add_button("Scan","accentBtn",self._scan)
        self._root.addWidget(bar)
        self._card = Card()
        self._root.addWidget(self._card)
        self._root.addStretch()
        self._scan()

    def _scan(self):
        self._worker = BatteryWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, data):
        while self._card.layout().count():
            item = self._card.layout().takeAt(0)
            if item.widget(): item.widget().deleteLater()
        if not data.get("present"):
            lbl = QLabel("No battery detected — desktop system")
            lbl.setObjectName("subText")
            self._card.add(lbl)
            return
        self._card.add(InfoRow("Charge Level",  f"{data['percent']}%"))
        self._card.add(InfoRow("Power Source",  "Plugged In" if data['plugged'] else "On Battery"))
        if data['secs_left'] and data['secs_left']>0 and not data['plugged']:
            mins = data['secs_left']//60
            self._card.add(InfoRow("Time Remaining",f"{mins//60}h {mins%60}m"))
        if data.get('design_cap'):
            self._card.add(InfoRow("Design Capacity",f"{data['design_cap']} mWh"))
            self._card.add(InfoRow("Full Charge Cap", f"{data['full_cap']} mWh"))
        if data.get('health_pct') is not None:
            h = data['health_pct']
            color = "#2ecc71" if h>80 else "#f39c12" if h>60 else "#e74c3c"
            self._card.add(ProgressRow("Battery Health",int(h),100,color))
            self._card.add(InfoRow("Health",f"{h}% — {'Good' if h>80 else 'Fair' if h>60 else 'Poor'}"))

# ── Windows Updates ───────────────────────────────────────────────────────────
class UpdatesPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._updates = []
        self._root.addWidget(SectionHeader(self.tr("updates"),"Installed Windows updates"))
        self._root.addWidget(Divider())
        bar = ActionBar()
        bar.add_button("Load History","accentBtn",self._scan)
        bar.add_button("Open Windows Update","flatBtn",
            lambda: subprocess.Popen("start ms-settings:windowsupdate",shell=True,
                creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0))
        bar.add_button("Pause Updates (7 days)","flatBtn",self._pause)
        self._root.addWidget(bar)
        self._table = SmartTable(["KB ID","Type","Installed On","Installed By"])
        self._table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)

    def _scan(self):
        self._worker = UpdatesWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()
        self.status_message.emit("Loading update history...")

    def _on_result(self, updates):
        self._updates = updates
        self._table.clear_rows()
        for u in updates:
            self._table.add_row([u['id'],u['description'],
                                  u['installed_on'],u['installed_by']])
        self.status_message.emit(f"{len(updates)} updates installed")

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._updates): return
        u = self._updates[row]
        menu = QMenu(self)
        menu.addAction("Open KB Page", lambda: QDesktopServices.openUrl(QUrl(u['kb_url'])))
        menu.addAction("Uninstall Update", lambda: self._uninstall(u))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _uninstall(self, u):
        if self.confirm(f"uninstall update {u['id']}"):
            _ps_hidden(f"wusa /uninstall /kb:{u['id'].replace('KB','')} /quiet /norestart")
            self.status_message.emit(f"Uninstall sent for {u['id']}")

    def _pause(self):
        _ps_hidden('Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\WindowsUpdate\\UX\\Settings" -Name "PauseUpdatesExpiryTime" -Value ((Get-Date).AddDays(7).ToString("yyyy-MM-ddTHH:mm:ssZ"))')
        self.status_message.emit("Updates paused for 7 days")

# ── Registry Cleaner ──────────────────────────────────────────────────────────
class RegistryPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._issues = []
        self._root.addWidget(SectionHeader(self.tr("registry"),"Scan and fix orphaned registry entries"))
        self._root.addWidget(Divider())

        stats = QHBoxLayout(); stats.setSpacing(12)
        self._found_card  = StatCard("Issues Found","—","#e05c2a")
        self._safe_card   = StatCard("Safe to Fix","—","#2ecc71")
        self._caution_card= StatCard("Caution","—","#f39c12")
        for c in [self._found_card,self._safe_card,self._caution_card]:
            stats.addWidget(c)
        self._root.addLayout(stats)

        bar = ActionBar()
        bar.add_button("Scan Registry","accentBtn",self._scan)
        self._fix_btn = bar.add_button("Fix Selected","dangerBtn",self._fix_selected)
        self._fix_btn.setEnabled(False)
        bar.add_button("Backup Registry","flatBtn",self._backup)
        self._status_lbl = QLabel(""); self._status_lbl.setObjectName("subText")
        bar.add_widget(self._status_lbl)
        self._root.addWidget(bar)

        self._prog = QProgressBar()
        self._prog.setVisible(False); self._prog.setFixedHeight(6)
        self._root.addWidget(self._prog)

        self._table = SmartTable(["","Type","Risk","Registry Key","Description"])
        self._table.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0,30)
        self._root.addWidget(self._table)

    def _scan(self):
        self._table.clear_rows()
        self._prog.setVisible(True); self._prog.setRange(0,0)
        self._worker = RegistryWorker()
        self._worker.progress.connect(lambda m: self._status_lbl.setText(m))
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, issues):
        self._issues = issues
        self._prog.setVisible(False)
        self._table.clear_rows()
        safe = caution = 0
        for issue in issues:
            r = self._table.add_row(["",issue['type'],issue['risk'],
                                      issue['key'],issue['desc']])
            chk = QCheckBox(); chk.setChecked(True)
            self._table.setCellWidget(r,0,chk)
            risk_item = QTableWidgetItem(issue['risk'])
            risk_item.setForeground(QColor(
                "#2ecc71" if issue['risk']=="Safe" else "#f39c12"))
            self._table.setItem(r,2,risk_item)
            if issue['risk']=="Safe": safe+=1
            else: caution+=1
        self._found_card.set_value(str(len(issues)))
        self._safe_card.set_value(str(safe))
        self._caution_card.set_value(str(caution))
        self._fix_btn.setEnabled(bool(issues))
        self._status_lbl.setText(f"Found {len(issues)} issues — backup before fixing recommended")

    def _backup(self):
        path, _ = QFileDialog.getSaveFileName(self,"Backup Registry",
            "registry_backup.reg","Registry Files (*.reg)")
        if path:
            _ps_hidden(f'reg export HKLM "{path}" /y')
            self.status_message.emit(f"Registry backed up to {path}")

    def _fix_selected(self):
        if not self.confirm(f"fix selected registry issues"): return
        import winreg
        fixed = 0
        for i, issue in enumerate(self._issues):
            chk = self._table.cellWidget(i,0)
            if not (chk and chk.isChecked()): continue
            try:
                if issue['hive'] and issue['path'] and issue['subkey']:
                    key = winreg.OpenKey(issue['hive'],issue['path'],0,winreg.KEY_WRITE)
                    try:
                        winreg.DeleteKey(key, issue['subkey'])
                    except:
                        winreg.DeleteValue(key, issue['subkey'])
                    winreg.CloseKey(key)
                    fixed += 1
            except: pass
        self._status_lbl.setText(f"Fixed {fixed} issues")
        self._scan()

# ── Hosts File ────────────────────────────────────────────────────────────────
class HostsPage(BasePage):
    HOSTS = r"C:\Windows\System32\drivers\etc\hosts"

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("hosts"),"View and edit the Windows hosts file"))
        self._root.addWidget(Divider())
        bar = ActionBar()
        bar.add_button("Load","accentBtn",self._load)
        bar.add_button("Save","flatBtn",self._save)
        bar.add_button("Add Entry","flatBtn",self._add_entry)
        self._root.addWidget(bar)
        self._editor = QTextEdit()
        self._editor.setFont(QFont("Consolas",11))
        self._root.addWidget(self._editor)
        self._load()

    def _load(self):
        try:
            with open(self.HOSTS,"r") as f:
                self._editor.setPlainText(f.read())
        except Exception as e:
            self._editor.setPlainText(f"# Error: {e}\n# Run as Administrator")

    def _save(self):
        if not self.confirm("overwrite the hosts file"): return
        try:
            with open(self.HOSTS,"w") as f:
                f.write(self._editor.toPlainText())
            self.status_message.emit("Hosts file saved")
        except PermissionError:
            self.status_message.emit("Error: Run as Administrator")
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

    def _add_entry(self):
        self._editor.append("\n127.0.0.1    example.com  # comment")

# ── Environment Variables ─────────────────────────────────────────────────────
class EnvVarsPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("envvars"),"System and user environment variables"))
        self._root.addWidget(Divider())
        bar = ActionBar()
        bar.add_button("Load","accentBtn",self._load)
        bar.add_button("Open System Settings","flatBtn",
            lambda: subprocess.Popen("rundll32 sysdm.cpl,EditEnvironmentVariables",shell=True,
                creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0))
        bar.add_stretch()
        self._search = SearchBar("Search variables...")
        bar.add_widget(self._search)
        self._root.addWidget(bar)
        tabs = QTabWidget()
        self._sys_table  = SmartTable(["Variable","Value"])
        self._sys_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self._user_table = SmartTable(["Variable","Value"])
        self._user_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self._sys_table,"System")
        tabs.addTab(self._user_table,"User")
        self._search.textChanged.connect(lambda t: (
            self._sys_table.filter_rows(t), self._user_table.filter_rows(t)))
        self._root.addWidget(tabs)
        self._load()

    def _load(self):
        import winreg
        for table, hive, path in [
            (self._sys_table,  winreg.HKEY_LOCAL_MACHINE,
             r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (self._user_table, winreg.HKEY_CURRENT_USER, r"Environment"),
        ]:
            table.clear_rows()
            try:
                key = winreg.OpenKey(hive,path)
                for i in range(winreg.QueryInfoKey(key)[1]):
                    try:
                        name,val,_ = winreg.EnumValue(key,i)
                        table.add_row([name,str(val)])
                    except: pass
                winreg.CloseKey(key)
            except: pass

# ── Font Manager ──────────────────────────────────────────────────────────────
class FontsPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._fonts = []
        self._root.addWidget(SectionHeader(self.tr("fonts"),"Installed fonts — preview and manage"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan","accentBtn",self._scan)
        bar.add_button("Install Font","flatBtn",self._install)
        bar.add_button("Open Fonts Folder","flatBtn",
            lambda: subprocess.Popen("explorer C:\\Windows\\Fonts",shell=True,
                creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0))

        # Preview size slider
        self._preview_size = 14
        size_lbl = QLabel("Preview Size:")
        size_lbl.setObjectName("subText")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(10); slider.setMaximum(32); slider.setValue(14)
        slider.setFixedWidth(100)
        slider.valueChanged.connect(self._on_size_change)
        bar.add_stretch()
        bar.add_widget(size_lbl)
        bar.add_widget(slider)

        self._filter = QComboBox()
        self._filter.addItems(["All","TrueType","OpenType","Bitmap"])
        self._filter.currentTextChanged.connect(self._apply_filter)
        bar.add_widget(self._filter)
        self._search = SearchBar("Search fonts...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Font Name","Type","Size (KB)","Preview","File"])
        self._table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)

    def _on_size_change(self, v):
        self._preview_size = v
        if self._fonts: self._render(self._fonts)

    def _scan(self):
        self._worker = FontsWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, fonts):
        self._fonts = fonts
        self._render(fonts)
        self.status_message.emit(f"{len(fonts)} fonts installed")

    def _render(self, fonts):
        self._table.clear_rows()
        for f in fonts:
            r = self._table.add_row([f['name'],f['type'],str(f['size_kb']),"",""])
            # Live font preview
            preview = QLabel("AaBbCc 123 أبج")
            try:
                font = QFont(f['name'].split("(")[0].strip(), self._preview_size)
                preview.setFont(font)
            except: pass
            preview.setStyleSheet("padding: 2px 8px;")
            self._table.setCellWidget(r,3,preview)
            file_item = QTableWidgetItem(f['file'])
            self._table.setItem(r,4,file_item)

    def _apply_filter(self, f):
        for row in range(self._table.rowCount()):
            t = (self._table.item(row,1) or QTableWidgetItem()).text()
            if f=="All": self._table.setRowHidden(row,False)
            else: self._table.setRowHidden(row, f not in t)

    def _install(self):
        path, _ = QFileDialog.getOpenFileName(self,"Select Font File","",
            "Font Files (*.ttf *.otf *.fon *.ttc)")
        if not path: return
        import shutil
        dest = os.path.join(os.environ.get("WINDIR","C:\\Windows"),"Fonts",os.path.basename(path))
        try:
            shutil.copy2(path, dest)
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",0,winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, os.path.splitext(os.path.basename(path))[0],
                0, winreg.REG_SZ, os.path.basename(path))
            winreg.CloseKey(key)
            self.status_message.emit(f"Font installed: {os.path.basename(path)}")
            self._scan()
        except Exception as e:
            self.status_message.emit(f"Error installing font: {e}")

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._fonts): return
        font = self._fonts[row]
        menu = QMenu(self)
        menu.addAction("Open File Location", lambda: self.open_location(font['path']))
        menu.addAction("Uninstall Font",     lambda: self._uninstall(font,row))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _uninstall(self, font, row):
        if not self.confirm(f"uninstall font '{font['name']}'"): return
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",0,winreg.KEY_WRITE)
            winreg.DeleteValue(key,font['name'])
            winreg.CloseKey(key)
            try: os.remove(font['path'])
            except: pass
            self._fonts.pop(row)
            self._table.removeRow(row)
            self.status_message.emit(f"Removed: {font['name']}")
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

# ── Windows Tweaks ────────────────────────────────────────────────────────────
TWEAKS = {
    "Privacy & Telemetry": [
        ("Disable Telemetry",              "Stops Windows sending usage data to Microsoft",
         "HKLM",r"SOFTWARE\Policies\Microsoft\Windows\DataCollection","AllowTelemetry","0","REG_DWORD"),
        ("Disable Activity History",       "Prevents Windows tracking app/web activity",
         "HKLM",r"SOFTWARE\Policies\Microsoft\Windows\System","EnableActivityFeed","0","REG_DWORD"),
        ("Disable Advertising ID",         "Stops apps using your advertising ID",
         "HKCU",r"SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo","Enabled","0","REG_DWORD"),
        ("Disable Cortana",                "Prevents Cortana from running",
         "HKLM",r"SOFTWARE\Policies\Microsoft\Windows\Windows Search","AllowCortana","0","REG_DWORD"),
        ("Disable Windows Error Reporting", "Stops sending crash reports to Microsoft",
         "HKLM",r"SOFTWARE\Microsoft\Windows\Windows Error Reporting","Disabled","1","REG_DWORD"),
        ("Disable Customer Experience",    "Disables CEIP data collection",
         "HKLM",r"SOFTWARE\Policies\Microsoft\SQMClient\Windows","CEIPEnable","0","REG_DWORD"),
        ("Disable Timeline",               "Disables Windows Timeline/Task View history",
         "HKLM",r"SOFTWARE\Policies\Microsoft\Windows\System","EnableActivityFeed","0","REG_DWORD"),
        ("Disable Clipboard Sync",         "Stops clipboard history syncing to cloud",
         "HKCU",r"SOFTWARE\Microsoft\Clipboard","EnableClipboardHistory","0","REG_DWORD"),
        ("Disable Diagnostic Data",        "Minimizes diagnostic data sent to Microsoft",
         "HKLM",r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection","AllowTelemetry","0","REG_DWORD"),
    ],
    "Hidden UI Tweaks": [
        ("Classic Right-Click Menu",       "Restores Windows 10 context menu in Windows 11",
         "HKCU",r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32","(Default)","","REG_SZ"),
        ("Show File Extensions",           "Always show file extensions in Explorer",
         "HKCU",r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","HideFileExt","0","REG_DWORD"),
        ("Show Hidden Files",              "Show hidden files and folders",
         "HKCU",r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","Hidden","1","REG_DWORD"),
        ("Show Full Path in Title Bar",    "Displays full folder path in Explorer title",
         "HKCU",r"Software\Microsoft\Windows\CurrentVersion\Explorer\CabinetState","FullPath","1","REG_DWORD"),
        ("Disable Sticky Keys Prompt",     "Stops Sticky Keys popup on 5x Shift",
         "HKCU",r"Control Panel\Accessibility\StickyKeys","Flags","506","REG_SZ"),
        ("Disable Snap Suggestions",       "Removes snap layout suggestions popup",
         "HKCU",r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","SnapAssist","0","REG_DWORD"),
        ("Verbose Boot Messages",          "Shows detailed messages during startup",
         "HKLM",r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System","VerboseStatus","1","REG_DWORD"),
        ("Remove Widgets from Taskbar",    "Hides the Widgets button in Windows 11",
         "HKCU",r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","TaskbarDa","0","REG_DWORD"),
        ("Remove Chat from Taskbar",       "Hides Teams/Chat button in Windows 11",
         "HKCU",r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","TaskbarMn","0","REG_DWORD"),
        ("Disable Thumbnail Previews",     "Disables file thumbnail preview generation",
         "HKCU",r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced","IconsOnly","1","REG_DWORD"),
        ("Disable Recent Files in Quick Access","Stops showing recent files in Explorer",
         "HKCU",r"Software\Microsoft\Windows\CurrentVersion\Explorer","ShowRecent","0","REG_DWORD"),
    ],
    "Performance": [
        ("Disable Animations",             "Turns off window animations for faster UI",
         "HKCU",r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects","VisualFXSetting","2","REG_DWORD"),
        ("Disable Transparency",           "Removes Aero transparency effects",
         "HKCU",r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize","EnableTransparency","0","REG_DWORD"),
        ("Disable Superfetch/SysMain",     "Disables SysMain service to reduce disk usage",
         "HKLM",r"SYSTEM\CurrentControlSet\Services\SysMain","Start","4","REG_DWORD"),
        ("Disable Windows Tips",           "Stops Windows from showing tips and suggestions",
         "HKCU",r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager","SoftLandingEnabled","0","REG_DWORD"),
        ("Disable Hibernation",            "Frees disk space by disabling hibernate",
         "HKLM",r"SYSTEM\CurrentControlSet\Control\Power","HibernateEnabled","0","REG_DWORD"),
        ("Disable Fast Startup",           "Disables fast startup (can cause update issues)",
         "HKLM",r"SYSTEM\CurrentControlSet\Control\Session Manager\Power","HiberbootEnabled","0","REG_DWORD"),
        ("Disable USB Selective Suspend",  "Prevents USB devices from sleeping",
         "HKLM",r"SYSTEM\CurrentControlSet\Services\USB","DisableSelectiveSuspend","1","REG_DWORD"),
    ],
    "Gaming": [
        ("Disable Xbox Game Bar",          "Removes Xbox Game Bar overlay",
         "HKCU",r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR","AppCaptureEnabled","0","REG_DWORD"),
        ("Disable Fullscreen Optimizations","Stops Windows modifying fullscreen apps",
         "HKCU",r"System\GameConfigStore","GameDVR_FSEBehaviorMode","2","REG_DWORD"),
        ("Enable HAGS",                    "Hardware Accelerated GPU Scheduling for better FPS",
         "HKLM",r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers","HwSchMode","2","REG_DWORD"),
        ("Disable Mouse Pointer Precision", "Disables mouse acceleration for raw input",
         "HKCU",r"Control Panel\Mouse","MouseSpeed","0","REG_SZ"),
        ("Disable Nagle's Algorithm",      "Reduces network latency in online games",
         "HKLM",r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters","TcpAckFrequency","1","REG_DWORD"),
        ("Priority to Games",             "Sets foreground app to get more CPU time",
         "HKLM",r"SYSTEM\CurrentControlSet\Control\PriorityControl","Win32PrioritySeparation","38","REG_DWORD"),
    ],
    "Security": [
        ("Disable SmartScreen",            "Turns off Windows SmartScreen filter",
         "HKLM",r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer","SmartScreenEnabled","Off","REG_SZ"),
        ("Disable Remote Assistance",      "Prevents remote assistance connections",
         "HKLM",r"SYSTEM\CurrentControlSet\Control\Remote Assistance","fAllowToGetHelp","0","REG_DWORD"),
        ("Disable AutoRun",                "Prevents AutoRun from running on USB/CD insert",
         "HKLM",r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer","NoDriveTypeAutoRun","255","REG_DWORD"),
        ("Disable Guest Account",          "Ensures guest account is disabled",
         "HKLM",r"SAM\SAM\Domains\Account\Users\000001F5","F","","REG_BINARY"),
    ],
    "Network Tweaks": [
        ("Disable IPv6",                   "Disables IPv6 on all network adapters",
         "HKLM",r"SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters","DisabledComponents","255","REG_DWORD"),
        ("Disable LLMNR",                  "Disables Link-Local Multicast Name Resolution",
         "HKLM",r"SOFTWARE\Policies\Microsoft\Windows NT\DNSClient","EnableMulticast","0","REG_DWORD"),
        ("Limit Bandwidth Reserve",        "Removes QoS 20% bandwidth reservation",
         "HKLM",r"SOFTWARE\Policies\Microsoft\Windows\Psched","NonBestEffortLimit","0","REG_DWORD"),
        ("Disable Wi-Fi Sense",            "Disables automatic Wi-Fi hotspot sharing",
         "HKLM",r"SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\config","AutoConnectAllowedOEM","0","REG_DWORD"),
        ("Disable Network Throttling",     "Removes multimedia network throttling",
         "HKLM",r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile","NetworkThrottlingIndex","4294967295","REG_DWORD"),
    ],
}

class TweaksPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._tweak_rows = []
        self._root.addWidget(SectionHeader(self.tr("tweaks"),"Hidden Windows settings and tweaks"))
        self._root.addWidget(Divider())

        preset_bar = ActionBar()
        preset_bar.add_button("🎮 Gaming Mode",  "flatBtn", lambda: self._apply_preset("gaming"))
        preset_bar.add_button("🔒 Privacy Mode", "flatBtn", lambda: self._apply_preset("privacy"))
        preset_bar.add_button("⚡ Performance",  "flatBtn", lambda: self._apply_preset("performance"))
        preset_bar.add_stretch()
        preset_bar.add_button("↺ Reload State", "flatBtn", self._reload_state)
        preset_bar.add_button("Apply All Enabled","accentBtn",self._apply_all)
        preset_bar.add_button("God Mode Folder",  "flatBtn", self._god_mode)
        self._root.addWidget(preset_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(16)
        lay.setContentsMargins(0,4,4,4)

        for category, tweaks in TWEAKS.items():
            cat_lbl = QLabel(category)
            cat_lbl.setObjectName("sectionTitle")
            lay.addWidget(cat_lbl)
            for tweak in tweaks:
                title, desc, hive, path, name, value, reg_type = tweak
                # Read actual current state from registry
                current = self._read_reg(hive, path, name)
                is_on = self._is_applied(current, value, reg_type)
                row = TweakRow(title, desc, checked=is_on)
                row.setProperty("hive",    hive)
                row.setProperty("rpath",   path)
                row.setProperty("rname",   name)
                row.setProperty("rval",    value)
                row.setProperty("rtype",   reg_type)
                row.setProperty("title",   title)
                self._tweak_rows.append(row)
                lay.addWidget(row)
            lay.addWidget(Divider())

        lay.addStretch()
        scroll.setWidget(container)
        self._root.addWidget(scroll)

    def _read_reg(self, hive, path, name):
        """Read current registry value. Returns None if key doesn't exist."""
        try:
            import winreg
            h = winreg.HKEY_LOCAL_MACHINE if hive=="HKLM" else winreg.HKEY_CURRENT_USER
            key = winreg.OpenKey(h, path, 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, name)
            winreg.CloseKey(key)
            return val
        except:
            return None

    def _is_applied(self, current_val, target_val, reg_type):
        """Check if tweak is currently applied by comparing registry value."""
        if current_val is None:
            return False
        try:
            if reg_type == "REG_DWORD":
                return int(current_val) == int(target_val)
            else:
                return str(current_val).strip().lower() == str(target_val).strip().lower()
        except:
            return False

    def _reload_state(self):
        """Re-read all registry values and update toggle states."""
        for row in self._tweak_rows:
            hive  = row.property("hive")
            path  = row.property("rpath")
            name  = row.property("rname")
            value = row.property("rval")
            rtype = row.property("rtype")
            current = self._read_reg(hive, path, name)
            is_on = self._is_applied(current, value, rtype)
            row.set_checked(is_on)
        self.status_message.emit("Tweak states reloaded from registry")

    def _apply_all(self):
        applied = 0
        for row in self._tweak_rows:
            if row.is_checked():
                self._apply_tweak(row)
                applied += 1
        self.status_message.emit(f"Applied {applied} tweaks — some require restart")

    def _apply_tweak(self, row):
        hive   = row.property("hive")
        path   = row.property("rpath")
        name   = row.property("rname")
        value  = row.property("rval")
        rtype  = row.property("rtype")
        try:
            import winreg
            h = winreg.HKEY_LOCAL_MACHINE if hive=="HKLM" else winreg.HKEY_CURRENT_USER
            key = winreg.CreateKeyEx(h, path, 0, winreg.KEY_SET_VALUE)
            if rtype == "REG_DWORD":
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(value))
            else:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            winreg.CloseKey(key)
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

    def _apply_preset(self, preset):
        PRESETS = {
            "gaming":       ["Disable Xbox Game Bar","Disable Fullscreen Optimizations",
                             "Enable HAGS","Disable Mouse Pointer Precision",
                             "Disable Nagle's Algorithm","Priority to Games",
                             "Disable Animations","Disable Transparency"],
            "privacy":      ["Disable Telemetry","Disable Activity History","Disable Advertising ID",
                             "Disable Cortana","Disable Windows Error Reporting",
                             "Disable Customer Experience","Disable Clipboard Sync"],
            "performance":  ["Disable Animations","Disable Transparency","Disable Superfetch/SysMain",
                             "Disable Windows Tips","Disable Hibernation"],
        }
        names = PRESETS.get(preset,[])
        applied = 0
        for row in self._tweak_rows:
            if row.property("title") in names:
                row.set_checked(True)
                self._apply_tweak(row)
                applied += 1
        self.status_message.emit(f"Preset '{preset}' — {applied} tweaks applied")

    def _god_mode(self):
        try:
            desktop = os.path.join(os.path.expanduser("~"),"Desktop")
            god = os.path.join(desktop,"GodMode.{ED7BA470-8E54-465E-825C-99712043E01C}")
            os.makedirs(god, exist_ok=True)
            subprocess.Popen(f'explorer "{god}"',
                creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0)
            self.status_message.emit("God Mode folder created on Desktop")
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

# ── Settings ──────────────────────────────────────────────────────────────────
class SettingsPage(BasePage):
    theme_changed    = pyqtSignal(str)
    language_changed = pyqtSignal(str)
    check_update_now = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader("Settings","Configure AlCore"))
        self._root.addWidget(Divider())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(12); lay.setContentsMargins(0,0,4,0)

        # Appearance
        theme_card = Card()
        theme_card.add(self._lbl("Appearance"))
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme"))
        theme_row.addStretch()
        self._theme_lbl = QLabel("Dark" if settings.get("theme","dark")=="dark" else "Light")
        self._theme_lbl.setObjectName("subText")
        self._theme_toggle = ToggleSwitch(checked=settings.get("theme","dark")=="light")
        self._theme_toggle.toggled.connect(self._on_theme)
        theme_row.addWidget(self._theme_lbl)
        theme_row.addWidget(self._theme_toggle)
        theme_card.add_layout(theme_row)
        lay.addWidget(theme_card)

        # Language
        lang_card = Card()
        lang_card.add(self._lbl("Language"))
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("UI Language"))
        lang_row.addStretch()
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["English","العربية"])
        self._lang_combo.setCurrentIndex(0 if settings.get("language","en")=="en" else 1)
        self._lang_combo.currentIndexChanged.connect(self._on_lang)
        lang_row.addWidget(self._lang_combo)
        lang_card.add_layout(lang_row)
        lay.addWidget(lang_card)

        # Behavior
        behav_card = Card()
        behav_card.add(self._lbl("Behavior"))
        for key, label in [
            ("start_with_windows","Start with Windows"),
            ("minimize_to_tray",  "Minimize to system tray"),
            ("notifications_enabled","Show notifications"),
            ("scan_on_launch",    "Auto-scan on launch"),
            ("auto_update_check", "Auto-check for updates on launch"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addStretch()
            toggle = ToggleSwitch(checked=settings.get(key,False))
            k = key
            toggle.toggled.connect(lambda v, k=k: settings.update({k:v}))
            row.addWidget(toggle)
            w = QWidget(); w.setLayout(row)
            behav_card.add(w)
        lay.addWidget(behav_card)

        # Polling
        poll_card = Card()
        poll_card.add(self._lbl("Live Polling Interval"))
        poll_row = QHBoxLayout()
        poll_row.addWidget(QLabel("Refresh every"))
        self._poll_slider = QSlider(Qt.Orientation.Horizontal)
        self._poll_slider.setMinimum(1); self._poll_slider.setMaximum(10)
        self._poll_slider.setValue(settings.get("polling_interval",2))
        self._poll_val = QLabel(f"{settings.get('polling_interval',2)}s")
        self._poll_slider.valueChanged.connect(
            lambda v: (self._poll_val.setText(f"{v}s"),settings.update({"polling_interval":v})))
        poll_row.addWidget(self._poll_slider)
        poll_row.addWidget(self._poll_val)
        poll_card.add_layout(poll_row)
        lay.addWidget(poll_card)

        # Updates
        upd_card = Card()
        upd_card.add(self._lbl("Updates"))
        check_btn = QPushButton("Check for Updates Now")
        check_btn.setObjectName("flatBtn")
        check_btn.clicked.connect(self.check_update_now.emit)
        upd_card.add(check_btn)
        lay.addWidget(upd_card)

        # About
        about_card = Card()
        about_card.add(self._lbl("About"))
        from config import APP_NAME, APP_VERSION, APP_AUTHOR, GITHUB_REPO
        about_card.add(InfoRow("Application", APP_NAME))
        about_card.add(InfoRow("Version",     APP_VERSION))
        about_card.add(InfoRow("Developer",   APP_AUTHOR))
        gh_btn = QPushButton(f"github.com/{GITHUB_REPO}")
        gh_btn.setObjectName("iconBtn")
        gh_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl(f"https://github.com/{GITHUB_REPO}")))
        about_card.add(gh_btn)
        lay.addWidget(about_card)

        # Reset
        reset_card = Card()
        reset_card.add(self._lbl("Reset"))
        reset_btn = QPushButton("Reset All Settings to Default")
        reset_btn.setObjectName("dangerBtn")
        reset_btn.clicked.connect(self._reset)
        reset_card.add(reset_btn)
        lay.addWidget(reset_card)

        lay.addStretch()
        scroll.setWidget(container)
        self._root.addWidget(scroll)

    def _lbl(self, text):
        l = QLabel(text); l.setObjectName("sectionTitle"); return l

    def _on_theme(self, light):
        mode = "light" if light else "dark"
        self._theme_lbl.setText("Light" if light else "Dark")
        self.settings["theme"] = mode
        self.theme_changed.emit(mode)

    def _on_lang(self, idx):
        lang = "en" if idx==0 else "ar"
        self.settings["language"] = lang
        self.language_changed.emit(lang)

    def _reset(self):
        from config import DEFAULT_SETTINGS, save_settings
        self.settings.update(DEFAULT_SETTINGS)
        save_settings(self.settings)
        self.status_message.emit("Settings reset to defaults")
