# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

# 项目根目录
project_root = Path(os.path.abspath('.'))

icon_path = Path('assets/icon.ico')
icon = str(icon_path) if icon_path.exists() else None

# 分析依赖
a = Analysis(
    ['src/backend/main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # 前端静态文件（css/js）
        ('src/frontend', 'src/frontend'),
        # aria2c 可执行文件
        ('aria2c/aria2c.exe', 'aria2c'),
    ],
    hiddenimports=[
        'pydantic',
        'requests',
        'psutil',
        'webview',
        'src.backend.models',
        'src.backend.config',
        'src.backend.history',
        'src.backend.aria2_client',
        'src.backend.aria2_process',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'pytest', 'uvicorn', 'fastapi'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

# 创建字节码归档
pyz = PYZ(a.pure, a.zipped_data)

# 创建可执行文件
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Aria2cUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    icon=icon,
)

# 收集所有文件（文件夹模式）
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='Aria2cUI'
)
