"""
SAM3 分割测试脚本
自动分割图片中的所有物体，并用不同RGBA颜色显示每个mask
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import asyncio
import numpy as np
from PIL import Image
import colorsys


# 生成N个视觉上易区分的颜色
def generate_distinct_colors(n: int, alpha: int = 150):
    """生成N个不同的RGBA颜色"""
    colors = []
    for i in range(n):
        hue = i / n
        saturation = 0.7 + (i % 3) * 0.1
        value = 0.9
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        colors.append((int(r * 255), int(g * 255), int(b * 255), alpha))
    return colors


def create_colored_mask_overlay(image: Image.Image, masks: list, colors: list) -> Image.Image:
    """
    创建带有不同颜色mask覆盖的图像
    
    Args:
        image: 原始图像
        masks: mask列表，每个mask是2D numpy数组
        colors: RGBA颜色列表
        
    Returns:
        带有彩色mask覆盖的图像
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    
    result = image.copy()
    
    for i, mask in enumerate(masks):
        color = colors[i % len(colors)]
        
        # 创建彩色mask层
        mask_array = np.array(mask, dtype=np.uint8)
        if mask_array.max() <= 1:
            mask_array = mask_array * 255
        
        # 创建RGBA overlay
        overlay = np.zeros((mask_array.shape[0], mask_array.shape[1], 4), dtype=np.uint8)
        overlay[:, :, 0] = color[0]  # R
        overlay[:, :, 1] = color[1]  # G
        overlay[:, :, 2] = color[2]  # B
        overlay[:, :, 3] = (mask_array > 0).astype(np.uint8) * color[3]  # A
        
        overlay_image = Image.fromarray(overlay, mode="RGBA")
        result = Image.alpha_composite(result, overlay_image)
    
    return result


def create_mock_masks_by_grid(image: Image.Image, grid_size: int = 4) -> list:
    """
    创建模拟的网格mask用于演示（无API时使用）
    """
    width, height = image.size
    masks = []
    
    cell_w = width // grid_size
    cell_h = height // grid_size
    
    for i in range(grid_size):
        for j in range(grid_size):
            mask = np.zeros((height, width), dtype=np.uint8)
            x1, y1 = j * cell_w, i * cell_h
            x2, y2 = (j + 1) * cell_w, (i + 1) * cell_h
            mask[y1:y2, x1:x2] = 255
            masks.append(mask)
    
    return masks


async def test_sam3_with_api(image_path: str, output_path: str):
    """使用SAM3 API进行真实分割测试"""
    from app.services.sam_service import sam3_service
    
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    
    print(f"图片尺寸: {width} x {height}")
    print("开始SAM3分割测试...")
    
    # 定义要识别的物体列表
    objects_to_detect = [
        "sofa",
        "coffee table", 
        "TV",
        "curtain",
        "rug",
        "lamp",
        "door",
        "window"
    ]
    
    masks = []
    labels = []
    
    for obj in objects_to_detect:
        print(f"  正在识别: {obj}...")
        try:
            result = await sam3_service.segment_by_text(image, obj, threshold=0.3)
            if result.get("masks"):
                for m in result["masks"]:
                    masks.append(np.array(m))
                    labels.append(obj)
                print(f"    ✓ 找到 {len(result['masks'])} 个 {obj}")
            else:
                print(f"    ✗ 未找到 {obj}")
        except Exception as e:
            print(f"    ✗ 识别失败: {e}")
    
    if masks:
        colors = generate_distinct_colors(len(masks))
        result_image = create_colored_mask_overlay(image, masks, colors)
        result_image.save(output_path)
        print(f"\n✅ 分割完成！共识别 {len(masks)} 个物体")
        print(f"结果保存至: {output_path}")
        
        # 打印颜色图例
        print("\n颜色图例:")
        for i, (label, color) in enumerate(zip(labels, colors)):
            print(f"  {i+1}. {label}: RGB({color[0]}, {color[1]}, {color[2]})")
    else:
        print("\n⚠️ 未识别到任何物体")
    
    return masks, labels


def test_sam3_demo(image_path: str, output_path: str):
    """
    演示模式：使用预定义区域模拟mask效果
    用于在没有API Token时展示效果
    """
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    
    print(f"图片尺寸: {width} x {height}")
    print("使用演示模式（预定义区域）...")
    
    # 根据图片内容手动定义区域（基于5504x3072尺寸的客厅布局）
    # 坐标按比例缩放到实际图片尺寸
    scale_x = width / 1024
    scale_y = height / 600
    
    def scale_box(box):
        return (int(box[0] * scale_x), int(box[1] * scale_y), 
                int(box[2] * scale_x), int(box[3] * scale_y))
    
    regions = [
        {"name": "沙发", "box": scale_box((180, 280, 480, 420)), "color": (255, 80, 80, 160)},
        {"name": "茶几", "box": scale_box((420, 350, 580, 430)), "color": (80, 255, 80, 160)},
        {"name": "电视", "box": scale_box((720, 180, 880, 340)), "color": (80, 80, 255, 160)},
        {"name": "电视柜", "box": scale_box((680, 340, 940, 420)), "color": (255, 255, 80, 160)},
        {"name": "地毯", "box": scale_box((180, 400, 780, 520)), "color": (255, 80, 255, 160)},
        {"name": "落地窗", "box": scale_box((360, 50, 680, 420)), "color": (80, 255, 255, 160)},
        {"name": "窗帘", "box": scale_box((280, 50, 380, 400)), "color": (220, 180, 120, 160)},
        {"name": "左门", "box": scale_box((0, 100, 100, 480)), "color": (150, 220, 150, 160)},
        {"name": "右门", "box": scale_box((940, 100, 1024, 480)), "color": (150, 150, 220, 160)},
        {"name": "挂画", "box": scale_box((150, 180, 260, 310)), "color": (220, 100, 220, 160)},
        {"name": "边几", "box": scale_box((100, 340, 180, 420)), "color": (255, 200, 100, 160)},
        {"name": "台灯", "box": scale_box((880, 320, 940, 400)), "color": (100, 200, 255, 160)},
    ]
    
    # 创建masks
    masks = []
    colors = []
    labels = []
    
    for region in regions:
        mask = np.zeros((height, width), dtype=np.uint8)
        x1, y1, x2, y2 = region["box"]
        # 确保坐标在图片范围内
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)
        mask[y1:y2, x1:x2] = 255
        masks.append(mask)
        colors.append(region["color"])
        labels.append(region["name"])
    
    # 创建结果图像
    result = image.convert("RGBA")
    
    for mask, color in zip(masks, colors):
        overlay = np.zeros((height, width, 4), dtype=np.uint8)
        overlay[:, :, 0] = color[0]
        overlay[:, :, 1] = color[1]
        overlay[:, :, 2] = color[2]
        overlay[:, :, 3] = (mask > 0).astype(np.uint8) * color[3]
        
        overlay_image = Image.fromarray(overlay, mode="RGBA")
        result = Image.alpha_composite(result, overlay_image)
    
    result.save(output_path)
    
    print(f"\n✅ 演示分割完成！共 {len(masks)} 个区域")
    print(f"结果保存至: {output_path}")
    print("\n颜色图例:")
    for i, (label, color) in enumerate(zip(labels, colors)):
        print(f"  {i+1:2d}. {label}: RGB({color[0]:3d}, {color[1]:3d}, {color[2]:3d})")
    
    return masks, labels


if __name__ == "__main__":
    # 测试图片路径
    input_image = r"e:\vibe coding projects\20250109-AI 装修-agentic版\output\微信图片_20260119173121.png"
    output_image = r"e:\vibe coding projects\20250109-AI 装修-agentic版\output\sam3_segmented_result.png"
    
    # 检查HF_TOKEN
    hf_token = os.getenv("HF_TOKEN")
    
    if hf_token and hf_token != "your_hf_token_here":
        print("检测到HF_TOKEN，使用SAM3 API模式...")
        asyncio.run(test_sam3_with_api(input_image, output_image))
    else:
        print("未检测到HF_TOKEN，使用演示模式...")
        print("如需使用真实SAM3分割，请在.env中配置HF_TOKEN\n")
        test_sam3_demo(input_image, output_image)
