# -*- coding: utf-8 -*-
"""
图片压缩脚本：将项目中的大图片转为 WebP 格式，大幅减小文件体积。
用法: python scripts/compress_images.py
"""

import os
import sys
from pathlib import Path
from PIL import Image

# 项目根目录
ROOT = Path(__file__).parent.parent
PUBLIC = ROOT / "frontend" / "public"

# 压缩配置: (目录, 最大宽度, 最大高度, WebP质量)
COMPRESS_RULES = [
    # Logo: 导航栏只需要 ~112px 高
    (PUBLIC / "assets" / "logo", 9999, 112, 80),
    # Hero 图片: 最大宽度 1200px
    (PUBLIC / "assets" / "hero section", 1200, 900, 75),
    # Gallery: 最大宽度 600px
    (PUBLIC / "assets" / "gallery", 600, 800, 70),
    # Video poster: 最大宽度 800px
    (PUBLIC / "assets" / "video", 800, 600, 75),
    # Style 风格图: 缩略图只需 200px 宽
    (PUBLIC / "styles", 200, 200, 70),
]


def compress_image(filepath: Path, max_w: int, max_h: int, quality: int) -> tuple:
    """压缩单张图片，返回 (原大小, 新大小)"""
    original_size = filepath.stat().st_size

    img = Image.open(filepath)

    # 如果有透明通道，保留 RGBA；否则转 RGB
    if img.mode == "RGBA":
        # 检查是否真的用到了透明度
        bg = Image.new("RGBA", img.size, (0, 0, 0, 0))
        if img.getpalette() is None:
            mode = "RGBA"
        else:
            img = img.convert("RGBA")
            mode = "RGBA"
    else:
        img = img.convert("RGB")
        mode = "RGB"

    # 缩放
    img.thumbnail((max_w, max_h), Image.LANCZOS)

    # 输出路径：同目录，扩展名改为 .webp
    output_path = filepath.with_suffix(".webp")

    # 保存
    save_kwargs = {"format": "WEBP", "quality": quality}
    if mode == "RGBA":
        # WebP 支持透明，不需要特殊处理
        pass

    img.save(str(output_path), **save_kwargs)
    img.close()

    new_size = output_path.stat().st_size

    # 删除原始文件（如果扩展名不同）
    if output_path != filepath:
        filepath.unlink()

    return original_size, new_size


def main():
    total_original = 0
    total_compressed = 0
    file_count = 0

    print("=" * 60)
    print("  图片压缩工具 - PNG/JPG → WebP")
    print("=" * 60)

    for directory, max_w, max_h, quality in COMPRESS_RULES:
        if not directory.exists():
            print(f"\n⏭ 跳过（目录不存在）: {directory}")
            continue

        print(f"\n📁 {directory.relative_to(ROOT)}")
        print(f"   参数: {max_w}×{max_h}, quality={quality}")

        # 只处理 png 和 jpg 文件
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            for filepath in sorted(directory.rglob(ext)):
                # 跳过已经是 webp 的文件和非图片文件
                if filepath.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                    continue
                # 跳过 README 等非图片
                if filepath.name.startswith("README"):
                    continue

                try:
                    orig, comp = compress_image(filepath, max_w, max_h, quality)
                    total_original += orig
                    total_compressed += comp
                    file_count += 1

                    ratio = (1 - comp / orig) * 100 if orig > 0 else 0
                    print(f"   ✅ {filepath.name}")
                    print(f"      {orig/1024:.0f}KB → {comp/1024:.0f}KB (↓{ratio:.1f}%)")
                except Exception as e:
                    print(f"   ❌ {filepath.name}: {e}")

    print("\n" + "=" * 60)
    print(f"  压缩完成！共处理 {file_count} 个文件")
    print(f"  总计: {total_original/1024/1024:.1f}MB → {total_compressed/1024/1024:.1f}MB")
    ratio = (1 - total_compressed / total_original) * 100 if total_original > 0 else 0
    print(f"  缩减: {ratio:.1f}%")
    print("=" * 60)


if __name__ == "__main__":
    main()
