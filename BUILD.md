# AlagorCore — Build Instructions

## Requirements
- Windows 10/11 (64-bit)
- Python 3.10+ → https://www.python.org/downloads/
- Inno Setup 6 → https://jrsoftware.org/isdl.php

---

## Step 1 — Install Python dependencies

Open PowerShell in the project folder and run:

```powershell
pip install pyqt6 psutil pyinstaller
```

---

## Step 2 — Build the .exe with PyInstaller

```powershell
cd path\to\alagorcore
pyinstaller alagorcore.spec
```

This creates `dist\AlagorCore.exe` — a standalone Windows executable.

---

## Step 3 — Build the installer with Inno Setup

1. Open **Inno Setup Compiler**
2. Open `installer.iss`
3. Click **Build → Compile** (or press F9)
4. The installer is created at `installer_output\AlagorCore_v1.0.0_Setup.exe`

---

## Step 4 — Configure before distributing

Before building, edit `src/config.py`:

```python
GITHUB_REPO       = "YOUR_USERNAME/alagorcore"   # Your GitHub repo
PAYPAL_DONATE_URL = "https://paypal.me/YOURNAME"  # Your PayPal.me link
```

---

## Updating the app

1. Edit `src/config.py` → bump `APP_VERSION = "1.1.0"`
2. Run PyInstaller again → `pyinstaller alagorcore.spec`
3. Run Inno Setup again → new installer built
4. Push a new GitHub Release tagged `v1.1.0` and upload the new installer as a release asset
5. AlagorCore will auto-detect the new version on next launch and download it silently

---

## Project structure

```
alagorcore/
├── src/
│   ├── main.py          ← entry point, main window
│   ├── pages.py         ← all 20 section pages
│   ├── workers.py       ← background QThread workers
│   ├── widgets.py       ← reusable UI components
│   ├── themes.py        ← dark/light stylesheets
│   ├── translations.py  ← English + Arabic strings
│   └── config.py        ← version, URLs, settings
├── alagorcore.spec      ← PyInstaller build config
├── installer.iss        ← Inno Setup installer script
└── BUILD.md             ← this file
```

---

## All 20 sections included

| # | Section | Features |
|---|---------|----------|
| 1  | Dashboard          | Live CPU/RAM/Disk overview |
| 2  | Startup Manager    | Registry + startup folder, disable entries |
| 3  | RAM Monitor        | Per-process memory, kill, live polling toggle |
| 4  | CPU Processes      | Per-process CPU%, kill, live polling toggle |
| 5  | Services Manager   | Start/stop/disable/enable services |
| 6  | Uninstall Manager  | Full registry scan, launch uninstaller |
| 7  | PC Specs           | CPU, GPU, RAM sticks, mobo, BIOS, disks, monitors |
| 8  | Disk Analyzer      | Folder size breakdown for any drive |
| 9  | Network Monitor    | Active connections per process, kill |
| 10 | Junk Cleaner       | Temp, prefetch, cache — scan then clean |
| 11 | Driver Manager     | All drivers, unsigned flag |
| 12 | Scheduled Tasks    | View/disable/delete hidden tasks |
| 13 | Windows Features   | Enable/disable optional components |
| 14 | Battery Health     | Wear level, capacity, health % |
| 15 | Windows Updates    | Update history, pause updates |
| 16 | Registry Cleaner   | Orphaned uninstall, file assoc, MUI cache |
| 17 | Hosts File         | View and edit hosts file |
| 18 | Env Variables      | System and user environment variables |
| 19 | Font Manager       | List/uninstall fonts |
| 20 | Windows Tweaks     | Privacy, UI, performance, security, network tweaks + presets |
| +  | Settings           | Theme toggle, language toggle, PayPal config, update check |
