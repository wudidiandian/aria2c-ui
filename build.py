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

_ROOT = Path(__file__).parent


def _venv_python():
    py = _ROOT / '.venv' / 'Scripts' / 'python.exe'
    return str(py) if py.exists() else None


def build_python():
    """找到带 PyInstaller 的解释器：当前 venv 优先，其次项目 .venv，最后回退当前解释器。

    解决直接用系统 python（如 Anaconda）运行 build.py 时 PyInstaller 缺失的问题。
    """
    candidates = []
    if sys.prefix != getattr(sys, 'base_prefix', sys.prefix):
        candidates.append(sys.executable)  # 已在某个虚拟环境中
    venv = _venv_python()
    if venv:
        candidates.append(venv)
    candidates.append(sys.executable)

    for py in candidates:
        try:
            subprocess.run([py, '-m', 'PyInstaller', '--version'],
                           capture_output=True, check=True)
            return py
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

    print("错误：未找到 PyInstaller。请先安装构建依赖：")
    print("  .venv\\Scripts\\python -m pip install -r requirements-dev.txt")
    sys.exit(1)


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
        print("警告：aria2c.exe 不存在，打包后的程序将无法启动下载引擎")

    # 清理
    clean_build()

    # 安装依赖（含 PyInstaller 等构建依赖）
    print("安装依赖...")
    subprocess.run([build_python(), '-m', 'pip', 'install', '-r', 'requirements-dev.txt'], check=True)

    # 使用 PyInstaller 构建
    print("构建可执行文件...")
    subprocess.run([
        build_python(), '-m', 'PyInstaller',
        'aria2c-ui.spec',
        '--clean',
        '--noconfirm'
    ], check=True)
    
    # 验证关键资源（aria2c.exe 已由 spec datas 打包进 _internal/aria2c）
    dist_dir = Path('dist/Aria2cUI')
    if dist_dir.exists():
        exe_file = dist_dir / 'Aria2cUI.exe'
        engine = dist_dir / '_internal' / 'aria2c' / 'aria2c.exe'
        print(f"\n构建完成！输出目录: {dist_dir.absolute()}")
        print(f"可执行文件: {exe_file} ({exe_file.stat().st_size / 1 / 1024 / 1024:.1f} MB)")
        print(f"下载引擎: {'OK' if engine.exists() else '缺失！'}")
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
    # 注意：--paths . 必须保留，src.backend.* 包需要从项目根解析
    cmd = [
        build_python(), '-m', 'PyInstaller',
        '--onefile',
        '--windowed',
        '--name', 'Aria2cUI',
        '--paths', '.',
        '--add-data', 'src/frontend;src/frontend',
        '--add-data', 'aria2c/aria2c.exe;aria2c',
        '--hidden-import', 'pydantic',
        '--hidden-import', 'requests',
        '--hidden-import', 'psutil',
        '--hidden-import', 'webview',
        '--hidden-import', 'src.backend.models',
        '--hidden-import', 'src.backend.config',
        '--hidden-import', 'src.backend.history',
        '--hidden-import', 'src.backend.aria2_client',
        '--hidden-import', 'src.backend.aria2_process',
    ]

    icon = Path('assets/icon.ico')
    if icon.exists():
        cmd += ['--icon', str(icon)]

    cmd.append('src/backend/main.py')

    subprocess.run(cmd, check=True)

    out = Path('dist/Aria2cUI.exe')
    if out.exists():
        print("\n单文件版本构建完成！")
        print(f"输出: {out.absolute()} ({out.stat().st_size / 1 / 1024 / 1024:.1f} MB)")
    else:
        print("构建失败，未找到输出文件")


def run_dev():
    """开发模式运行（直接启动 pywebview 窗口）"""
    print("启动开发模式...")
    os.environ['PYTHONPATH'] = str(_ROOT)
    subprocess.run([_venv_python() or sys.executable, 'src/backend/main.py'])


def build_installer():
    """构建 Windows 安装包（使用 Inno Setup）"""
    import subprocess
    from pathlib import Path
    
    print("开始构建 Windows 安装包...")
    
    # 首先构建可执行文件
    build()
    
    # 检查 Inno Setup 是否安装
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
    ]
    
    iscc = None
    for path in iscc_paths:
        if Path(path).exists():
            iscc = path
            break
    
    if not iscc:
        print("错误：未找到 Inno Setup！")
        print("请下载并安装 Inno Setup：")
        print("https://jrsoftware.org/isdl.php")
        print("")
        print("安装完成后重新运行此命令。")
        return False
    
    # 创建 assets 目录（如果不存在）
    assets_dir = Path('assets')
    assets_dir.mkdir(exist_ok=True)
    
    # 检查图标文件
    icon_file = assets_dir / 'icon.ico'
    if not icon_file.exists():
        print("警告：未找到图标文件 assets/icon.ico")
        print("将使用默认图标...")
        # 创建一个简单的默认图标
        create_default_icon()
    
    # 运行 Inno Setup 编译器
    print(f"使用 Inno Setup: {iscc}")
    print("编译安装包...")
    
    try:
        # 使用 utf-8 编码并忽略错误，避免中文 Windows 编码问题
        result = subprocess.run(
            [iscc, 'setup.iss'], 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='ignore'
        )
        if result.returncode == 0:
            print("\n" + "="*50)
            print("安装包构建成功！")
            print("="*50)
            print(f"输出文件: {Path('installer/Aria2cUI-1.0.0-Setup.exe').absolute()}")
            return True
        else:
            print("编译失败！")
            if result.stderr:
                print("错误输出:", result.stderr)
            return False
    except Exception as e:
        print(f"编译出错: {e}")
        return False


def create_default_icon():
    """图标生成统一走 create_icon.py（支持 assets/icon-source.png 高清源图）"""
    subprocess.run([build_python(), 'create_icon.py'], check=False)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Aria2c UI 构建工具')
    parser.add_argument('command', choices=['build', 'onefile', 'clean', 'dev', 'installer'], 
                       help='构建命令: build(文件夹模式), onefile(单文件), clean(清理), dev(开发运行), installer(安装包)')
    
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
    elif args.command == 'installer':
        build_installer()
