#!/usr/bin/env python3
"""
创建 Aria2c UI 应用程序图标
"""

import sys
from pathlib import Path

def create_icon():
    """创建应用程序图标"""
    try:
        from PIL import Image, ImageDraw
        
        # 创建 assets 目录
        assets_dir = Path('assets')
        assets_dir.mkdir(exist_ok=True)
        
        # 创建 256x256 的图标
        size = 256
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制蓝色圆形背景
        margin = 10
        draw.ellipse([margin, margin, size-margin, size-margin], fill='#3b82f6')
        
        # 绘制白色向下箭头（下载图标）
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
        
        output_path = assets_dir / 'icon.ico'
        icons[0].save(output_path, format='ICO', sizes=[(s, s) for s in icon_sizes])
        print(f"✓ 图标已创建: {output_path.absolute()}")
        return True
        
    except ImportError:
        print("错误：未安装 Pillow 库")
        print("请运行: pip install Pillow")
        print("或: pip install -r requirements.txt")
        return False


if __name__ == '__main__':
    if create_icon():
        sys.exit(0)
    else:
        sys.exit(1)