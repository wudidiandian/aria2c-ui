# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/backend/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[('src/frontend', 'src/frontend'), ('aria2c/aria2c.exe', 'aria2c')],
    hiddenimports=['pydantic', 'requests', 'psutil', 'webview', 'src.backend.models', 'src.backend.config', 'src.backend.history', 'src.backend.aria2_client', 'src.backend.aria2_process'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Aria2cUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
)
