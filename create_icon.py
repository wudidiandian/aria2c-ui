#!/usr/bin/env python3
"""生成 Aria2c UI 应用程序图标

用法：
  python create_icon.py [源图片路径]

源图片要求：正方形 PNG，推荐 1024x1024，带透明背景。
未提供源图片时，若存在 assets/icon-source.png 则使用之；
都没有则回退到程序绘制的默认图标。
"""

import sys
from pathlib import Path

# Windows 图标标准尺寸集（从小到大全部内嵌一个 .ico 中）
ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]
SOURCE_MIN = 256  # 源图最小边长


def build_ico(source: "Image.Image", out_path: Path) -> None:
    """从高分辨率源图缩小生成多尺寸 ico（LANCZOS 缩小 = 清晰）"""
    from PIL import Image

    side = min(source.size)
    # 居中裁剪为正方形
    left = (source.width - side) // 2
    top = (source.height - side) // 2
    square = source.crop((left, top, left + side, top + side)).convert("RGBA")
    if side > 1024:
        square = square.resize((1024, 1024), Image.Resampling.LANCZOS)

    icons = [square.resize((s, s), Image.Resampling.LANCZOS) for s in ICON_SIZES]
    icons[-1].save(out_path, format="ICO", sizes=[(s, s) for s in ICON_SIZES])
    print(f"已生成 {out_path}（尺寸: {', '.join(map(str, ICON_SIZES))}）")


def fallback_icon(out_path: Path) -> None:
    """无源图时绘制默认图标（程序化箭头图案）"""
    from PIL import Image, ImageDraw

    base = 1024  # 大画布绘制，再缩小保证小尺寸清晰
    img = Image.new("RGBA", (base, base), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 40
    draw.ellipse([margin, margin, base - margin, base - margin], fill="#10b981")

    cx = cy = base // 2
    w, h = base * 0.10, base * 0.42
    draw.rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2 - w], fill="white")
    draw.polygon(
        [(cx - w, cy + h / 2 - w), (cx + w, cy + h / 2 - w), (cx, cy + h / 2)],
        fill="white",
    )
    build_ico(img, out_path)


def main() -> int:
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("错误：未安装 Pillow，请运行 pip install -r requirements-dev.txt")
        return 1

    src_arg = sys.argv[1] if len(sys.argv) > 1 else "assets/icon-source.png"
    src = Path(src_arg)
    out = Path("assets/icon.ico")

    if src.exists():
        img = Image.open(src)
        if min(img.size) < SOURCE_MIN:
            print(f"警告：源图 {img.size[0]}x{img.size[1]} 分辨率偏低，建议 >= 1024x1024")
        build_ico(img, out)
    else:
        print(f"未找到源图 {src}，使用程序绘制的默认图标")
        fallback_icon(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
