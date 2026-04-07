# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

# 项目根目录
project_root = Path(os.path.abspath('.'))

block_cipher = None

# 收集 pkg_resources 及其所有依赖
pkg_resources_datas, pkg_resources_binaries, pkg_resources_hiddenimports = collect_all('pkg_resources')

# 分析依赖
a = Analysis(
    ['src/backend/main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # 前端静态文件
        ('src/frontend', 'src/frontend'),
        # aria2c 可执行文件（如果存在）
        ('aria2c/aria2c.exe', 'aria2c'),
    ] + pkg_resources_datas,
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'pydantic',
        'requests',
        'psutil',
        'webview',
        'src.backend.models',
        'src.backend.config',
        'src.backend.aria2_client',
        'src.backend.aria2_process',
        'src.backend.server',
    ] + pkg_resources_hiddenimports,
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 去除重复项
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 创建可执行文件
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Aria2cUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # 图标（如果有的话）
    # icon='assets/icon.ico',
)

# 收集所有文件
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Aria2cUI'
)