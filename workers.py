import os, sys, subprocess, platform, json
from PyQt6.QtCore import QThread, pyqtSignal

# ── Hidden subprocess helper ─────────────────────────────────────────────────
CREATE_NO_WINDOW = 0x08000000

def _ps(cmd, timeout=30):
    """Run PowerShell completely hidden — no window flash."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", cmd],
            capture_output=True, text=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0
        )
        return r.stdout.strip()
    except Exception:
        return ""

def _wmic(obj, field):
    """Use PowerShell WMI instead of wmic.exe for reliability."""
    try:
        cmd = f"(Get-WmiObject {obj}).{field}"
        result = _ps(cmd, timeout=15)
        if result and result.strip() and result.strip() != "N/A":
            return result.strip()
    except Exception:
        pass
    return "N/A"

def _run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
            creationflags=CREATE_NO_WINDOW if sys.platform=="win32" else 0)
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
                (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
            ]
            for hive, path, hive_name in locations:
                try:
                    key = winreg.OpenKey(hive, path)
                    i = 0
                    while True:
                        try:
                            name, val, _ = winreg.EnumValue(key, i)
                            exe_path = val.strip('"').split('"')[0].split()[0] if val else ""
                            size_mb = 0
                            try:
                                if os.path.exists(exe_path):
                                    size_mb = round(os.path.getsize(exe_path)/1024**2, 1)
                            except: pass
                            impact = "Heavy" if size_mb > 50 else "Medium" if size_mb > 10 else "Light"
                            entries.append({
                                "name": name, "command": val,
                                "location": f"{hive_name}\\...\\Run",
                                "hive": hive, "path": path,
                                "enabled": True, "impact": impact,
                                "size_mb": size_mb,
                            })
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(key)
                except Exception:
                    pass

            # Startup folders
            for folder in [
                os.path.join(os.environ.get("APPDATA",""), r"Microsoft\Windows\Start Menu\Programs\Startup"),
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp",
            ]:
                if os.path.isdir(folder):
                    for f in os.listdir(folder):
                        fp = os.path.join(folder, f)
                        size_mb = 0
                        try: size_mb = round(os.path.getsize(fp)/1024**2, 1)
                        except: pass
                        impact = "Heavy" if size_mb > 50 else "Medium" if size_mb > 5 else "Light"
                        entries.append({
                            "name": f, "command": fp,
                            "location": "Startup Folder",
                            "hive": None, "path": folder,
                            "enabled": True, "impact": impact,
                            "size_mb": size_mb,
                        })
            self.result.emit(entries)
        except Exception as e:
            self.error.emit(str(e))

# ── Boot Time ─────────────────────────────────────────────────────────────────
class BootTimeWorker(QThread):
    result = pyqtSignal(dict)

    def run(self):
        try:
            import psutil, datetime
            boot = psutil.boot_time()
            boot_dt = datetime.datetime.fromtimestamp(boot)
            now = datetime.datetime.now()
            uptime = now - boot_dt
            days = uptime.days
            hours = uptime.seconds // 3600
            mins  = (uptime.seconds % 3600) // 60
            self.result.emit({
                "boot_time": boot_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "uptime_str": f"{days}d {hours}h {mins}m",
                "uptime_seconds": uptime.total_seconds(),
            })
        except Exception:
            self.result.emit({"boot_time":"N/A","uptime_str":"N/A","uptime_seconds":0})

# ── RAM ──────────────────────────────────────────────────────────────────────
class RamWorker(QThread):
    result = pyqtSignal(dict)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import psutil
            vm = psutil.virtual_memory()
            sw = psutil.swap_memory()

            # RAM sticks detail
            sticks = []
            try:
                out = _ps("Get-WmiObject Win32_PhysicalMemory | Select-Object Capacity,Speed,Manufacturer,PartNumber,DeviceLocator,MemoryType,SMBIOSMemoryType | ConvertTo-Json -Compress")
                if out:
                    data = json.loads(out)
                    if isinstance(data, dict): data = [data]
                    for s in data:
                        cap = int(s.get("Capacity",0))
                        mtype = s.get("SMBIOSMemoryType", 0)
                        type_map = {26:"DDR4", 34:"DDR5", 24:"DDR3", 20:"DDR2"}
                        ram_type = type_map.get(mtype, f"DDR({mtype})")
                        sticks.append({
                            "slot":     s.get("DeviceLocator",""),
                            "capacity": round(cap/1024**3, 1),
                            "speed":    s.get("Speed","N/A"),
                            "manufacturer": s.get("Manufacturer","N/A").strip(),
                            "part":     s.get("PartNumber","N/A").strip(),
                            "type":     ram_type,
                        })
            except: pass

            procs = []
            for p in psutil.process_iter(['pid','name','memory_info','memory_percent','status','exe']):
                try:
                    mi = p.info['memory_info']
                    procs.append({
                        "pid":    p.info['pid'],
                        "name":   p.info['name'],
                        "rss_mb": round(mi.rss/1024**2, 1),
                        "vms_mb": round(mi.vms/1024**2, 1),
                        "pct":    round(p.info['memory_percent'], 2),
                        "status": p.info['status'],
                        "exe":    p.info['exe'] or "",
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            procs.sort(key=lambda x: x['rss_mb'], reverse=True)

            self.result.emit({
                "total_gb":   round(vm.total/1024**3, 2),
                "used_gb":    round(vm.used/1024**3, 2),
                "free_gb":    round(vm.available/1024**3, 2),
                "pct":        vm.percent,
                "swap_total": round(sw.total/1024**3, 2),
                "swap_used":  round(sw.used/1024**3, 2),
                "sticks":     sticks,
                "processes":  procs,
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
            cpu_pct  = psutil.cpu_percent(interval=1)
            per_core = psutil.cpu_percent(interval=0, percpu=True)
            freq     = psutil.cpu_freq()

            # Full CPU info via WMI
            cpu_name    = _wmic("Win32_Processor", "Name")
            cpu_mfr     = _wmic("Win32_Processor", "Manufacturer")
            max_clock   = _wmic("Win32_Processor", "MaxClockSpeed")
            cur_clock   = _wmic("Win32_Processor", "CurrentClockSpeed")
            l2_cache    = _wmic("Win32_Processor", "L2CacheSize")
            l3_cache    = _wmic("Win32_Processor", "L3CacheSize")
            socket      = _wmic("Win32_Processor", "SocketDesignation")
            arch        = _wmic("Win32_Processor", "Architecture")
            arch_map    = {"0":"x86","1":"MIPS","2":"Alpha","3":"PowerPC","5":"ARM","6":"ia64","9":"x86-64"}
            arch_str    = arch_map.get(str(arch), arch)

            procs = []
            for p in psutil.process_iter(['pid','name','cpu_percent','status','exe','username']):
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
                "name":       cpu_name,
                "manufacturer": cpu_mfr,
                "total_pct":  cpu_pct,
                "per_core":   per_core,
                "freq_mhz":   round(freq.current) if freq else int(cur_clock) if cur_clock.isdigit() else 0,
                "freq_max":   round(freq.max) if freq else int(max_clock) if max_clock.isdigit() else 0,
                "cores":      psutil.cpu_count(logical=False),
                "threads":    psutil.cpu_count(logical=True),
                "l2_kb":      l2_cache,
                "l3_kb":      l3_cache,
                "socket":     socket,
                "arch":       arch_str,
                "processes":  procs,
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

    BLOAT_KEYWORDS = [
        'candy crush','king.com','mcafee','norton','wildtangent','booking.com',
        'spotify','tiktok','facebook','twitter','amazon alexa','cortana',
        '3d viewer','get help','maps','msn','solitaire','paint 3d',
        'mixed reality','groove music','movies & tv','xbox game bar',
        'skype','microsoft teams','hp support','dell support','lenovo vantage',
    ]

    def run(self):
        try:
            import winreg, datetime
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
                            loc = gv("InstallLocation","")
                            drive = os.path.splitdrive(loc)[0] if loc else "N/A"
                            app_type = "Store" if not gv("UninstallString") else "Win32"
                            is_bloat = any(k in name.lower() for k in self.BLOAT_KEYWORDS)
                            apps.append({
                                "name":         name,
                                "version":      gv("DisplayVersion"),
                                "publisher":    gv("Publisher"),
                                "size_mb":      round(int(gv("EstimatedSize",0))/1024, 1),
                                "install_date": gv("InstallDate"),
                                "uninstall":    gv("UninstallString"),
                                "location":     loc,
                                "drive":        drive or "N/A",
                                "type":         app_type,
                                "bloat":        is_bloat,
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

            cpu_name  = _wmic("Win32_Processor", "Name")
            cpu_cores = _wmic("Win32_Processor", "NumberOfCores")
            cpu_threads = _wmic("Win32_Processor", "NumberOfLogicalProcessors")
            cpu_max   = _wmic("Win32_Processor", "MaxClockSpeed")
            cpu_cur   = _wmic("Win32_Processor", "CurrentClockSpeed")
            cpu_l2    = _wmic("Win32_Processor", "L2CacheSize")
            cpu_l3    = _wmic("Win32_Processor", "L3CacheSize")
            cpu_socket= _wmic("Win32_Processor", "SocketDesignation")

            gpu_name  = _wmic("Win32_VideoController", "Name")
            gpu_vram  = _wmic("Win32_VideoController", "AdapterRAM")
            gpu_driver= _wmic("Win32_VideoController", "DriverVersion")
            gpu_res   = _wmic("Win32_VideoController", "VideoModeDescription")

            board     = _wmic("Win32_BaseBoard", "Product")
            board_mfr = _wmic("Win32_BaseBoard", "Manufacturer")
            board_ver = _wmic("Win32_BaseBoard", "Version")
            bios_ver  = _wmic("Win32_BIOS", "SMBIOSBIOSVersion")
            bios_mfr  = _wmic("Win32_BIOS", "Manufacturer")
            bios_date = _wmic("Win32_BIOS", "ReleaseDate")

            os_name   = _wmic("Win32_OperatingSystem", "Caption")
            os_build  = _wmic("Win32_OperatingSystem", "BuildNumber")
            os_arch   = _wmic("Win32_OperatingSystem", "OSArchitecture")
            os_serial = _wmic("Win32_OperatingSystem", "SerialNumber")

            # RAM sticks
            sticks = []
            try:
                out = _ps("Get-WmiObject Win32_PhysicalMemory | Select-Object Capacity,Speed,Manufacturer,PartNumber,DeviceLocator,SMBIOSMemoryType | ConvertTo-Json -Compress")
                if out:
                    data = json.loads(out)
                    if isinstance(data, dict): data = [data]
                    for s in data:
                        cap = int(s.get("Capacity",0))
                        mtype = s.get("SMBIOSMemoryType",0)
                        type_map = {26:"DDR4",34:"DDR5",24:"DDR3",20:"DDR2"}
                        sticks.append({
                            "slot":     s.get("DeviceLocator",""),
                            "capacity": round(cap/1024**3,1),
                            "speed":    s.get("Speed","N/A"),
                            "manufacturer": s.get("Manufacturer","N/A").strip(),
                            "part":     s.get("PartNumber","N/A").strip(),
                            "type":     type_map.get(mtype, f"DDR"),
                        })
            except: pass

            # Monitors
            monitors = []
            try:
                out = _ps("""
Get-WmiObject -Namespace root/wmi -Class WmiMonitorID | ForEach-Object {
    $name = [System.Text.Encoding]::ASCII.GetString($_.UserFriendlyName).Trim([char]0).Trim()
    if ($name) { $name }
}
""")
                monitors = [m.strip() for m in out.splitlines() if m.strip() and len(m.strip()) > 2]
            except: pass

            # Network adapters
            adapters = []
            try:
                out = _ps("Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object Name,InterfaceDescription,LinkSpeed,MacAddress,MediaType | ConvertTo-Json -Compress")
                if out:
                    data = json.loads(out)
                    if isinstance(data, dict): data = [data]
                    for a in data:
                        adapters.append({
                            "name":        a.get("Name",""),
                            "description": a.get("InterfaceDescription",""),
                            "speed":       a.get("LinkSpeed",""),
                            "mac":         a.get("MacAddress",""),
                            "type":        a.get("MediaType",""),
                        })
            except: pass

            # Disks
            disks = []
            try:
                out = _ps("Get-WmiObject Win32_DiskDrive | Select-Object Model,Size,MediaType,SerialNumber,InterfaceType | ConvertTo-Json -Compress")
                if out:
                    data = json.loads(out)
                    if isinstance(data, dict): data = [data]
                    for d in data:
                        sz = int(d.get("Size",0) or 0)
                        disks.append({
                            "model":     d.get("Model","N/A"),
                            "size_gb":   round(sz/1024**3,1),
                            "type":      d.get("MediaType","N/A"),
                            "serial":    d.get("SerialNumber","N/A"),
                            "interface": d.get("InterfaceType","N/A"),
                        })
            except: pass

            # Partitions
            partitions = []
            for p in psutil.disk_partitions():
                try:
                    u = psutil.disk_usage(p.mountpoint)
                    partitions.append({
                        "device":    p.device,
                        "mountpoint":p.mountpoint,
                        "fstype":    p.fstype,
                        "total_gb":  round(u.total/1024**3,1),
                        "used_gb":   round(u.used/1024**3,1),
                        "free_gb":   round(u.free/1024**3,1),
                        "pct":       u.percent,
                    })
                except: pass

            vm = psutil.virtual_memory()
            vram_gb = "N/A"
            try:
                vram_bytes = int(gpu_vram)
                vram_gb = f"{round(vram_bytes/1024**3,1)} GB"
            except: pass

            bios_date_clean = bios_date[:8] if bios_date and len(bios_date) >= 8 else bios_date

            self.result.emit({
                "os":          os_name or f"{uname.system} {uname.release}",
                "os_build":    os_build,
                "os_arch":     os_arch or uname.machine,
                "hostname":    uname.node,
                "os_serial":   os_serial,
                "cpu":         cpu_name,
                "cpu_cores":   cpu_cores,
                "cpu_threads": cpu_threads,
                "cpu_max_mhz": cpu_max,
                "cpu_cur_mhz": cpu_cur,
                "cpu_l2":      cpu_l2,
                "cpu_l3":      cpu_l3,
                "cpu_socket":  cpu_socket,
                "gpu":         gpu_name,
                "gpu_vram":    vram_gb,
                "gpu_driver":  gpu_driver,
                "gpu_res":     gpu_res,
                "ram_total":   round(vm.total/1024**3,2),
                "ram_sticks":  sticks,
                "motherboard": f"{board_mfr} {board} {board_ver}".strip(),
                "bios":        bios_ver,
                "bios_mfr":    bios_mfr,
                "bios_date":   bios_date_clean,
                "disks":       disks,
                "partitions":  partitions,
                "monitors":    monitors,
                "adapters":    adapters,
            })
        except Exception as e:
            self.error.emit(str(e))

# ── Disk Analyzer ─────────────────────────────────────────────────────────────
class DiskWorker(QThread):
    result   = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, path="C:\\"):
        super().__init__()
        self.path = path

    def run(self):
        try:
            import psutil

            # Drive info
            drive_info = {}
            try:
                out = _ps("Get-WmiObject Win32_DiskDrive | Select-Object Model,Size,SerialNumber,InterfaceType | ConvertTo-Json -Compress")
                if out:
                    data = json.loads(out)
                    if isinstance(data, dict): data = [data]
                    drive_info["physical"] = data
            except: pass

            # Partitions
            partitions = []
            for p in psutil.disk_partitions():
                try:
                    u = psutil.disk_usage(p.mountpoint)
                    partitions.append({
                        "device": p.device, "mountpoint": p.mountpoint,
                        "fstype": p.fstype,
                        "total_gb": round(u.total/1024**3,1),
                        "used_gb":  round(u.used/1024**3,1),
                        "free_gb":  round(u.free/1024**3,1),
                        "pct":      u.percent,
                    })
                except: pass

            # Folder breakdown
            folders = []
            self.progress.emit(f"Scanning {self.path}...")
            try:
                for entry in os.scandir(self.path):
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            size = self._dir_size(entry.path)
                            folders.append({"name": entry.name, "path": entry.path,
                                            "size_mb": round(size/1024**2,1), "type":"folder"})
                        else:
                            size = entry.stat(follow_symlinks=False).st_size
                            folders.append({"name": entry.name, "path": entry.path,
                                            "size_mb": round(size/1024**2,1), "type":"file"})
                    except: pass
            except: pass
            folders.sort(key=lambda x: x['size_mb'], reverse=True)

            # Largest files
            self.progress.emit("Finding largest files...")
            largest = []
            try:
                for root, dirs, files in os.walk(self.path):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for f in files:
                        try:
                            fp = os.path.join(root, f)
                            sz = os.path.getsize(fp)
                            largest.append({"name": f, "path": fp, "size_mb": round(sz/1024**2,1)})
                        except: pass
                    if len(largest) > 5000: break
            except: pass
            largest.sort(key=lambda x: x['size_mb'], reverse=True)

            self.result.emit({
                "partitions": partitions,
                "drive_info": drive_info,
                "folders":    folders[:50],
                "largest":    largest[:20],
            })
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
                except: pass
        except: pass
        return total

# ── Network ───────────────────────────────────────────────────────────────────
class NetworkWorker(QThread):
    result = pyqtSignal(dict)
    error  = pyqtSignal(str)

    def run(self):
        try:
            import psutil
            conns = []
            for c in psutil.net_connections(kind='inet'):
                try:
                    proc_name = proc_exe = ""
                    if c.pid:
                        try:
                            p = psutil.Process(c.pid)
                            proc_name = p.name()
                            proc_exe  = p.exe()
                        except: pass
                    laddr = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ""
                    raddr = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ""
                    # Skip pure loopback
                    if c.laddr and c.laddr.ip == "127.0.0.1" and (not c.raddr or c.raddr.ip == "127.0.0.1"):
                        continue
                    conns.append({
                        "pid":    c.pid or 0,
                        "name":   proc_name,
                        "exe":    proc_exe,
                        "laddr":  laddr,
                        "raddr":  raddr,
                        "status": c.status,
                        "type":   "TCP" if c.type.name == "SOCK_STREAM" else "UDP",
                    })
                except: pass
            conns.sort(key=lambda x: x['name'])

            # Adapters
            adapters = []
            try:
                out = _ps("Get-NetAdapter | Select-Object Name,InterfaceDescription,LinkSpeed,MacAddress,Status,MediaType | ConvertTo-Json -Compress")
                if out:
                    data = json.loads(out)
                    if isinstance(data, dict): data = [data]
                    for a in data:
                        adapters.append({
                            "name":    a.get("Name",""),
                            "desc":    a.get("InterfaceDescription",""),
                            "speed":   a.get("LinkSpeed",""),
                            "mac":     a.get("MacAddress",""),
                            "status":  a.get("Status",""),
                            "type":    a.get("MediaType",""),
                        })
            except: pass

            # IO counters
            io = psutil.net_io_counters()

            self.result.emit({
                "connections": conns,
                "adapters":    adapters,
                "bytes_sent":  io.bytes_sent,
                "bytes_recv":  io.bytes_recv,
                "packets_sent":io.packets_sent,
                "packets_recv":io.packets_recv,
            })
        except Exception as e:
            self.error.emit(str(e))

# ── Speed Test ────────────────────────────────────────────────────────────────
class SpeedTestWorker(QThread):
    result   = pyqtSignal(dict)
    progress = pyqtSignal(str)
    error    = pyqtSignal(str)

    # Large test files from reliable CDNs
    DL_URLS = [
        "https://speed.cloudflare.com/__down?bytes=25000000",
        "http://speedtest.tele2.net/25MB.zip",
        "http://ipv4.download.thinkbroadband.com/25MB.zip",
    ]

    def run(self):
        try:
            import urllib.request, time, socket

            self.progress.emit("Measuring ping...")
            ping_ms, jitter = self._measure_ping("8.8.8.8", count=8)

            self.progress.emit("Testing download speed...")
            dl_mbps = self._test_download()

            self.progress.emit("Testing upload speed...")
            ul_mbps = self._test_upload()

            self.result.emit({
                "download_mbps": dl_mbps,
                "upload_mbps":   ul_mbps,
                "ping_ms":       ping_ms,
                "jitter_ms":     jitter,
                "server":        "Nearest CDN",
                "isp":           "",
            })
        except Exception as e:
            self.error.emit(str(e))

    def _measure_ping(self, host, count=8):
        """Use Windows ping command for accurate ICMP results."""
        import subprocess, re, time
        times = []
        try:
            result = subprocess.run(
                ["ping", "-n", str(count), host],
                capture_output=True, text=True, timeout=20,
                creationflags=0x08000000
            )
            for line in result.stdout.splitlines():
                m = re.search(r"time[=<](\d+)ms", line, re.IGNORECASE)
                if m:
                    times.append(float(m.group(1)))
            # Also try to get average from summary line
            avg_match = re.search(r"Average\s*=\s*(\d+)ms", result.stdout, re.IGNORECASE)
            if avg_match and times:
                avg = float(avg_match.group(1))
                jitter = round(max(times) - min(times), 1) if len(times) > 1 else 0
                return round(avg, 1), jitter
        except: pass
        if times:
            avg = round(sum(times)/len(times), 1)
            jitter = round(max(times)-min(times), 1) if len(times)>1 else 0
            return avg, jitter
        return 0, 0

    def _test_download(self):
        import urllib.request, time
        for url in self.DL_URLS:
            try:
                self.progress.emit(f"Downloading test file...")
                req = urllib.request.Request(url, headers={"User-Agent":"AlCore/1.0"})
                t0 = time.perf_counter()
                conn = urllib.request.urlopen(req, timeout=20)
                chunk_size = 65536
                downloaded = 0
                deadline = t0 + 10  # max 10 seconds
                while True:
                    chunk = conn.read(chunk_size)
                    if not chunk: break
                    downloaded += len(chunk)
                    if time.perf_counter() > deadline: break
                elapsed = time.perf_counter() - t0
                if elapsed > 0.5 and downloaded > 100000:
                    mbps = round((downloaded * 8) / elapsed / 1_000_000, 2)
                    return mbps
            except: continue
        return 0.0

    def _test_upload(self):
        import urllib.request, time
        try:
            # Cloudflare upload test with 10MB payload
            data = bytes(10 * 1024 * 1024)
            req = urllib.request.Request(
                "https://speed.cloudflare.com/__up",
                data=data,
                method="POST",
                headers={
                    "Content-Type": "application/octet-stream",
                    "User-Agent": "AlCore/1.0",
                    "Content-Length": str(len(data)),
                }
            )
            t0 = time.perf_counter()
            urllib.request.urlopen(req, timeout=30)
            elapsed = time.perf_counter() - t0
            if elapsed > 0.5:
                return round((len(data) * 8) / elapsed / 1_000_000, 2)
        except: pass
        return 0.0


# ── Junk Cleaner ──────────────────────────────────────────────────────────────
class JunkScanWorker(QThread):
    result   = pyqtSignal(list)
    progress = pyqtSignal(str)

    LOCATIONS = [
        ("%TEMP%",             "🗑️", "User Temp Files",          "Temporary files created by apps"),
        ("%WINDIR%\\Temp",     "🗑️", "Windows Temp",             "Windows system temporary files"),
        ("%WINDIR%\\Prefetch", "⚡", "Prefetch Files",           "App launch cache files"),
        ("%LOCALAPPDATA%\\Temp","🗑️","Local App Temp",           "Local application temp files"),
        ("%WINDIR%\\SoftwareDistribution\\Download","⬇️","Windows Update Cache","Downloaded Windows updates"),
        ("%LOCALAPPDATA%\\Microsoft\\Windows\\INetCache","🌐","Browser Cache (IE/Edge)","Internet Explorer and Edge cache"),
        ("%LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default\\Cache","🌐","Chrome Cache","Google Chrome cached files"),
        ("%LOCALAPPDATA%\\Microsoft\\Windows\\Explorer","🖼️","Thumbnail Cache","Windows thumbnail preview cache"),
        ("%APPDATA%\\Microsoft\\Windows\\Recent","📄","Recent Files List","Recently opened files history"),
        ("%WINDIR%\\Logs",     "📋","Windows Logs",              "Windows system log files"),
        ("%LOCALAPPDATA%\\CrashDumps","💥","Crash Dumps",         "Application crash dump files"),
        ("%LOCALAPPDATA%\\Microsoft\\Windows\\WER","💥","Error Reports","Windows Error Reporting files"),
    ]

    def run(self):
        results = []
        for raw_path, icon, label, desc in self.LOCATIONS:
            path = os.path.expandvars(raw_path)
            self.progress.emit(f"Scanning {label}...")
            if os.path.isdir(path):
                size  = self._dir_size(path)
                count = self._file_count(path)
                results.append({
                    "icon": icon, "label": label, "desc": desc,
                    "path": path, "size_mb": round(size/1024**2,1),
                    "files": count, "selected": True,
                })
        # Recycle bin
        try:
            rb_size = int(_ps("(New-Object -ComObject Shell.Application).Namespace(10).Items() | Measure-Object -Property Size -Sum | Select-Object -ExpandProperty Sum") or 0)
            results.append({
                "icon":"🗑️","label":"Recycle Bin","desc":"Files in the Recycle Bin",
                "path":"RECYCLE_BIN","size_mb":round(rb_size/1024**2,1),
                "files":0,"selected":False,
            })
        except: pass
        self.result.emit(results)

    def _dir_size(self, path):
        total = 0
        try:
            for dp, _, files in os.walk(path):
                for f in files:
                    try: total += os.path.getsize(os.path.join(dp,f))
                    except: pass
        except: pass
        return total

    def _file_count(self, path):
        count = 0
        try:
            for _,_,files in os.walk(path):
                count += len(files)
        except: pass
        return count

class JunkCleanWorker(QThread):
    progress = pyqtSignal(str)
    done     = pyqtSignal(int, int)

    def __init__(self, items):
        super().__init__()
        self.items = items

    def run(self):
        import shutil
        deleted = freed = 0
        for item in self.items:
            path = item["path"]
            self.progress.emit(f"Cleaning {item['label']}...")
            if path == "RECYCLE_BIN":
                _ps("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
                continue
            try:
                for entry in os.scandir(path):
                    try:
                        sz = os.path.getsize(entry.path) if entry.is_file() else 0
                        if entry.is_dir(): shutil.rmtree(entry.path, ignore_errors=True)
                        else: os.remove(entry.path)
                        freed += sz; deleted += 1
                    except: pass
            except: pass
        self.done.emit(deleted, freed)

# ── Drivers ───────────────────────────────────────────────────────────────────
class DriversWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            out = _ps("Get-WmiObject Win32_PnPSignedDriver | Select-Object DeviceName,DriverVersion,Manufacturer,DriverDate,IsSigned,DeviceClass,DeviceID,Status | ConvertTo-Json -Compress")
            drivers = []
            if out:
                data = json.loads(out)
                if isinstance(data, dict): data = [data]
                for d in data:
                    if not d.get("DeviceName"): continue
                    drivers.append({
                        "name":         d.get("DeviceName",""),
                        "version":      d.get("DriverVersion",""),
                        "manufacturer": d.get("Manufacturer",""),
                        "date":         str(d.get("DriverDate",""))[:10],
                        "signed":       d.get("IsSigned",False),
                        "class":        d.get("DeviceClass",""),
                        "device_id":    d.get("DeviceID",""),
                        "status":       d.get("Status",""),
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
            out = _ps("""
$tasks = Get-ScheduledTask | ForEach-Object {
    $info = $_ | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue
    [PSCustomObject]@{
        TaskName    = $_.TaskName
        TaskPath    = $_.TaskPath
        State       = $_.State.ToString()
        Description = $_.Description
        Author      = $_.Principal.UserId
        LastRun     = if($info) { $info.LastRunTime.ToString('yyyy-MM-dd HH:mm') } else { 'Never' }
        NextRun     = if($info) { $info.NextRunTime.ToString('yyyy-MM-dd HH:mm') } else { 'N/A' }
    }
}
$tasks | ConvertTo-Json -Compress
""")
            tasks = []
            if out:
                data = json.loads(out)
                if isinstance(data, dict): data = [data]
                for t in data:
                    tasks.append({
                        "name":        t.get("TaskName",""),
                        "path":        t.get("TaskPath",""),
                        "state":       t.get("State",""),
                        "description": t.get("Description","") or "",
                        "author":      t.get("Author","") or "",
                        "last_run":    t.get("LastRun",""),
                        "next_run":    t.get("NextRun",""),
                    })
            tasks.sort(key=lambda x: x['name'].lower())
            self.result.emit(tasks)
        except Exception as e:
            self.error.emit(str(e))

# ── Windows Features ──────────────────────────────────────────────────────────
FEATURE_DESCRIPTIONS = {
    "DirectPlay":                    "Legacy gaming network API for old DirectX games",
    "TelnetClient":                  "Command-line tool to connect to Telnet servers",
    "TFTP":                          "Trivial File Transfer Protocol client",
    "Containers":                    "Windows container support for Docker",
    "Microsoft-Hyper-V":             "Hardware virtualization platform",
    "VirtualMachinePlatform":        "Required for WSL2 and Windows Sandbox",
    "Microsoft-Windows-Subsystem-Linux":"Run Linux distributions natively on Windows",
    "WindowsSandbox":                "Isolated desktop for running untrusted software",
    "NetFx3":                        ".NET Framework 3.5 for legacy applications",
    "NetFx4-AdvSrvs":                ".NET Framework 4 advanced services",
    "IIS-WebServerRole":             "Internet Information Services web server",
    "MSMQ-Server":                   "Message queuing service for distributed apps",
    "WCF-Services45":                "Windows Communication Foundation services",
    "Printing-PrintToPDFServices-Features":"Print to PDF from any application",
    "Printing-XPSServices-Features": "XML Paper Specification document services",
    "WorkFolders-Client":            "Sync work files with corporate servers",
    "SmbDirect":                     "High-performance SMB file sharing via RDMA",
    "HostGuardian":                  "Security feature for shielded virtual machines",
    "Client-DeviceLockdown":         "Locks device to specific apps (kiosk mode)",
    "Client-EmbeddedBootExp":        "Custom boot experience for embedded devices",
    "Client-EmbeddedLogon":          "Custom login screen for embedded devices",
    "DataCenterBridging":            "Network traffic management for data centers",
    "ServicesForNFS-ClientOnly":     "Access NFS (Linux/Unix) network file shares",
    "SimpleTCP":                     "Simple TCP/IP services (ping echo, etc.)",
}

class WinFeaturesWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            out = _ps("Get-WindowsOptionalFeature -Online | Select-Object FeatureName,State | ConvertTo-Json -Compress")
            features = []
            if out:
                data = json.loads(out)
                if isinstance(data, dict): data = [data]
                for f in data:
                    name  = f.get("FeatureName","")
                    state = f.get("State","")
                    if hasattr(state, '__class__') and state.__class__.__name__ != 'str':
                        state = str(state)
                    enabled = "enabled" in str(state).lower()
                    desc = FEATURE_DESCRIPTIONS.get(name, "")
                    # Generate plain English from name if no description
                    if not desc:
                        desc = name.replace("-"," ").replace("_"," ")
                    features.append({
                        "name":        name,
                        "state":       "Enabled" if enabled else "Disabled",
                        "description": desc,
                        "enabled":     enabled,
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
            design_cap = full_cap = 0
            try:
                report_path = os.path.join(os.environ.get("TEMP",""), "battery_report.xml")
                _ps(f'powercfg /batteryreport /xml /output "{report_path}"')
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
            except: pass
            health_pct = round(full_cap/design_cap*100,1) if design_cap > 0 else None
            self.result.emit({
                "present":    True,
                "percent":    bat.percent,
                "plugged":    bat.power_plugged,
                "secs_left":  bat.secsleft,
                "design_cap": design_cap,
                "full_cap":   full_cap,
                "health_pct": health_pct,
            })
        except Exception as e:
            self.error.emit(str(e))

# ── Windows Updates ───────────────────────────────────────────────────────────
class UpdatesWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            out = _ps("""
Get-HotFix | Select-Object HotFixID,Description,InstalledOn,InstalledBy |
Sort-Object InstalledOn -Descending | ConvertTo-Json -Compress
""")
            updates = []
            if out:
                data = json.loads(out)
                if isinstance(data, dict): data = [data]
                for u in data:
                    installed = u.get("InstalledOn","")
                    if isinstance(installed, dict):
                        installed = installed.get("value","") or installed.get("DateTime","")
                    if installed:
                        try:
                            installed = str(installed)[:10]
                        except: pass
                    updates.append({
                        "id":           u.get("HotFixID",""),
                        "description":  u.get("Description",""),
                        "installed_on": installed,
                        "installed_by": u.get("InstalledBy",""),
                        "kb_url":       f"https://support.microsoft.com/kb/{u.get('HotFixID','').replace('KB','')}",
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
            self.progress.emit("Scanning startup entries...")
            issues += self._scan_startup(winreg)
            self.progress.emit("Scanning shared DLLs...")
            issues += self._scan_shared_dlls(winreg)
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
                                "type":"Orphaned Uninstall Entry","risk":"Safe",
                                "key": f"HKLM\\...\\Uninstall\\{sname}",
                                "desc":f"{name} — install path missing: {loc}",
                                "hive":winreg.HKEY_LOCAL_MACHINE,"path":path,"subkey":sname,
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
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,"")
            for i in range(min(winreg.QueryInfoKey(key)[0],500)):
                try:
                    ext = winreg.EnumKey(key,i)
                    if not ext.startswith("."): continue
                    ekey = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,ext)
                    try:
                        prog_id = winreg.QueryValue(ekey,"")
                        if prog_id:
                            try: winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,prog_id)
                            except:
                                issues.append({
                                    "type":"Broken File Association","risk":"Safe",
                                    "key":f"HKCR\\{ext}",
                                    "desc":f"{ext} → missing ProgID: {prog_id}",
                                    "hive":None,"path":"","subkey":ext,
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
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,path)
            for i in range(min(winreg.QueryInfoKey(key)[1],200)):
                try:
                    name,_,_ = winreg.EnumValue(key,i)
                    exe = name.split(".FriendlyAppName")[0].split(".ApplicationCompany")[0]
                    if exe and not os.path.exists(exe) and exe.endswith(".exe"):
                        issues.append({
                            "type":"MUI Cache Orphan","risk":"Safe",
                            "key":"HKCU\\...\\MuiCache",
                            "desc":f"Missing exe reference: {exe}",
                            "hive":winreg.HKEY_CURRENT_USER,"path":path,"subkey":name,
                        })
                except: pass
            winreg.CloseKey(key)
        except: pass
        return issues[:30]

    def _scan_startup(self, winreg):
        issues = []
        for hive, path, hname in [
            (winreg.HKEY_CURRENT_USER,  r"Software\Microsoft\Windows\CurrentVersion\Run","HKCU"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run","HKLM"),
        ]:
            try:
                key = winreg.OpenKey(hive, path)
                for i in range(winreg.QueryInfoKey(key)[1]):
                    try:
                        name, val, _ = winreg.EnumValue(key, i)
                        exe = val.strip('"').split('"')[0].split()[0] if val else ""
                        if exe and not os.path.exists(exe):
                            issues.append({
                                "type":"Invalid Startup Entry","risk":"Safe",
                                "key":f"{hname}\\...\\Run",
                                "desc":f"'{name}' points to missing file: {exe}",
                                "hive":hive,"path":path,"subkey":name,
                            })
                    except: pass
                winreg.CloseKey(key)
            except: pass
        return issues

    def _scan_shared_dlls(self, winreg):
        issues = []
        path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\SharedDLLs"
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
            for i in range(min(winreg.QueryInfoKey(key)[1], 300)):
                try:
                    name,_,_ = winreg.EnumValue(key,i)
                    if not os.path.exists(name):
                        issues.append({
                            "type":"Missing Shared DLL","risk":"Caution",
                            "key":f"HKLM\\...\\SharedDLLs",
                            "desc":f"Missing DLL: {name}",
                            "hive":winreg.HKEY_LOCAL_MACHINE,"path":path,"subkey":name,
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
                    ext = os.path.splitext(val)[1].upper().lstrip(".")
                    font_type = {"TTF":"TrueType","OTF":"OpenType","FON":"Bitmap","TTC":"TrueType Collection"}.get(ext, ext)
                    fonts.append({
                        "name": name, "file": val, "path": full_path,
                        "size_kb": size_kb, "type": font_type,
                    })
                except: pass
            winreg.CloseKey(key)
            fonts.sort(key=lambda x: x['name'])
            self.result.emit(fonts)
        except Exception as e:
            self.error.emit(str(e))


# ── Drive Scanner (background — disk I/O can block) ─────────────────────────
class _DriveScanWorker(QThread):
    result = pyqtSignal(list)

    def run(self):
        try:
            import psutil
            drives = []
            for p in psutil.disk_partitions(all=False):
                try:
                    if not p.mountpoint: continue
                    if p.fstype in ('', 'squashfs'): continue
                    u = psutil.disk_usage(p.mountpoint)
                    dev = p.device[:2] if len(p.device) >= 2 else p.device
                    drives.append({
                        'dev':   dev,
                        'fs':    p.fstype,
                        'used':  round(u.used/1024**3, 1),
                        'total': round(u.total/1024**3, 1),
                        'free':  round(u.free/1024**3, 1),
                        'pct':   u.percent,
                    })
                except: pass
            self.result.emit(drives)
        except: pass

# ── Process Scanner (lightweight background) ─────────────────────────────────
class _ProcScanWorker(QThread):
    result = pyqtSignal(list)

    def run(self):
        try:
            import psutil
            procs = []
            for p in psutil.process_iter(['pid','name','memory_info','cpu_percent','status']):
                try:
                    procs.append({
                        "name":   p.info['name'],
                        "ram":    round(p.info['memory_info'].rss/1024**2,1),
                        "cpu":    round(p.info['cpu_percent'] or 0,1),
                        "pid":    p.info['pid'],
                        "status": p.info['status'],
                    })
                except: pass
            self.result.emit(procs)
        except: pass

# ── Update Checker ────────────────────────────────────────────────────────────
class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str)
    up_to_date       = pyqtSignal()
    error            = pyqtSignal(str)

    def __init__(self, current_version, api_url):
        super().__init__()
        self.current_version = current_version
        self.api_url = api_url

    def run(self):
        try:
            import urllib.request
            req = urllib.request.Request(self.api_url, headers={"User-Agent":"AlCore-Updater"})
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
            return [int(x) for x in a.split(".")] > [int(x) for x in b.split(".")]
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
            dest = os.path.join(tempfile.gettempdir(), "AlCore_Update.exe")
            def reporthook(count, block, total):
                if total > 0:
                    self.progress.emit(min(int(count*block*100/total), 100))
            urllib.request.urlretrieve(self.url, dest, reporthook)
            self.done.emit(dest)
        except Exception as e:
            self.error.emit(str(e))
