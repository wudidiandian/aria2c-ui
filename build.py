#!/usr/bin/env python3
"""
Aria2c UI 构建脚本
用于打包 Windows 可执行文件
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean_build():
    """清理构建目录"""
    dirs_to_remove = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            print(f"删除 {dir_name}...")
            shutil.rmtree(dir_name)
    
    # 清理 .pyc 文件
    for pyc_file in Path('.').rglob('*.pyc'):
        pyc_file.unlink()
    for pycache in Path('.').rglob('__pycache__'):
        if pycache.is_dir():
            shutil.rmtree(pycache)


def download_aria2c():
    """下载 aria2c（如果需要）"""
    aria2c_dir = Path('aria2c')
    aria2c_exe = aria2c_dir / 'aria2c.exe'
    
    if aria2c_exe.exists():
        print("aria2c.exe 已存在")
        return True
    
    print("请手动下载 aria2c Windows 版本：")
    print("1. 访问 https://github.com/aria2/aria2/releases")
    print("2. 下载 aria2-1.37.0-win-64bit-build1.zip")
    print("3. 解压并将 aria2c.exe 放到 aria2c/ 目录")
    
    # 创建目录
    aria2c_dir.mkdir(exist_ok=True)
    
    return False


def build():
    """构建可执行文件"""
    print("开始构建 Aria2c UI...")
    
    # 检查 aria2c
    if not download_aria2c():
        print("警告：aria2c.exe 不存在，打包后的程序可能无法正常工作")
        response = input("是否继续构建？(y/n): ")
        if response.lower() != 'y':
            return
    
    # 清理
    clean_build()
    
    # 安装依赖
    print("安装依赖...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
    
    # 使用 PyInstaller 构建
    print("构建可执行文件...")
    subprocess.run([
        sys.executable, '-m', 'PyInstaller',
        'aria2c-ui.spec',
        '--clean',
        '--noconfirm'
    ], check=True)
    
    # 复制额外文件
    dist_dir = Path('dist/Aria2cUI')
    if dist_dir.exists():
        # 确保 aria2c 目录存在
        aria2c_dist = dist_dir / 'aria2c'
        aria2c_dist.mkdir(exist_ok=True)
        
        # 如果 aria2c.exe 存在，复制它
        if Path('aria2c/aria2c.exe').exists():
            shutil.copy('aria2c/aria2c.exe', aria2c_dist / 'aria2c.exe')
            print("已复制 aria2c.exe")
        
        print(f"\n构建完成！输出目录: {dist_dir.absolute()}")
        print(f"可执行文件: {dist_dir / 'Aria2cUI.exe'}")
    else:
        print("构建失败，未找到输出目录")


def build_onefile():
    """构建单文件版本"""
    print("构建单文件版本...")
    
    # 检查 aria2c
    if not Path('aria2c/aria2c.exe').exists():
        print("警告：aria2c.exe 不存在")
    
    # 清理
    clean_build()
    
    # 构建单文件
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name', 'Aria2cUI',
        '--add-data', 'src/frontend;src/frontend',
        '--add-data', 'aria2c/aria2c.exe;aria2c',
        '--hidden-import', 'uvicorn.logging',
        '--hidden-import', 'uvicorn.loops.auto',
        '--hidden-import', 'uvicorn.protocols.http.auto',
        '--hidden-import', 'fastapi',
        '--hidden-import', 'pydantic',
        '--hidden-import', 'requests',
        '--hidden-import', 'psutil',
        '--hidden-import', 'webview',
        'src/backend/main.py'
    ]
    
    subprocess.run(cmd, check=True)
    
    print("\n单文件版本构建完成！")
    print(f"输出: {Path('dist/Aria2cUI.exe').absolute()}")


def run_dev():
    """运行开发服务器"""
    print("启动开发服务器...")
    os.environ['PYTHONPATH'] = str(Path(__file__).parent)
    subprocess.run([sys.executable, 'src/backend/main.py'])


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Aria2c UI 构建工具')
    parser.add_argument('command', choices=['build', 'onefile', 'clean', 'dev'], 
                       help='构建命令: build(文件夹模式), onefile(单文件), clean(清理), dev(开发运行)')
    
    args = parser.parse_args()
    
    if args.command == 'build':
        build()
    elif args.command == 'onefile':
        build_onefile()
    elif args.command == 'clean':
        clean_build()
        print("清理完成")
    elif args.command == 'dev':
        run_dev()