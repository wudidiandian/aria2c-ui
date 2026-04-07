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
    """创建默认图标（使用 Python 的 PIL 库）"""
    try:
        from PIL import Image, ImageDraw
        
        # 创建 256x256 的图标
        size = 256
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制一个简单的下载图标（蓝色圆形背景 + 白色向下箭头）
        # 背景圆
        margin = 10
        draw.ellipse([margin, margin, size-margin, size-margin], fill='#3b82f6')
        
        # 白色向下箭头
        arrow_width = 80
        arrow_height = 100
        head_height = 40
        center_x = size // 2
        center_y = size // 2
        
        # 箭头杆
        shaft_left = center_x - arrow_width // 4
        shaft_right = center_x + arrow_width // 4
        shaft_top = center_y - arrow_height // 2
        shaft_bottom = center_y + arrow_height // 2 - head_height
        
        draw.rectangle([shaft_left, shaft_top, shaft_right, shaft_bottom], fill='white')
        
        # 箭头头部（三角形）
        head_top = shaft_bottom
        head_bottom = center_y + arrow_height // 2
        draw.polygon([
            (center_x - arrow_width // 2, head_top),
            (center_x + arrow_width // 2, head_top),
            (center_x, head_bottom)
        ], fill='white')
        
        # 保存为 ICO 文件（多种尺寸）
        icon_sizes = [16, 32, 48, 64, 128, 256]
        icons = []
        for icon_size in icon_sizes:
            resized = img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
            icons.append(resized)
        
        icons[0].save('assets/icon.ico', format='ICO', sizes=[(s, s) for s in icon_sizes])
        print("已创建默认图标: assets/icon.ico")
        
    except ImportError:
        print("警告：未安装 PIL 库，无法创建默认图标")
        print("请运行: pip install Pillow")
        # 创建一个空文件作为占位符
        Path('assets/icon.ico').touch()


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
