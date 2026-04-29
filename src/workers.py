import os, sys, subprocess, platform
from PyQt6.QtCore import QThread, pyqtSignal

# ── helper ──────────────────────────────────────────────────────────────────
def _ps(cmd):
    """Run a PowerShell command and return stdout."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=30
        )
        return r.stdout.strip()
    except Exception:
        return ""

def _wmic(query):
    try:
        r = subprocess.run(["wmic"] + query.split(), capture_output=True, text=True, timeout=20)
        return r.stdout.strip()
    except Exception:
        return ""

# ── Startup ──────────────────────────────────────────────────────────────────
class StartupWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import winreg
            entries = []
            locations = [
                (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
            ]
            for hive, path in locations:
                try:
                    key = winreg.OpenKey(hive, path)
                    i = 0
                    while True:
                        try:
                            name, val, _ = winreg.EnumValue(key, i)
                            hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
                            entries.append({
                                "name": name, "command": val,
                                "location": f"{hive_name}\\...\\Run",
                                "hive": hive, "path": path,
                                "enabled": True,
                            })
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(key)
                except Exception:
                    pass
            # Startup folder
            for folder in [
                os.path.join(os.environ.get("APPDATA",""), r"Microsoft\Windows\Start Menu\Programs\Startup"),
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp",
            ]:
                if os.path.isdir(folder):
                    for f in os.listdir(folder):
                        fp = os.path.join(folder, f)
                        entries.append({
                            "name": f, "command": fp,
                            "location": "Startup Folder",
                            "hive": None, "path": folder,
                            "enabled": True,
                        })
            self.result.emit(entries)
        except Exception as e:
            self.error.emit(str(e))

# ── RAM ──────────────────────────────────────────────────────────────────────
class RamWorker(QThread):
    result = pyqtSignal(dict)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import psutil
            vm = psutil.virtual_memory()
            sw = psutil.swap_memory()
            procs = []
            for p in psutil.process_iter(['pid','name','memory_info','memory_percent','status','exe']):
                try:
                    mi = p.info['memory_info']
                    procs.append({
                        "pid":     p.info['pid'],
                        "name":    p.info['name'],
                        "rss_mb":  round(mi.rss / 1024**2, 1),
                        "vms_mb":  round(mi.vms / 1024**2, 1),
                        "pct":     round(p.info['memory_percent'], 2),
                        "status":  p.info['status'],
                        "exe":     p.info['exe'] or "",
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            procs.sort(key=lambda x: x['rss_mb'], reverse=True)
            self.result.emit({
                "total_gb":  round(vm.total / 1024**3, 2),
                "used_gb":   round(vm.used  / 1024**3, 2),
                "free_gb":   round(vm.available / 1024**3, 2),
                "pct":       vm.percent,
                "swap_total":round(sw.total / 1024**3, 2),
                "swap_used": round(sw.used  / 1024**3, 2),
                "processes": procs,
            })
        except Exception as e:
            self.error.emit(str(e))

# ── CPU ──────────────────────────────────────────────────────────────────────
class CpuWorker(QThread):
    result = pyqtSignal(dict)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import psutil
            cpu_pct   = psutil.cpu_percent(interval=1, percpu=False)
            per_core  = psutil.cpu_percent(interval=0, percpu=True)
            freq      = psutil.cpu_freq()
            procs = []
            for p in psutil.process_iter(['pid','name','cpu_percent','status','exe','username','create_time']):
                try:
                    procs.append({
                        "pid":     p.info['pid'],
                        "name":    p.info['name'],
                        "cpu_pct": round(p.info['cpu_percent'] or 0, 2),
                        "status":  p.info['status'],
                        "exe":     p.info['exe'] or "",
                        "user":    p.info['username'] or "",
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            procs.sort(key=lambda x: x['cpu_pct'], reverse=True)
            self.result.emit({
                "total_pct": cpu_pct,
                "per_core":  per_core,
                "freq_mhz":  round(freq.current) if freq else 0,
                "freq_max":  round(freq.max)     if freq else 0,
                "cores":     psutil.cpu_count(logical=False),
                "threads":   psutil.cpu_count(logical=True),
                "processes": procs,
            })
        except Exception as e:
            self.error.emit(str(e))

# ── Services ─────────────────────────────────────────────────────────────────
class ServicesWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import psutil
            svcs = []
            for s in psutil.win_service_iter():
                try:
                    si = s.as_dict()
                    svcs.append({
                        "name":        si.get('name',''),
                        "display":     si.get('display_name',''),
                        "status":      si.get('status',''),
                        "start_type":  si.get('start_type',''),
                        "pid":         si.get('pid') or 0,
                        "exe":         si.get('binpath',''),
                        "description": si.get('description',''),
                    })
                except Exception:
                    pass
            svcs.sort(key=lambda x: x['display'])
            self.result.emit(svcs)
        except Exception as e:
            self.error.emit(str(e))

# ── Installed Apps ────────────────────────────────────────────────────────────
class InstalledAppsWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import winreg
            apps = []
            paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            seen = set()
            for hive, path in paths:
                try:
                    key = winreg.OpenKey(hive, path)
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            sub_name = winreg.EnumKey(key, i)
                            sub_key  = winreg.OpenKey(key, sub_name)
                            def gv(n, d=""):
                                try: return winreg.QueryValueEx(sub_key, n)[0]
                                except: return d
                            name = gv("DisplayName")
                            if not name or name in seen:
                                winreg.CloseKey(sub_key); continue
                            seen.add(name)
                            apps.append({
                                "name":      name,
                                "version":   gv("DisplayVersion"),
                                "publisher": gv("Publisher"),
                                "size_mb":   round(int(gv("EstimatedSize", 0)) / 1024, 1),
                                "install_date": gv("InstallDate"),
                                "uninstall": gv("UninstallString"),
                                "location":  gv("InstallLocation"),
                            })
                            winreg.CloseKey(sub_key)
                        except Exception:
                            pass
                    winreg.CloseKey(key)
                except Exception:
                    pass
            apps.sort(key=lambda x: x['name'].lower())
            self.result.emit(apps)
        except Exception as e:
            self.error.emit(str(e))

# ── PC Specs ──────────────────────────────────────────────────────────────────
class SpecsWorker(QThread):
    result = pyqtSignal(dict)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import psutil, platform
            uname = platform.uname()

            def wmic_val(obj, field):
                out = _wmic(f"path {obj} get {field} /value")
                for line in out.splitlines():
                    if "=" in line:
                        return line.split("=",1)[1].strip()
                return "N/A"

            cpu_name  = wmic_val("Win32_Processor", "Name")
            gpu_name  = wmic_val("Win32_VideoController", "Name")
            board     = wmic_val("Win32_BaseBoard", "Product")
            board_mfr = wmic_val("Win32_BaseBoard", "Manufacturer")
            bios_ver  = wmic_val("Win32_BIOS", "SMBIOSBIOSVersion")
            monitors  = []
            try:
                mon_out = subprocess.run(
                    ["powershell","-NoProfile","-Command",
                     "Get-WmiObject -Namespace root/wmi -Class WmiMonitorID | ForEach-Object { [System.Text.Encoding]::ASCII.GetString($_.UserFriendlyName).Trim([char]0) }"],
                    capture_output=True, text=True, timeout=10
                ).stdout.strip()
                monitors = [m for m in mon_out.splitlines() if m.strip()]
            except Exception:
                pass

            vm   = psutil.virtual_memory()
            disk = []
            for p in psutil.disk_partitions():
                try:
                    u = psutil.disk_usage(p.mountpoint)
                    disk.append({
                        "device": p.device, "mountpoint": p.mountpoint,
                        "fstype": p.fstype,
                        "total_gb": round(u.total/1024**3, 1),
                        "used_gb":  round(u.used /1024**3, 1),
                        "free_gb":  round(u.free /1024**3, 1),
                        "pct":      u.percent,
                    })
                except Exception:
                    pass

            # RAM sticks
            ram_sticks = []
            try:
                ram_out = subprocess.run(
                    ["powershell","-NoProfile","-Command",
                     "Get-WmiObject Win32_PhysicalMemory | Select-Object Capacity,Speed,Manufacturer,MemoryType | ConvertTo-Json"],
                    capture_output=True, text=True, timeout=10
                ).stdout.strip()
                import json
                sticks = json.loads(ram_out) if ram_out else []
                if isinstance(sticks, dict): sticks = [sticks]
                for s in sticks:
                    cap = int(s.get("Capacity",0))
                    ram_sticks.append({
                        "capacity_gb": round(cap/1024**3,1),
                        "speed_mhz":   s.get("Speed","N/A"),
                        "manufacturer":s.get("Manufacturer","N/A"),
                    })
            except Exception:
                pass

            self.result.emit({
                "os":        f"{uname.system} {uname.release} {uname.version}",
                "hostname":  uname.node,
                "cpu":       cpu_name,
                "cpu_cores": psutil.cpu_count(logical=False),
                "cpu_threads": psutil.cpu_count(logical=True),
                "gpu":       gpu_name,
                "ram_total": round(vm.total/1024**3, 2),
                "ram_sticks": ram_sticks,
                "motherboard": f"{board_mfr} {board}",
                "bios":      bios_ver,
                "disks":     disk,
                "monitors":  monitors,
                "arch":      uname.machine,
                "processor": uname.processor,
            })
        except Exception as e:
            self.error.emit(str(e))

# ── Disk Analyzer ─────────────────────────────────────────────────────────────
class DiskWorker(QThread):
    result   = pyqtSignal(list)
    progress = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, path="C:\\"):
        super().__init__()
        self.path = path

    def run(self):
        try:
            import psutil
            folders = []
            try:
                for entry in os.scandir(self.path):
                    self.progress.emit(f"Scanning {entry.name}...")
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            size = self._dir_size(entry.path)
                            folders.append({"name": entry.name, "path": entry.path,
                                            "size_mb": round(size/1024**2, 1), "type": "folder"})
                        else:
                            size = entry.stat(follow_symlinks=False).st_size
                            folders.append({"name": entry.name, "path": entry.path,
                                            "size_mb": round(size/1024**2, 1), "type": "file"})
                    except Exception:
                        pass
            except Exception:
                pass
            folders.sort(key=lambda x: x['size_mb'], reverse=True)
            self.result.emit(folders[:100])
        except Exception as e:
            self.error.emit(str(e))

    def _dir_size(self, path, depth=2, cur=0):
        if cur > depth: return 0
        total = 0
        try:
            for e in os.scandir(path):
                try:
                    if e.is_file(follow_symlinks=False):
                        total += e.stat(follow_symlinks=False).st_size
                    elif e.is_dir(follow_symlinks=False):
                        total += self._dir_size(e.path, depth, cur+1)
                except Exception:
                    pass
        except Exception:
            pass
        return total

# ── Network ───────────────────────────────────────────────────────────────────
class NetworkWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import psutil
            conns = []
            for c in psutil.net_connections(kind='inet'):
                try:
                    proc_name = ""
                    proc_exe  = ""
                    if c.pid:
                        try:
                            p = psutil.Process(c.pid)
                            proc_name = p.name()
                            proc_exe  = p.exe()
                        except Exception:
                            pass
                    laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ""
                    raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ""
                    conns.append({
                        "pid":   c.pid or 0,
                        "name":  proc_name,
                        "exe":   proc_exe,
                        "laddr": laddr,
                        "raddr": raddr,
                        "status":c.status,
                        "type":  "TCP" if c.type.name == "SOCK_STREAM" else "UDP",
                    })
                except Exception:
                    pass
            conns.sort(key=lambda x: x['name'])
            self.result.emit(conns)
        except Exception as e:
            self.error.emit(str(e))

# ── Junk Cleaner ──────────────────────────────────────────────────────────────
class JunkScanWorker(QThread):
    result   = pyqtSignal(list)
    progress = pyqtSignal(str)
    error    = pyqtSignal(str)

    LOCATIONS = [
        ("%TEMP%",           "User Temp Files"),
        ("%WINDIR%\\Temp",   "Windows Temp"),
        ("%WINDIR%\\Prefetch","Prefetch Files"),
        ("%LOCALAPPDATA%\\Microsoft\\Windows\\Explorer", "Explorer Thumbnails"),
        ("%LOCALAPPDATA%\\Temp", "Local App Temp"),
        ("%WINDIR%\\SoftwareDistribution\\Download", "Windows Update Cache"),
        ("%LOCALAPPDATA%\\Microsoft\\Windows\\INetCache", "IE/Edge Cache"),
        ("%LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default\\Cache", "Chrome Cache"),
    ]

    def run(self):
        results = []
        for raw_path, label in self.LOCATIONS:
            path = os.path.expandvars(raw_path)
            self.progress.emit(f"Scanning {label}...")
            if os.path.isdir(path):
                size = self._dir_size(path)
                count = self._file_count(path)
                results.append({
                    "label": label, "path": path,
                    "size_mb": round(size/1024**2, 1),
                    "files": count, "selected": True,
                })
        self.result.emit(results)

    def _dir_size(self, path):
        total = 0
        try:
            for dirpath, _, files in os.walk(path):
                for f in files:
                    try: total += os.path.getsize(os.path.join(dirpath, f))
                    except: pass
        except: pass
        return total

    def _file_count(self, path):
        count = 0
        try:
            for _, _, files in os.walk(path):
                count += len(files)
        except: pass
        return count

class JunkCleanWorker(QThread):
    progress = pyqtSignal(str)
    done     = pyqtSignal(int, int)
    error    = pyqtSignal(str)

    def __init__(self, paths):
        super().__init__()
        self.paths = paths

    def run(self):
        import shutil
        deleted = 0
        freed   = 0
        for path in self.paths:
            self.progress.emit(f"Cleaning {path}...")
            try:
                for item in os.scandir(path):
                    try:
                        size = os.path.getsize(item.path) if item.is_file() else 0
                        if item.is_dir():
                            shutil.rmtree(item.path, ignore_errors=True)
                        else:
                            os.remove(item.path)
                        freed += size
                        deleted += 1
                    except Exception:
                        pass
            except Exception:
                pass
        self.done.emit(deleted, freed)

# ── Drivers ───────────────────────────────────────────────────────────────────
class DriversWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            out = _ps(
                "Get-WmiObject Win32_PnPSignedDriver | "
                "Select-Object DeviceName,DriverVersion,Manufacturer,DriverDate,IsSigned,DeviceClass | "
                "ConvertTo-Json -Compress"
            )
            import json
            drivers = []
            if out:
                data = json.loads(out)
                if isinstance(data, dict): data = [data]
                for d in data:
                    if not d.get("DeviceName"): continue
                    drivers.append({
                        "name":       d.get("DeviceName",""),
                        "version":    d.get("DriverVersion",""),
                        "manufacturer": d.get("Manufacturer",""),
                        "date":       str(d.get("DriverDate",""))[:10],
                        "signed":     d.get("IsSigned", False),
                        "class":      d.get("DeviceClass",""),
                    })
            drivers.sort(key=lambda x: x['name'])
            self.result.emit(drivers)
        except Exception as e:
            self.error.emit(str(e))

# ── Scheduled Tasks ───────────────────────────────────────────────────────────
class TasksWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            out = _ps(
                "Get-ScheduledTask | Select-Object TaskName,TaskPath,State,Description,"
                "@{N='Author';E={$_.Principal.UserId}} | ConvertTo-Json -Compress"
            )
            import json
            tasks = []
            if out:
                data = json.loads(out)
                if isinstance(data, dict): data = [data]
                for t in data:
                    tasks.append({
                        "name":        t.get("TaskName",""),
                        "path":        t.get("TaskPath",""),
                        "state":       t.get("State",""),
                        "description": t.get("Description",""),
                        "author":      t.get("Author",""),
                    })
            tasks.sort(key=lambda x: x['name'].lower())
            self.result.emit(tasks)
        except Exception as e:
            self.error.emit(str(e))

# ── Windows Features ──────────────────────────────────────────────────────────
class WinFeaturesWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            out = _ps(
                "Get-WindowsOptionalFeature -Online | "
                "Select-Object FeatureName,State,Description | ConvertTo-Json -Compress"
            )
            import json
            features = []
            if out:
                data = json.loads(out)
                if isinstance(data, dict): data = [data]
                for f in data:
                    features.append({
                        "name":        f.get("FeatureName",""),
                        "state":       f.get("State",""),
                        "description": f.get("Description",""),
                        "enabled":     f.get("State","") == "Enabled",
                    })
            features.sort(key=lambda x: x['name'])
            self.result.emit(features)
        except Exception as e:
            self.error.emit(str(e))

# ── Battery ───────────────────────────────────────────────────────────────────
class BatteryWorker(QThread):
    result = pyqtSignal(dict)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import psutil
            bat = psutil.sensors_battery()
            if bat is None:
                self.result.emit({"present": False})
                return
            # Try to get design capacity via powercfg
            design_cap  = 0
            full_cap    = 0
            try:
                report_path = os.path.join(os.environ.get("TEMP",""), "battery_report.xml")
                subprocess.run(["powercfg","/batteryreport","/xml",f"/output",report_path],
                               capture_output=True, timeout=15)
                if os.path.exists(report_path):
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(report_path)
                    root = tree.getroot()
                    ns = {'b': 'http://schemas.microsoft.com/battery/2012'}
                    for cap in root.findall('.//b:DesignCapacity', ns):
                        design_cap = int(cap.text or 0)
                    for cap in root.findall('.//b:FullChargeCapacity', ns):
                        full_cap = int(cap.text or 0)
                    os.remove(report_path)
            except Exception:
                pass
            health_pct = round(full_cap / design_cap * 100, 1) if design_cap > 0 else None
            self.result.emit({
                "present":      True,
                "percent":      bat.percent,
                "plugged":      bat.power_plugged,
                "secs_left":    bat.secsleft,
                "design_cap":   design_cap,
                "full_cap":     full_cap,
                "health_pct":   health_pct,
            })
        except Exception as e:
            self.error.emit(str(e))

# ── Windows Updates ───────────────────────────────────────────────────────────
class UpdatesWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            out = _ps(
                "Get-HotFix | Select-Object HotFixID,Description,InstalledOn,InstalledBy | "
                "Sort-Object InstalledOn -Descending | ConvertTo-Json -Compress"
            )
            import json
            updates = []
            if out:
                data = json.loads(out)
                if isinstance(data, dict): data = [data]
                for u in data:
                    updates.append({
                        "id":          u.get("HotFixID",""),
                        "description": u.get("Description",""),
                        "installed_on":str(u.get("InstalledOn",""))[:10],
                        "installed_by":u.get("InstalledBy",""),
                    })
            self.result.emit(updates)
        except Exception as e:
            self.error.emit(str(e))

# ── Registry Cleaner ──────────────────────────────────────────────────────────
class RegistryWorker(QThread):
    result   = pyqtSignal(list)
    progress = pyqtSignal(str)
    error    = pyqtSignal(str)

    def run(self):
        issues = []
        try:
            import winreg
            self.progress.emit("Scanning uninstall entries...")
            issues += self._scan_uninstall(winreg)
            self.progress.emit("Scanning file associations...")
            issues += self._scan_file_assoc(winreg)
            self.progress.emit("Scanning MUI cache...")
            issues += self._scan_mui(winreg)
            self.result.emit(issues)
        except Exception as e:
            self.error.emit(str(e))

    def _scan_uninstall(self, winreg):
        issues = []
        path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    sname = winreg.EnumKey(key, i)
                    skey  = winreg.OpenKey(key, sname)
                    try:
                        loc = winreg.QueryValueEx(skey, "InstallLocation")[0]
                        if loc and not os.path.exists(loc):
                            name = ""
                            try: name = winreg.QueryValueEx(skey, "DisplayName")[0]
                            except: pass
                            issues.append({
                                "type": "Orphaned Uninstall",
                                "key":  f"HKLM\\...\\Uninstall\\{sname}",
                                "desc": f"{name} — path not found: {loc}",
                                "hive": winreg.HKEY_LOCAL_MACHINE,
                                "path": path, "subkey": sname,
                            })
                    except: pass
                    winreg.CloseKey(skey)
                except: pass
            winreg.CloseKey(key)
        except: pass
        return issues

    def _scan_file_assoc(self, winreg):
        issues = []
        try:
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "")
            for i in range(min(winreg.QueryInfoKey(key)[0], 500)):
                try:
                    ext = winreg.EnumKey(key, i)
                    if not ext.startswith("."): continue
                    ekey = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ext)
                    try:
                        prog_id = winreg.QueryValue(ekey, "")
                        if prog_id:
                            try:
                                winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id)
                            except:
                                issues.append({
                                    "type": "Broken File Association",
                                    "key":  f"HKCR\\{ext}",
                                    "desc": f"{ext} points to missing ProgID: {prog_id}",
                                    "hive": None, "path": "", "subkey": ext,
                                })
                    except: pass
                    winreg.CloseKey(ekey)
                except: pass
            winreg.CloseKey(key)
        except: pass
        return issues[:50]

    def _scan_mui(self, winreg):
        issues = []
        path = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
            for i in range(min(winreg.QueryInfoKey(key)[1], 200)):
                try:
                    name, _, _ = winreg.EnumValue(key, i)
                    exe = name.split(".FriendlyAppName")[0].split(".ApplicationCompany")[0]
                    if exe and not os.path.exists(exe) and exe.endswith(".exe"):
                        issues.append({
                            "type": "MUI Cache Orphan",
                            "key":  f"HKCU\\...\\MuiCache",
                            "desc": f"Missing exe: {exe}",
                            "hive": winreg.HKEY_CURRENT_USER,
                            "path": path, "subkey": name,
                        })
                except: pass
            winreg.CloseKey(key)
        except: pass
        return issues[:30]

# ── Fonts ─────────────────────────────────────────────────────────────────────
class FontsWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import winreg
            fonts = []
            path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
            key  = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
            for i in range(winreg.QueryInfoKey(key)[1]):
                try:
                    name, val, _ = winreg.EnumValue(key, i)
                    full_path = val if os.path.isabs(val) else os.path.join(
                        os.environ.get("WINDIR","C:\\Windows"), "Fonts", val)
                    size_kb = 0
                    try: size_kb = round(os.path.getsize(full_path)/1024, 1)
                    except: pass
                    fonts.append({"name": name, "file": val,
                                  "path": full_path, "size_kb": size_kb})
                except: pass
            winreg.CloseKey(key)
            fonts.sort(key=lambda x: x['name'])
            self.result.emit(fonts)
        except Exception as e:
            self.error.emit(str(e))

# ── Update Checker ────────────────────────────────────────────────────────────
class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str)   # version, download_url
    up_to_date       = pyqtSignal()
    error            = pyqtSignal(str)

    def __init__(self, current_version, api_url):
        super().__init__()
        self.current_version = current_version
        self.api_url = api_url

    def run(self):
        try:
            import urllib.request, json
            req = urllib.request.Request(self.api_url,
                headers={"User-Agent": "AlagorCore-Updater"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
            latest = data.get("tag_name","").lstrip("v")
            if self._newer(latest, self.current_version):
                assets = data.get("assets",[])
                url = assets[0]["browser_download_url"] if assets else data.get("html_url","")
                self.update_available.emit(latest, url)
            else:
                self.up_to_date.emit()
        except Exception as e:
            self.error.emit(str(e))

    def _newer(self, a, b):
        try:
            av = [int(x) for x in a.split(".")]
            bv = [int(x) for x in b.split(".")]
            return av > bv
        except: return False

class UpdateDownloader(QThread):
    progress = pyqtSignal(int)
    done     = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            import urllib.request, tempfile
            dest = os.path.join(tempfile.gettempdir(), "AlagorCore_Update.exe")
            def reporthook(count, block, total):
                if total > 0:
                    pct = min(int(count * block * 100 / total), 100)
                    self.progress.emit(pct)
            urllib.request.urlretrieve(self.url, dest, reporthook)
            self.done.emit(dest)
        except Exception as e:
            self.error.emit(str(e))
