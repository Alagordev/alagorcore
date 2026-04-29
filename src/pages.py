import os, sys, subprocess, webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QLineEdit, QScrollArea, QFrame, QSplitter, QTextEdit,
    QComboBox, QCheckBox, QTabWidget, QFileDialog, QMenu,
    QApplication, QSizePolicy, QGridLayout, QSpacerItem
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QAction
from widgets import (StatCard, SectionHeader, SmartTable, SearchBar,
                     ActionBar, ConfirmDialog, ToggleSwitch, TweakRow,
                     InfoRow, Card, Divider, ProgressRow, StatusBadge)
from workers import (StartupWorker, RamWorker, CpuWorker, ServicesWorker,
                     InstalledAppsWorker, SpecsWorker, DiskWorker,
                     NetworkWorker, JunkScanWorker, JunkCleanWorker,
                     DriversWorker, TasksWorker, WinFeaturesWorker,
                     BatteryWorker, UpdatesWorker, RegistryWorker, FontsWorker)

# ── Base Page ─────────────────────────────────────────────────────────────────
class BasePage(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setObjectName("page")
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(24, 20, 24, 20)
        self._root.setSpacing(12)

    def tr(self, key, **kw):
        from translations import tr
        return tr(key, self.settings.get("language","en"), **kw)

    def confirm(self, action_text):
        dlg = ConfirmDialog(self.tr("confirm_title"),
                            self.tr("confirm_msg", action=action_text), self)
        return dlg.exec() == dlg.DialogCode.Accepted

    def open_location(self, path):
        if path and os.path.exists(path):
            subprocess.Popen(f'explorer /select,"{path}"')
        elif path:
            parent = os.path.dirname(path)
            if os.path.isdir(parent):
                subprocess.Popen(f'explorer "{parent}"')

    def export_report(self, title, content):
        path, _ = QFileDialog.getSaveFileName(self, f"Export {title}", f"{title}.txt",
                                               "Text Files (*.txt);;All Files (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.status_message.emit(f"Exported to {path}")

    def _ps(self, cmd, confirm_msg=""):
        if confirm_msg and not self.confirm(confirm_msg):
            return
        try:
            subprocess.run(["powershell","-NoProfile","-Command", cmd],
                           capture_output=True, timeout=30)
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

# ── Dashboard ─────────────────────────────────────────────────────────────────
class DashboardPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader("AlagorCore", "System Overview"))
        self._root.addWidget(Divider())

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.cpu_card  = StatCard("CPU Usage",  "—%",   "#e05c2a")
        self.ram_card  = StatCard("RAM Usage",  "—%",   "#3498db")
        self.disk_card = StatCard("Disk C:",    "—%",   "#2ecc71")
        self.procs_card= StatCard("Processes",  "—",    "#f39c12")
        for c in [self.cpu_card, self.ram_card, self.disk_card, self.procs_card]:
            stats_row.addWidget(c)
        self._root.addLayout(stats_row)

        # Progress bars
        pb_card = Card()
        pb_card.add(QLabel("Live Resource Usage").setObjectName("sectionTitle") or QLabel("Live Resource Usage"))
        self.cpu_bar = ProgressRow("CPU", 0, 100, "#e05c2a")
        self.ram_bar = ProgressRow("RAM", 0, 100, "#3498db")
        self.disk_bar= ProgressRow("Disk C:", 0, 100, "#2ecc71")
        pb_card.add(self.cpu_bar)
        pb_card.add(self.ram_bar)
        pb_card.add(self.disk_bar)
        self._root.addWidget(pb_card)

        self._root.addStretch()

        # Auto refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(2000)
        self._refresh()

    def _refresh(self):
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            vm  = psutil.virtual_memory()
            try:
                du = psutil.disk_usage("C:\\")
                disk_pct = du.percent
            except:
                disk_pct = 0
            procs = len(psutil.pids())

            self.cpu_card.set_value(f"{cpu:.1f}%")
            self.ram_card.set_value(f"{vm.percent:.1f}%")
            self.disk_card.set_value(f"{disk_pct:.1f}%")
            self.procs_card.set_value(str(procs))
            self.cpu_bar.set_value(cpu)
            self.ram_bar.set_value(vm.percent)
            self.disk_bar.set_value(disk_pct)
        except Exception:
            pass

# ── Startup Manager ───────────────────────────────────────────────────────────
class StartupPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._entries = []
        self._root.addWidget(SectionHeader(self.tr("startup"),
            "Manage programs that run when Windows starts"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
        self._search = SearchBar("Search startup entries...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_stretch()
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Name","Command","Location","Status"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)

        self._scan()

    def _scan(self):
        self._table.clear_rows()
        self.status_message.emit("Scanning startup entries...")
        self._worker = StartupWorker()
        self._worker.result.connect(self._on_result)
        self._worker.error.connect(lambda e: self.status_message.emit(f"Error: {e}"))
        self._worker.start()

    def _on_result(self, entries):
        self._entries = entries
        self._table.clear_rows()
        for e in entries:
            r = self._table.add_row([e['name'], e['command'], e['location'],
                                     "Enabled" if e['enabled'] else "Disabled"])
            status_item = QTableWidgetItem("Enabled" if e['enabled'] else "Disabled")
            status_item.setForeground(QColor("#2ecc71") if e['enabled'] else QColor("#e74c3c"))
            self._table.setItem(r, 3, status_item)
        self.status_message.emit(f"Found {len(entries)} startup entries")

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._entries): return
        entry = self._entries[row]
        menu  = QMenu(self)
        menu.addAction("Disable Entry", lambda: self._disable(entry, row))
        menu.addAction("Open File Location", lambda: self.open_location(entry['command'].split('"')[1] if '"' in entry['command'] else entry['command']))
        menu.addAction("Export PS1 Script", lambda: self._export_ps1(entry))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _disable(self, entry, row):
        if not self.confirm(f"disable '{entry['name']}' from startup"):
            return
        try:
            import winreg
            if entry['hive'] and entry['path']:
                key = winreg.OpenKey(entry['hive'], entry['path'], 0, winreg.KEY_WRITE)
                winreg.DeleteValue(key, entry['name'])
                winreg.CloseKey(key)
                self._entries.pop(row)
                self._table.removeRow(row)
                self.status_message.emit(f"Disabled: {entry['name']}")
            elif os.path.exists(entry['path']):
                os.remove(os.path.join(entry['path'], entry['name']))
                self._entries.pop(row)
                self._table.removeRow(row)
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

    def _export_ps1(self, entry):
        content = f"# Disable startup: {entry['name']}\n"
        content += f'Remove-ItemProperty -Path "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" -Name "{entry["name"]}" -Force\n'
        self.export_report("startup_disable", content)

# ── RAM Monitor ───────────────────────────────────────────────────────────────
class RamPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._procs = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._scan)
        self._live = False

        self._root.addWidget(SectionHeader(self.tr("ram"), "Memory usage and process breakdown"))
        self._root.addWidget(Divider())

        # Stats row
        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.total_card = StatCard("Total RAM",  "—")
        self.used_card  = StatCard("Used",       "—", "#e05c2a")
        self.free_card  = StatCard("Available",  "—", "#2ecc71")
        self.pct_card   = StatCard("Usage %",    "—", "#3498db")
        for c in [self.total_card, self.used_card, self.free_card, self.pct_card]:
            stats.addWidget(c)
        self._root.addLayout(stats)

        bar = ActionBar()
        bar.add_button("Scan / Refresh", "accentBtn", self._scan)
        self._live_btn = bar.add_button("Live OFF", "flatBtn", self._toggle_live)
        bar.add_stretch()
        self._search = SearchBar("Filter processes...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["PID","Process","RAM (MB)","RAM %","Status","Path"])
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)
        self._scan()

    def _toggle_live(self):
        self._live = not self._live
        if self._live:
            interval = self.settings.get("polling_interval", 2) * 1000
            self._timer.start(interval)
            self._live_btn.setText("Live ON")
        else:
            self._timer.stop()
            self._live_btn.setText("Live OFF")

    def _scan(self):
        self._worker = RamWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, data):
        self.total_card.set_value(f"{data['total_gb']} GB")
        self.used_card.set_value(f"{data['used_gb']} GB")
        self.free_card.set_value(f"{data['free_gb']} GB")
        self.pct_card.set_value(f"{data['pct']}%")
        self._procs = data['processes']
        self._table.clear_rows()
        for p in self._procs:
            self._table.add_row([str(p['pid']), p['name'],
                                  str(p['rss_mb']), str(p['pct']),
                                  p['status'], p['exe']])
        self.status_message.emit(f"RAM: {data['used_gb']}/{data['total_gb']} GB  ({data['pct']}%)")

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._procs): return
        proc = self._procs[row]
        menu = QMenu(self)
        menu.addAction("Kill Process", lambda: self._kill(proc, row))
        menu.addAction("Open File Location", lambda: self.open_location(proc['exe']))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _kill(self, proc, row):
        if not self.confirm(f"kill '{proc['name']}' (PID {proc['pid']})"):
            return
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

        self._root.addWidget(SectionHeader(self.tr("cpu"), "CPU usage per process"))
        self._root.addWidget(Divider())

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.cpu_card   = StatCard("CPU Usage", "—%", "#e05c2a")
        self.cores_card = StatCard("Cores/Threads","—")
        self.freq_card  = StatCard("Frequency","—")
        self.procs_card = StatCard("Processes","—")
        for c in [self.cpu_card, self.cores_card, self.freq_card, self.procs_card]:
            stats.addWidget(c)
        self._root.addLayout(stats)

        bar = ActionBar()
        bar.add_button("Scan / Refresh", "accentBtn", self._scan)
        self._live_btn = bar.add_button("Live OFF", "flatBtn", self._toggle_live)
        bar.add_stretch()
        self._search = SearchBar("Filter processes...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["PID","Process","CPU %","Status","User","Path"])
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)
        self._scan()

    def _toggle_live(self):
        self._live = not self._live
        if self._live:
            self._timer.start(self.settings.get("polling_interval",2)*1000)
            self._live_btn.setText("Live ON")
        else:
            self._timer.stop()
            self._live_btn.setText("Live OFF")

    def _scan(self):
        self._worker = CpuWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, data):
        self.cpu_card.set_value(f"{data['total_pct']}%")
        self.cores_card.set_value(f"{data['cores']}C / {data['threads']}T")
        self.freq_card.set_value(f"{data['freq_mhz']} MHz")
        self.procs_card.set_value(str(len(data['processes'])))
        self._procs = data['processes']
        self._table.clear_rows()
        for p in self._procs:
            r = self._table.add_row([str(p['pid']), p['name'], str(p['cpu_pct']),
                                      p['status'], p['user'], p['exe']])
            if p['cpu_pct'] > 20:
                for c in range(self._table.columnCount()):
                    item = self._table.item(r, c)
                    if item: item.setForeground(QColor("#e05c2a"))

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._procs): return
        proc = self._procs[row]
        menu = QMenu(self)
        menu.addAction("Kill Process", lambda: self._kill(proc, row))
        menu.addAction("Open File Location", lambda: self.open_location(proc['exe']))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _kill(self, proc, row):
        if not self.confirm(f"kill '{proc['name']}' (PID {proc['pid']})"):
            return
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
        self._root.addWidget(SectionHeader(self.tr("services"), "Windows services — view, start, stop, disable"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
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
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
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
        self._render(svcs)
        self.status_message.emit(f"Found {len(svcs)} services")

    def _render(self, svcs):
        self._table.clear_rows()
        for s in svcs:
            r = self._table.add_row([s['name'], s['display'], s['status'],
                                      s['start_type'], str(s['pid']), s['exe']])
            color = "#2ecc71" if s['status']=="running" else "#e74c3c" if s['status']=="stopped" else "#888888"
            item = QTableWidgetItem(s['status'])
            item.setForeground(QColor(color))
            self._table.setItem(r, 2, item)

    def _apply_filter(self, f):
        f = f.lower()
        for row in range(self._table.rowCount()):
            show = True
            if f == "running":
                show = (self._table.item(row,2) or QTableWidgetItem()).text().lower() == "running"
            elif f == "stopped":
                show = (self._table.item(row,2) or QTableWidgetItem()).text().lower() == "stopped"
            elif f == "disabled":
                show = "disabled" in (self._table.item(row,3) or QTableWidgetItem()).text().lower()
            elif f == "auto start":
                show = "auto" in (self._table.item(row,3) or QTableWidgetItem()).text().lower()
            elif f == "manual":
                show = "manual" in (self._table.item(row,3) or QTableWidgetItem()).text().lower()
            self._table.setRowHidden(row, not show)

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._svcs): return
        svc = self._svcs[row]
        menu = QMenu(self)
        menu.addAction("Stop Service",    lambda: self._svc_action(svc, "stop"))
        menu.addAction("Start Service",   lambda: self._svc_action(svc, "start"))
        menu.addAction("Disable Service", lambda: self._svc_action(svc, "disable"))
        menu.addAction("Enable (Manual)", lambda: self._svc_action(svc, "enable"))
        menu.addAction("Open File Location", lambda: self.open_location(svc['exe']))
        menu.addAction("Export PS1",      lambda: self._export(svc))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _svc_action(self, svc, action):
        if not self.confirm(f"{action} service '{svc['display']}'"):
            return
        cmds = {
            "stop":    f"Stop-Service -Name '{svc['name']}' -Force",
            "start":   f"Start-Service -Name '{svc['name']}'",
            "disable": f"Set-Service -Name '{svc['name']}' -StartupType Disabled",
            "enable":  f"Set-Service -Name '{svc['name']}' -StartupType Manual",
        }
        self._ps(cmds[action])
        self.status_message.emit(f"{action.title()}ed: {svc['name']}")
        self._scan()

    def _export(self, svc):
        content = (f"# Service: {svc['display']}\n"
                   f"Stop-Service -Name '{svc['name']}' -Force\n"
                   f"Set-Service -Name '{svc['name']}' -StartupType Disabled\n")
        self.export_report("service_disable", content)

# ── Uninstall Manager ─────────────────────────────────────────────────────────
class UninstallPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._apps = []
        self._root.addWidget(SectionHeader(self.tr("uninstall"), "All installed applications"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
        bar.add_stretch()
        self._search = SearchBar("Search applications...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Name","Publisher","Version","Size (MB)","Install Date"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
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
            self._table.add_row([a['name'], a['publisher'], a['version'],
                                  str(a['size_mb']), a['install_date']])
        self.status_message.emit(f"Found {len(apps)} installed apps")

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._apps): return
        app = self._apps[row]
        menu = QMenu(self)
        menu.addAction("Uninstall", lambda: self._uninstall(app))
        menu.addAction("Open Install Location", lambda: self.open_location(app['location']))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _uninstall(self, app):
        if not self.confirm(f"uninstall '{app['name']}'"):
            return
        if app['uninstall']:
            try:
                subprocess.Popen(app['uninstall'], shell=True)
                self.status_message.emit(f"Uninstall launched for: {app['name']}")
            except Exception as e:
                self.status_message.emit(f"Error: {e}")

# ── PC Specs ──────────────────────────────────────────────────────────────────
class SpecsPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("specs"), "Hardware and system information"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
        bar.add_button("Export Report", "flatBtn", self._export)
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
        lbl = QLabel("Scanning hardware...")
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
            t = QLabel(title)
            t.setObjectName("sectionTitle")
            card.add(t)
            card.add(Divider())
            for label, val in rows:
                card.add(InfoRow(label, val))
            self._lay.addWidget(card)

        section("Operating System", [
            ("OS", data.get("os","")),
            ("Hostname", data.get("hostname","")),
            ("Architecture", data.get("arch","")),
        ])
        section("Processor", [
            ("CPU", data.get("cpu","")),
            ("Cores / Threads", f"{data.get('cpu_cores','')} / {data.get('cpu_threads','')}"),
        ])
        section("Graphics", [("GPU", data.get("gpu",""))])
        section("Motherboard & BIOS", [
            ("Motherboard", data.get("motherboard","")),
            ("BIOS Version", data.get("bios","")),
        ])

        ram_card = Card()
        t = QLabel("Memory (RAM)")
        t.setObjectName("sectionTitle")
        ram_card.add(t)
        ram_card.add(Divider())
        ram_card.add(InfoRow("Total RAM", f"{data.get('ram_total','')} GB"))
        for i, s in enumerate(data.get("ram_sticks",[])):
            ram_card.add(InfoRow(f"Slot {i+1}",
                f"{s['capacity_gb']} GB  {s['speed_mhz']} MHz  {s['manufacturer']}"))
        self._lay.addWidget(ram_card)

        disk_card = Card()
        t2 = QLabel("Storage")
        t2.setObjectName("sectionTitle")
        disk_card.add(t2)
        disk_card.add(Divider())
        for d in data.get("disks",[]):
            disk_card.add(InfoRow(
                f"{d['device']} ({d['fstype']})",
                f"{d['used_gb']} / {d['total_gb']} GB  ({d['pct']}% used)"
            ))
            bar = ProgressRow(d['mountpoint'], int(d['pct']), 100,
                              "#e74c3c" if d['pct'] > 85 else "#e05c2a")
            disk_card.add(bar)
        self._lay.addWidget(disk_card)

        if data.get("monitors"):
            section("Monitors", [(f"Monitor {i+1}", m)
                                  for i,m in enumerate(data['monitors'])])
        self._lay.addStretch()
        self.status_message.emit("Specs loaded")

    def _export(self):
        if not self._data: return
        lines = ["AlagorCore — PC Specs Report\n" + "="*40]
        for k, v in self._data.items():
            if isinstance(v, list):
                lines.append(f"\n{k}:")
                for item in v:
                    lines.append(f"  {item}")
            else:
                lines.append(f"{k}: {v}")
        self.export_report("PC_Specs", "\n".join(lines))

# ── Disk Analyzer ─────────────────────────────────────────────────────────────
class DiskPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("disk"), "What is consuming your disk space"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        self._path_box = QLineEdit("C:\\")
        self._path_box.setFixedWidth(160)
        bar.add_widget(self._path_box)
        bar.add_button("Analyze", "accentBtn", self._scan)
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("subText")
        bar.add_widget(self._status_lbl)
        bar.add_stretch()
        self._root.addWidget(bar)

        self._table = SmartTable(["Name","Type","Size (MB)","Path"])
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)

    def _scan(self):
        self._table.clear_rows()
        path = self._path_box.text() or "C:\\"
        self._worker = DiskWorker(path)
        self._worker.progress.connect(lambda m: self._status_lbl.setText(m))
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, items):
        self._items = items
        self._table.clear_rows()
        for item in items:
            self._table.add_row([item['name'], item['type'],
                                  str(item['size_mb']), item['path']])
        self._status_lbl.setText(f"{len(items)} items found")

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or not hasattr(self,'_items') or row >= len(self._items): return
        item = self._items[row]
        menu = QMenu(self)
        menu.addAction("Open in Explorer", lambda: self.open_location(item['path']))
        menu.exec(self._table.viewport().mapToGlobal(pos))

# ── Network Monitor ───────────────────────────────────────────────────────────
class NetworkPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._conns = []
        self._root.addWidget(SectionHeader(self.tr("network"), "Active connections and bandwidth usage"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
        bar.add_stretch()
        self._search = SearchBar("Filter by process or address...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["PID","Process","Local Address","Remote Address","Status","Type","Path"])
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)
        self._scan()

    def _scan(self):
        self._worker = NetworkWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, conns):
        self._conns = conns
        self._table.clear_rows()
        for c in conns:
            self._table.add_row([str(c['pid']), c['name'], c['laddr'],
                                  c['raddr'], c['status'], c['type'], c['exe']])
        self.status_message.emit(f"{len(conns)} active connections")

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
        if not self.confirm(f"kill process {pid}"):
            return
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
        self._root.addWidget(SectionHeader(self.tr("cleaner"), "Clear temp files, cache, crash dumps"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
        self._clean_btn = bar.add_button("Clean Selected", "dangerBtn", self._clean)
        self._clean_btn.setEnabled(False)
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("subText")
        bar.add_widget(self._status_lbl)
        self._root.addWidget(bar)

        self._table = SmartTable(["Location","Files","Size (MB)","Path","Include"])
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._root.addWidget(self._table)

        self._prog = QProgressBar()
        self._prog.setVisible(False)
        self._prog.setFixedHeight(6)
        self._root.addWidget(self._prog)

    def _scan(self):
        self._table.clear_rows()
        self._status_lbl.setText("Scanning...")
        self._worker = JunkScanWorker()
        self._worker.progress.connect(lambda m: self._status_lbl.setText(m))
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, items):
        self._items = items
        self._table.clear_rows()
        total_mb = 0
        for item in items:
            r = self._table.add_row([item['label'], str(item['files']),
                                      str(item['size_mb']), item['path'], "✓"])
            chk = QCheckBox()
            chk.setChecked(item['selected'])
            self._table.setCellWidget(r, 4, chk)
            total_mb += item['size_mb']
        self._clean_btn.setEnabled(True)
        self._status_lbl.setText(f"Found {total_mb:.1f} MB of junk")

    def _clean(self):
        paths = []
        for r in range(self._table.rowCount()):
            chk = self._table.cellWidget(r, 4)
            if chk and chk.isChecked():
                if r < len(self._items):
                    paths.append(self._items[r]['path'])
        if not paths: return
        if not self.confirm(f"delete junk files from {len(paths)} locations"):
            return
        self._prog.setVisible(True)
        self._prog.setRange(0, 0)
        self._worker2 = JunkCleanWorker(paths)
        self._worker2.progress.connect(lambda m: self._status_lbl.setText(m))
        self._worker2.done.connect(self._on_clean_done)
        self._worker2.start()

    def _on_clean_done(self, deleted, freed):
        self._prog.setVisible(False)
        self._prog.setRange(0, 100)
        freed_mb = round(freed/1024**2, 1)
        self._status_lbl.setText(f"Cleaned {deleted} files, freed {freed_mb} MB")
        self._scan()

# ── Drivers ───────────────────────────────────────────────────────────────────
class DriversPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("drivers"), "Installed drivers — signed/unsigned flags"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
        self._filter = QComboBox()
        self._filter.addItems(["All","Unsigned Only","Signed Only"])
        self._filter.currentTextChanged.connect(self._apply_filter)
        bar.add_widget(self._filter)
        bar.add_stretch()
        self._search = SearchBar("Search drivers...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Device","Class","Version","Manufacturer","Date","Signed"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
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
            r = self._table.add_row([d['name'], d['class'], d['version'],
                                      d['manufacturer'], d['date'],
                                      "Yes" if d['signed'] else "NO"])
            if not d['signed']:
                item = QTableWidgetItem("NO ⚠")
                item.setForeground(QColor("#e74c3c"))
                self._table.setItem(r, 5, item)

    def _apply_filter(self, f):
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 5)
            signed = item and "Yes" in item.text()
            if f == "Unsigned Only": self._table.setRowHidden(row, signed)
            elif f == "Signed Only": self._table.setRowHidden(row, not signed)
            else: self._table.setRowHidden(row, False)

# ── Scheduled Tasks ───────────────────────────────────────────────────────────
class TasksPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._tasks = []
        self._root.addWidget(SectionHeader(self.tr("tasks"), "View and disable hidden scheduled tasks"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
        bar.add_stretch()
        self._search = SearchBar("Search tasks...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Task Name","Path","State","Author","Description"])
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)
        self._scan()

    def _scan(self):
        self._worker = TasksWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, tasks):
        self._tasks = tasks
        self._table.clear_rows()
        for t in tasks:
            r = self._table.add_row([t['name'], t['path'], t['state'],
                                      t['author'], t['description']])
            color = "#2ecc71" if t['state'] == "Ready" else "#e74c3c" if t['state'] == "Running" else "#888888"
            item = QTableWidgetItem(t['state'])
            item.setForeground(QColor(color))
            self._table.setItem(r, 2, item)
        self.status_message.emit(f"{len(tasks)} scheduled tasks")

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._tasks): return
        task = self._tasks[row]
        menu = QMenu(self)
        menu.addAction("Disable Task", lambda: self._disable(task))
        menu.addAction("Enable Task",  lambda: self._enable(task))
        menu.addAction("Delete Task",  lambda: self._delete(task))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _disable(self, t):
        if self.confirm(f"disable task '{t['name']}'"):
            self._ps(f"Disable-ScheduledTask -TaskName '{t['name']}'")
            self._scan()

    def _enable(self, t):
        self._ps(f"Enable-ScheduledTask -TaskName '{t['name']}'")
        self._scan()

    def _delete(self, t):
        if self.confirm(f"delete task '{t['name']}'"):
            self._ps(f"Unregister-ScheduledTask -TaskName '{t['name']}' -Confirm:$false")
            self._scan()

# ── Windows Features ──────────────────────────────────────────────────────────
class WinFeaturesPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._features = []
        self._root.addWidget(SectionHeader(self.tr("winfeatures"), "Enable or disable optional Windows components"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
        self._filter = QComboBox()
        self._filter.addItems(["All","Enabled","Disabled"])
        self._filter.currentTextChanged.connect(self._apply_filter)
        bar.add_widget(self._filter)
        bar.add_stretch()
        self._search = SearchBar("Search features...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Feature Name","State","Description"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)

    def _scan(self):
        self._worker = WinFeaturesWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()
        self.status_message.emit("Scanning Windows features...")

    def _on_result(self, features):
        self._features = features
        self._render(features)
        enabled = sum(1 for f in features if f['enabled'])
        self.status_message.emit(f"{len(features)} features — {enabled} enabled")

    def _render(self, features):
        self._table.clear_rows()
        for f in features:
            r = self._table.add_row([f['name'], f['state'], f['description']])
            color = "#2ecc71" if f['enabled'] else "#888888"
            item = QTableWidgetItem(f['state'])
            item.setForeground(QColor(color))
            self._table.setItem(r, 1, item)

    def _apply_filter(self, f):
        for row in range(self._table.rowCount()):
            state = (self._table.item(row,1) or QTableWidgetItem()).text()
            if f == "Enabled":  self._table.setRowHidden(row, state != "Enabled")
            elif f == "Disabled": self._table.setRowHidden(row, state == "Enabled")
            else: self._table.setRowHidden(row, False)

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._features): return
        feat = self._features[row]
        menu = QMenu(self)
        if feat['enabled']:
            menu.addAction("Disable Feature", lambda: self._toggle(feat, False))
        else:
            menu.addAction("Enable Feature", lambda: self._toggle(feat, True))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _toggle(self, feat, enable):
        action = "enable" if enable else "disable"
        if not self.confirm(f"{action} feature '{feat['name']}'"):
            return
        cmd = ("Enable-WindowsOptionalFeature" if enable else "Disable-WindowsOptionalFeature")
        self._ps(f"{cmd} -Online -FeatureName '{feat['name']}' -NoRestart")
        self.status_message.emit(f"Requires restart to take effect.")
        self._scan()

# ── Battery ───────────────────────────────────────────────────────────────────
class BatteryPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("battery"), "Battery health, capacity and wear level"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
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

        self._card.add(InfoRow("Charge Level",   f"{data['percent']}%"))
        self._card.add(InfoRow("Power Source",   "Plugged In" if data['plugged'] else "Battery"))
        if data['secs_left'] and data['secs_left'] > 0 and not data['plugged']:
            mins = data['secs_left'] // 60
            self._card.add(InfoRow("Time Remaining", f"{mins//60}h {mins%60}m"))
        if data.get('design_cap'):
            self._card.add(InfoRow("Design Capacity", f"{data['design_cap']} mWh"))
            self._card.add(InfoRow("Full Charge Cap",  f"{data['full_cap']} mWh"))
        if data.get('health_pct') is not None:
            health = data['health_pct']
            color = "#2ecc71" if health > 80 else "#f39c12" if health > 60 else "#e74c3c"
            row = ProgressRow("Battery Health", int(health), 100, color)
            self._card.add(row)
            self._card.add(InfoRow("Health",
                f"{health}%  ({'Good' if health>80 else 'Fair' if health>60 else 'Poor'})"))

# ── Windows Updates ───────────────────────────────────────────────────────────
class UpdatesPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("updates"), "Installed Windows updates — history"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Load History", "accentBtn", self._scan)
        bar.add_button("Open Windows Update", "flatBtn",
                       lambda: subprocess.Popen("start ms-settings:windowsupdate", shell=True))
        bar.add_button("Pause Updates (7 days)", "flatBtn", self._pause)
        self._root.addWidget(bar)

        self._table = SmartTable(["KB ID","Description","Installed On","Installed By"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._root.addWidget(self._table)

    def _scan(self):
        self._worker = UpdatesWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()
        self.status_message.emit("Loading update history...")

    def _on_result(self, updates):
        self._table.clear_rows()
        for u in updates:
            self._table.add_row([u['id'], u['description'],
                                  u['installed_on'], u['installed_by']])
        self.status_message.emit(f"{len(updates)} updates installed")

    def _pause(self):
        self._ps(
            'Set-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\WindowsUpdate\\UX\\Settings" '
            '-Name "PauseUpdatesExpiryTime" -Value ((Get-Date).AddDays(7).ToString("yyyy-MM-ddTHH:mm:ssZ"))'
        )
        self.status_message.emit("Updates paused for 7 days")

# ── Registry Cleaner ──────────────────────────────────────────────────────────
class RegistryPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._issues = []
        self._root.addWidget(SectionHeader(self.tr("registry"), "Find and fix orphaned registry entries"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan Registry", "accentBtn", self._scan)
        self._fix_btn = bar.add_button("Fix Selected", "dangerBtn", self._fix_selected)
        self._fix_btn.setEnabled(False)
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("subText")
        bar.add_widget(self._status_lbl)
        self._root.addWidget(bar)

        self._prog = QProgressBar()
        self._prog.setVisible(False)
        self._prog.setFixedHeight(6)
        self._root.addWidget(self._prog)

        self._table = SmartTable(["Type","Registry Key","Description","Fix"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._root.addWidget(self._table)

    def _scan(self):
        self._table.clear_rows()
        self._prog.setVisible(True)
        self._prog.setRange(0, 0)
        self._worker = RegistryWorker()
        self._worker.progress.connect(lambda m: self._status_lbl.setText(m))
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, issues):
        self._issues = issues
        self._prog.setVisible(False)
        self._table.clear_rows()
        for issue in issues:
            r = self._table.add_row([issue['type'], issue['key'],
                                      issue['desc'], "✓ Remove"])
            chk = QCheckBox()
            chk.setChecked(True)
            self._table.setCellWidget(r, 3, chk)
        self._fix_btn.setEnabled(bool(issues))
        self._status_lbl.setText(f"Found {len(issues)} issues")

    def _fix_selected(self):
        if not self.confirm(f"fix {len(self._issues)} registry issues"):
            return
        import winreg
        fixed = 0
        for i, issue in enumerate(self._issues):
            chk = self._table.cellWidget(i, 3)
            if not (chk and chk.isChecked()): continue
            try:
                if issue['hive'] and issue['path'] and issue['subkey']:
                    key = winreg.OpenKey(issue['hive'], issue['path'], 0, winreg.KEY_WRITE)
                    winreg.DeleteKey(key, issue['subkey'])
                    winreg.CloseKey(key)
                    fixed += 1
            except Exception:
                pass
        self._status_lbl.setText(f"Fixed {fixed} issues")
        self._scan()

# ── Hosts File ────────────────────────────────────────────────────────────────
class HostsPage(BasePage):
    HOSTS = r"C:\Windows\System32\drivers\etc\hosts"

    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("hosts"), "View and edit the Windows hosts file"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Load", "accentBtn", self._load)
        bar.add_button("Save", "flatBtn", self._save)
        bar.add_button("Add Entry", "flatBtn", self._add_entry)
        self._root.addWidget(bar)

        self._editor = QTextEdit()
        self._editor.setFont(QFont("Consolas", 11))
        self._root.addWidget(self._editor)
        self._load()

    def _load(self):
        try:
            with open(self.HOSTS, "r") as f:
                self._editor.setPlainText(f.read())
        except Exception as e:
            self._editor.setPlainText(f"# Error reading hosts file: {e}\n# Run as Administrator")

    def _save(self):
        if not self.confirm("overwrite the hosts file"):
            return
        try:
            with open(self.HOSTS, "w") as f:
                f.write(self._editor.toPlainText())
            self.status_message.emit("Hosts file saved")
        except PermissionError:
            self.status_message.emit("Error: Run as Administrator to edit hosts file")
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

    def _add_entry(self):
        self._editor.append("\n127.0.0.1    example.com  # add your entry here")

# ── Environment Variables ─────────────────────────────────────────────────────
class EnvVarsPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._root.addWidget(SectionHeader(self.tr("envvars"), "System and user environment variables"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Load", "accentBtn", self._load)
        bar.add_button("Open System Settings", "flatBtn",
                       lambda: subprocess.Popen("rundll32 sysdm.cpl,EditEnvironmentVariables", shell=True))
        bar.add_stretch()
        self._search = SearchBar("Search variables...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        tabs = QTabWidget()
        self._sys_table  = SmartTable(["Variable","Value"])
        self._sys_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._user_table = SmartTable(["Variable","Value"])
        self._user_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tabs.addTab(self._sys_table,  "System")
        tabs.addTab(self._user_table, "User")
        self._root.addWidget(tabs)
        self._table = self._sys_table
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
                key = winreg.OpenKey(hive, path)
                for i in range(winreg.QueryInfoKey(key)[1]):
                    try:
                        name, val, _ = winreg.EnumValue(key, i)
                        table.add_row([name, str(val)])
                    except: pass
                winreg.CloseKey(key)
            except: pass

# ── Font Manager ──────────────────────────────────────────────────────────────
class FontsPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._fonts = []
        self._root.addWidget(SectionHeader(self.tr("fonts"), "Installed fonts — view and remove"))
        self._root.addWidget(Divider())

        bar = ActionBar()
        bar.add_button("Scan", "accentBtn", self._scan)
        bar.add_button("Open Fonts Folder", "flatBtn",
                       lambda: subprocess.Popen("explorer C:\\Windows\\Fonts", shell=True))
        bar.add_stretch()
        self._search = SearchBar("Search fonts...")
        self._search.textChanged.connect(lambda t: self._table.filter_rows(t))
        bar.add_widget(self._search)
        self._root.addWidget(bar)

        self._table = SmartTable(["Font Name","File","Size (KB)","Path"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._root.addWidget(self._table)

    def _scan(self):
        self._worker = FontsWorker()
        self._worker.result.connect(self._on_result)
        self._worker.start()

    def _on_result(self, fonts):
        self._fonts = fonts
        self._table.clear_rows()
        for f in fonts:
            self._table.add_row([f['name'], f['file'], str(f['size_kb']), f['path']])
        self.status_message.emit(f"{len(fonts)} fonts installed")

    def _ctx_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._fonts): return
        font = self._fonts[row]
        menu = QMenu(self)
        menu.addAction("Open File Location", lambda: self.open_location(font['path']))
        menu.addAction("Uninstall Font", lambda: self._uninstall(font, row))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _uninstall(self, font, row):
        if not self.confirm(f"uninstall font '{font['name']}'"):
            return
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts", 0, winreg.KEY_WRITE)
            winreg.DeleteValue(key, font['name'])
            winreg.CloseKey(key)
            try: os.remove(font['path'])
            except: pass
            self._fonts.pop(row)
            self._table.removeRow(row)
            self.status_message.emit(f"Removed font: {font['name']}")
        except Exception as e:
            self.status_message.emit(f"Error: {e}")

# ── Windows Tweaks ────────────────────────────────────────────────────────────
TWEAKS = {
    "Privacy & Telemetry": [
        ("Disable Telemetry",        "Stops Windows sending usage data to Microsoft",
         "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", "0"),
        ("Disable Activity History",  "Prevents Windows tracking app/web activity",
         "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\System", "EnableActivityFeed", "0"),
        ("Disable Advertising ID",    "Stops apps using your advertising ID",
         "HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", "0"),
        ("Disable Location Tracking", "Disables Windows location services",
         "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location", "Value", "Deny"),
        ("Disable Cortana",           "Prevents Cortana from running",
         "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", "AllowCortana", "0"),
        ("Disable App Diagnostics",   "Stops apps from accessing diagnostic info",
         "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\appDiagnostics", "Value", "Deny"),
    ],
    "Hidden UI Tweaks": [
        ("Classic Right-Click Menu",  "Restores the classic Windows 10 context menu in Windows 11",
         "HKCU", r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32", "(Default)", ""),
        ("Show File Extensions",      "Always show file extensions in Explorer",
         "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "HideFileExt", "0"),
        ("Show Hidden Files",         "Show hidden files and folders in Explorer",
         "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Hidden", "1"),
        ("Disable Snap Suggestions",  "Removes snap layout suggestions popup",
         "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "SnapAssist", "0"),
        ("Verbose Boot Messages",     "Shows detailed messages during boot",
         "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "VerboseStatus", "1"),
        ("Disable Sticky Keys Prompt","Stops the Sticky Keys popup on 5× Shift",
         "HKCU", r"Control Panel\Accessibility\StickyKeys", "Flags", "506"),
    ],
    "Performance": [
        ("Disable Animations",        "Turns off window animations for faster UI",
         "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", "2"),
        ("Disable Transparency",      "Removes Aero transparency effects",
         "HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", "0"),
        ("Disable Search Indexing",   "Stops Windows Search from indexing files",
         "HKLM", r"SYSTEM\CurrentControlSet\Services\WSearch", "Start", "4"),
        ("High Performance Power",    "Switches to high performance power plan",
         "HKLM", r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes", "ActivePowerScheme",
         "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"),
        ("Disable Superfetch/SysMain","Disables SysMain (Superfetch) service",
         "HKLM", r"SYSTEM\CurrentControlSet\Services\SysMain", "Start", "4"),
        ("Disable Windows Tips",      "Stops Windows from showing tips and suggestions",
         "HKCU", r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager", "SoftLandingEnabled", "0"),
    ],
    "Security": [
        ("Disable SmartScreen",       "Turns off Windows SmartScreen filter",
         "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer", "SmartScreenEnabled", "Off"),
        ("Disable Windows Defender Realtime", "Disables real-time Defender protection (use with caution)",
         "HKLM", r"SOFTWARE\Policies\Microsoft\Windows Defender\Real-Time Protection", "DisableRealtimeMonitoring", "1"),
        ("Disable UAC Prompts",       "Disables User Account Control prompts (not recommended)",
         "HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", "EnableLUA", "0"),
        ("Disable Remote Assistance", "Prevents remote assistance connections",
         "HKLM", r"SYSTEM\CurrentControlSet\Control\Remote Assistance", "fAllowToGetHelp", "0"),
    ],
    "Network Tweaks": [
        ("Disable IPv6",              "Disables IPv6 on all network adapters",
         "HKLM", r"SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters", "DisabledComponents", "255"),
        ("Disable NetBIOS",           "Disables NetBIOS over TCP/IP",
         "HKLM", r"SYSTEM\CurrentControlSet\Services\NetBT\Parameters", "TransportBindName", ""),
        ("Disable LLMNR",             "Disables Link-Local Multicast Name Resolution",
         "HKLM", r"SOFTWARE\Policies\Microsoft\Windows NT\DNSClient", "EnableMulticast", "0"),
        ("Limit Bandwidth Reserve",   "Removes the 20% QoS bandwidth reservation",
         "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\Psched", "NonBestEffortLimit", "0"),
        ("Disable Wi-Fi Sense",       "Disables automatic Wi-Fi hotspot sharing",
         "HKLM", r"SOFTWARE\Microsoft\WcmSvc\wifinetworkmanager\config", "AutoConnectAllowedOEM", "0"),
    ],
    "God Mode & Panels": [],
}

class TweaksPage(BasePage):
    def __init__(self, settings, parent=None):
        super().__init__(settings, parent)
        self._tweak_rows = []
        self._root.addWidget(SectionHeader(self.tr("tweaks"), "Hidden Windows settings, privacy and performance tweaks"))
        self._root.addWidget(Divider())

        preset_bar = ActionBar()
        preset_bar.add_button("Gaming Mode",  "flatBtn", lambda: self._apply_preset("gaming"))
        preset_bar.add_button("Privacy Mode", "flatBtn", lambda: self._apply_preset("privacy"))
        preset_bar.add_button("Clean Mode",   "flatBtn", lambda: self._apply_preset("clean"))
        preset_bar.add_stretch()
        preset_bar.add_button("Apply All Enabled", "accentBtn", self._apply_all)
        preset_bar.add_button("God Mode Folder",   "flatBtn",   self._god_mode)
        self._root.addWidget(preset_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(16)
        lay.setContentsMargins(0, 4, 4, 4)

        for category, tweaks in TWEAKS.items():
            if not tweaks: continue
            cat_lbl = QLabel(category)
            cat_lbl.setObjectName("sectionTitle")
            lay.addWidget(cat_lbl)
            for title, desc, hive, path, name, value in tweaks:
                row = TweakRow(title, desc, checked=False)
                row.setProperty("hive",  hive)
                row.setProperty("rpath", path)
                row.setProperty("rname", name)
                row.setProperty("rval",  value)
                self._tweak_rows.append(row)
                lay.addWidget(row)
            lay.addWidget(Divider())

        lay.addStretch()
        scroll.setWidget(container)
        self._root.addWidget(scroll)

    def _apply_all(self):
        applied = 0
        for row in self._tweak_rows:
            if row.is_checked():
                self._apply_tweak(row)
                applied += 1
        self.status_message.emit(f"Applied {applied} tweaks. Some require a restart.")

    def _apply_tweak(self, row):
        hive  = row.property("hive")
        path  = row.property("rpath")
        name  = row.property("rname")
        value = row.property("rval")
        try:
            import winreg
            h = winreg.HKEY_LOCAL_MACHINE if hive == "HKLM" else winreg.HKEY_CURRENT_USER
            key = winreg.CreateKeyEx(h, path, 0, winreg.KEY_SET_VALUE)
            if value.isdigit():
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(value))
            else:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            winreg.CloseKey(key)
        except Exception as e:
            self.status_message.emit(f"Error applying tweak: {e}")

    def _apply_preset(self, preset):
        PRESETS = {
            "gaming":  ["Disable Animations","Disable Transparency","Disable Superfetch/SysMain",
                        "High Performance Power","Disable Windows Tips"],
            "privacy": ["Disable Telemetry","Disable Activity History","Disable Advertising ID",
                        "Disable Cortana","Disable Location Tracking","Disable App Diagnostics"],
            "clean":   ["Show File Extensions","Show Hidden Files","Disable Animations",
                        "Disable Windows Tips","Disable Sticky Keys Prompt"],
        }
        names = PRESETS.get(preset, [])
        applied = 0
        for row in self._tweak_rows:
            title = row.findChild(QLabel).text() if row.findChild(QLabel) else ""
            # match by checking title widget
            for child in row.children():
                if isinstance(child, QLabel) and child.objectName() == "sectionTitle":
                    if child.text() in names:
                        row.set_checked(True)
                        self._apply_tweak(row)
                        applied += 1
        self.status_message.emit(f"Preset '{preset}' applied {applied} tweaks")

    def _god_mode(self):
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            god_path = os.path.join(desktop, "GodMode.{ED7BA470-8E54-465E-825C-99712043E01C}")
            os.makedirs(god_path, exist_ok=True)
            subprocess.Popen(f'explorer "{god_path}"')
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
        self._root.addWidget(SectionHeader("Settings", "Configure AlagorCore"))
        self._root.addWidget(Divider())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setSpacing(12)
        lay.setContentsMargins(0,0,4,0)

        # Theme
        theme_card = Card()
        t = QLabel("Appearance")
        t.setObjectName("sectionTitle")
        theme_card.add(t)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme"))
        theme_row.addStretch()
        self._theme_toggle = ToggleSwitch(checked=settings.get("theme","dark")=="light")
        self._theme_toggle.toggled.connect(self._on_theme)
        self._theme_lbl = QLabel("Dark" if settings.get("theme","dark")=="dark" else "Light")
        self._theme_lbl.setObjectName("subText")
        theme_row.addWidget(self._theme_lbl)
        theme_row.addWidget(self._theme_toggle)
        theme_card.add_layout(theme_row)
        lay.addWidget(theme_card)

        # Language
        lang_card = Card()
        l = QLabel("Language")
        l.setObjectName("sectionTitle")
        lang_card.add(l)
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("UI Language"))
        lang_row.addStretch()
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["English", "العربية"])
        self._lang_combo.setCurrentIndex(0 if settings.get("language","en")=="en" else 1)
        self._lang_combo.currentIndexChanged.connect(self._on_lang)
        lang_row.addWidget(self._lang_combo)
        lang_card.add_layout(lang_row)
        lay.addWidget(lang_card)

        # Polling
        poll_card = Card()
        p = QLabel("Live Polling Interval")
        p.setObjectName("sectionTitle")
        poll_card.add(p)
        from PyQt6.QtWidgets import QSlider
        from PyQt6.QtCore import Qt
        poll_row = QHBoxLayout()
        poll_row.addWidget(QLabel("Refresh every"))
        self._poll_slider = QSlider(Qt.Orientation.Horizontal)
        self._poll_slider.setMinimum(1)
        self._poll_slider.setMaximum(10)
        self._poll_slider.setValue(settings.get("polling_interval",2))
        self._poll_val = QLabel(f"{settings.get('polling_interval',2)}s")
        self._poll_slider.valueChanged.connect(
            lambda v: (self._poll_val.setText(f"{v}s"),
                       settings.update({"polling_interval": v})))
        poll_row.addWidget(self._poll_slider)
        poll_row.addWidget(self._poll_val)
        poll_card.add_layout(poll_row)
        lay.addWidget(poll_card)

        # Updates
        upd_card = Card()
        u = QLabel("Updates")
        u.setObjectName("sectionTitle")
        upd_card.add(u)
        upd_row = QHBoxLayout()
        upd_row.addWidget(QLabel("Auto-check on launch"))
        upd_row.addStretch()
        self._auto_upd = ToggleSwitch(checked=settings.get("auto_update_check", True))
        self._auto_upd.toggled.connect(lambda v: settings.update({"auto_update_check": v}))
        upd_row.addWidget(self._auto_upd)
        upd_card.add_layout(upd_row)
        check_btn = QPushButton("Check for Updates Now")
        check_btn.setObjectName("flatBtn")
        check_btn.clicked.connect(self.check_update_now.emit)
        upd_card.add(check_btn)
        lay.addWidget(upd_card)

        # PayPal config
        pp_card = Card()
        pp_lbl = QLabel("Donation Link (PayPal.me)")
        pp_lbl.setObjectName("sectionTitle")
        pp_card.add(pp_lbl)
        self._pp_edit = QLineEdit(settings.get("paypal_url",""))
        self._pp_edit.setPlaceholderText("https://paypal.me/yourname")
        self._pp_edit.textChanged.connect(lambda v: settings.update({"paypal_url": v}))
        pp_card.add(self._pp_edit)
        lay.addWidget(pp_card)

        lay.addStretch()
        scroll.setWidget(container)
        self._root.addWidget(scroll)

    def _on_theme(self, light):
        mode = "light" if light else "dark"
        self._theme_lbl.setText("Light" if light else "Dark")
        self.settings["theme"] = mode
        self.theme_changed.emit(mode)

    def _on_lang(self, idx):
        lang = "en" if idx == 0 else "ar"
        self.settings["language"] = lang
        self.language_changed.emit(lang)
