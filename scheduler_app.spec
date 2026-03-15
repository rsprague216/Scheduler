# scheduler_app.spec
# PyInstaller build spec for Shift Scheduler (macOS, Windows, Linux)
#
# Build with:
#   pyinstaller scheduler_app.spec
#
# Output:
#   macOS   → dist/Shift Scheduler.app   (double-click in Finder)
#   Windows → dist/Shift Scheduler/Shift Scheduler.exe
#   Linux   → dist/Shift Scheduler/Shift Scheduler

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# reportlab ships font data and other resources outside .py files
reportlab_datas = collect_data_files("reportlab")
# tkcalendar needs babel locale data for date formatting
babel_datas = collect_data_files("babel")
tkcalendar_datas = collect_data_files("tkcalendar")
all_datas = reportlab_datas + babel_datas + tkcalendar_datas

hidden_imports = [
    "babel.dates",
    "babel.numbers",
    "PIL._tkinter_finder",
]

a = Analysis(
    ["scheduler_app.py"],
    pathex=[],
    binaries=[],
    datas=all_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "unittest", "email", "http", "html", "xml", "xmlrpc",
        "multiprocessing", "doctest", "pydoc",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Shift Scheduler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,         # No terminal window
    argv_emulation=False,  # MUST be False on macOS 13+ — True causes tkinter to hang at launch
    target_arch=None,      # None = match host architecture
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Shift Scheduler",
)

# macOS .app bundle — ignored on Windows/Linux
app = BUNDLE(
    coll,
    name="Shift Scheduler.app",
    icon=None,
    bundle_identifier="com.schedularapp.shiftscheduler",
    version="1.0.0",
    info_plist={
        "NSHighResolutionCapable": True,
        "NSPrincipalClass": "NSApplication",
        "NSAppleScriptEnabled": False,
        "NSRequiresAquaSystemAppearance": False,
        "LSMinimumSystemVersion": "12.0",
        "CFBundleDisplayName": "Shift Scheduler",
        "CFBundleName": "Shift Scheduler",
    },
)
