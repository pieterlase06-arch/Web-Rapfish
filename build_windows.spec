# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ============================================================================
# ARCHITECT CONFIGURATION
# ============================================================================
# Kita mengumpulkan semua submodule dari library berat secara otomatis
# untuk menghindari error 'ModuleNotFound' pada saat runtime.
# ============================================================================

hidden_imports = []
hidden_imports += collect_submodules('flask')
hidden_imports += collect_submodules('pandas')
hidden_imports += collect_submodules('numpy')
hidden_imports += collect_submodules('sklearn')
hidden_imports += collect_submodules('scipy')
hidden_imports += collect_submodules('webview')
hidden_imports += ['engineio.async_drivers.threading', 'xlsxwriter', 'openpyxl', 'xlrd']

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'notebook', 'tkinter', 'PyQt5', 'PyQt6', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Web-Rapfish',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Sembunyikan console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None # Tambahkan icon.ico di sini jika ada
)
