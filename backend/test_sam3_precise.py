"""
SAM3 精确边界分割测试
使用 Hugging Face Transformers 本地运行 SAM3 模型
生成精确的物体边界 mask
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
import numpy as np
from PIL import Image
import colorsys

# 检查CUDA可用性
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"使用设备: {device}")

def generate_distinct_colors(n: int, alpha: int = 150):
    """生成N个视觉上易区分的RGBA颜色"""
    colors = []
    for i in range(n):
        hue = i / n
        saturation = 0.8
        value = 0.9
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        colors.append((int(r * 255), int(g * 255), int(b * 255), alpha))
    return colors


def create_colored_mask_overlay(image: Image.Image, masks: list, scores: list = None) -> Image.Image:
    """
    创建带有不同颜色精确mask覆盖的图像
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    
    result = image.copy()
    n_masks = len(masks)
    colors = generate_distinct_colors(n_masks, alpha=140)
    
    # 按分数排序，高分的mask后绘制（在上层）
    if scores is not None:
        sorted_indices = np.argsort(scores)
    else:
        sorted_indices = range(n_masks)
    
    for idx in sorted_indices:
        mask = masks[idx]
        color = colors[idx]
        
        # 确保mask是numpy数组
        if torch.is_tensor(mask):
            mask = mask.cpu().numpy()
        
        mask_array = np.array(mask, dtype=np.uint8)
        if mask_array.max() <= 1:
            mask_array = mask_array * 255
        
        # 创建RGBA overlay - 精确边界
        height, width = mask_array.shape[:2]
        overlay = np.zeros((height, width, 4), dtype=np.uint8)
        overlay[:, :, 0] = color[0]
        overlay[:, :, 1] = color[1]
        overlay[:, :, 2] = color[2]
        overlay[:, :, 3] = (mask_array > 0).astype(np.uint8) * color[3]
        
        overlay_image = Image.fromarray(overlay, mode="RGBA")
        result = Image.alpha_composite(result, overlay_image)
    
    return result, colors


def run_sam3_auto_mask(image_path: str, output_path: str):
    """
    使用SAM3自动mask生成器分割图片中的所有物体
    """
    from transformers import pipeline
    
    print("加载SAM3模型...")
    print("(首次运行需要下载模型，约2GB)")
    
    # 使用mask-generation pipeline
    generator = pipeline(
        "mask-generation",
        model="facebook/sam2.1-hiera-large",  # SAM2.1作为备选，SAM3可能需要更新transformers
        device=0 if device == "cuda" else -1
    )
    
    print(f"加载图片: {image_path}")
    image = Image.open(image_path).convert("RGB")
    
    # 调整图片大小以加快处理速度
    max_size = 1024
    ratio = min(max_size / image.width, max_size / image.height)
    if ratio < 1:
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image_resized = image.resize(new_size, Image.LANCZOS)
        print(f"调整尺寸: {image.size} -> {new_size}")
    else:
        image_resized = image
    
    print("运行SAM自动分割（细粒度模式）...")
    # 增加points_per_batch以获得更多细节分割
    # 降低pred_iou_thresh和stability_score_thresh以检测更多小物体
    outputs = generator(
        image_resized, 
        points_per_batch=128,  # 更多采样点
        pred_iou_thresh=0.7,   # 降低阈值检测更多物体
        stability_score_thresh=0.8,  # 降低稳定性阈值
    )
    
    masks = outputs["masks"]
    scores = outputs.get("scores", [1.0] * len(masks))
    
    print(f"检测到 {len(masks)} 个物体区域")
    
    # 过滤mask - 保留更多小物体
    filtered_masks = []
    filtered_scores = []
    filtered_labels = []
    total_pixels = image_resized.width * image_resized.height
    
    for mask, score in zip(masks, scores):
        mask_array = np.array(mask)
        mask_pixels = mask_array.sum()
        ratio = mask_pixels / total_pixels
        
        # 保留占比在0.1%到80%之间的mask（更宽松，包括小物件和地面）
        if 0.001 < ratio < 0.8:
            filtered_masks.append(mask_array)
            filtered_scores.append(score)
            # 根据大小和位置推断物体类型
            if ratio > 0.3:
                filtered_labels.append("大区域(墙/地面)")
            elif ratio > 0.1:
                filtered_labels.append("中型物体(沙发/柜)")
            elif ratio > 0.02:
                filtered_labels.append("小型物体(茶几/椅)")
            else:
                filtered_labels.append("装饰物(花瓶/灯)")
    
    print(f"过滤后保留 {len(filtered_masks)} 个有效物体")
    
    # 统计各类物体数量
    from collections import Counter
    label_counts = Counter(filtered_labels)
    print("\n物体分类统计:")
    for label, count in label_counts.items():
        print(f"  - {label}: {count}个")
    
    # 生成彩色mask覆盖图
    result_image, colors = create_colored_mask_overlay(image_resized, filtered_masks, filtered_scores)
    
    # 保存结果
    result_image.save(output_path)
    print(f"\n✅ 细粒度分割完成！")
    print(f"结果保存至: {output_path}")
    
    # 打印详细信息
    print(f"\n共分割出 {len(filtered_masks)} 个物体区域:")
    for i, (label, color, score) in enumerate(zip(filtered_labels, colors, filtered_scores)):
        print(f"  {i+1:2d}. {label} - RGB({color[0]:3d},{color[1]:3d},{color[2]:3d}) 置信度:{score:.2f}")
    
    return filtered_masks, filtered_scores, filtered_labels


def run_sam3_text_prompt(image_path: str, output_path: str, prompts: list):
    """
    使用SAM3文本提示分割特定物体
    """
    from transformers import Sam3Processor, Sam3Model
    
    print("加载SAM3模型...")
    model = Sam3Model.from_pretrained("facebook/sam3").to(device)
    processor = Sam3Processor.from_pretrained("facebook/sam3")
    
    print(f"加载图片: {image_path}")
    image = Image.open(image_path).convert("RGB")
    
    # 调整图片大小
    max_size = 1024
    ratio = min(max_size / image.width, max_size / image.height)
    if ratio < 1:
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image = image.resize(new_size, Image.LANCZOS)
    
    all_masks = []
    all_labels = []
    
    for prompt in prompts:
        print(f"识别: {prompt}...")
        inputs = processor(images=image, text=prompt, return_tensors="pt").to(device)
        
        with torch.no_grad():
            outputs = model(**inputs)
        
        results = processor.post_process_instance_segmentation(
            outputs,
            threshold=0.5,
            mask_threshold=0.5,
            target_sizes=inputs.get("original_sizes").tolist()
        )[0]
        
        if len(results['masks']) > 0:
            for mask in results['masks']:
                all_masks.append(mask.cpu().numpy())
                all_labels.append(prompt)
            print(f"  ✓ 找到 {len(results['masks'])} 个")
        else:
            print(f"  ✗ 未找到")
    
    if all_masks:
        result_image, colors = create_colored_mask_overlay(image, all_masks)
        result_image.save(output_path)
        
        print(f"\n✅ 分割完成！共 {len(all_masks)} 个物体")
        print(f"结果保存至: {output_path}")
        print("\n颜色图例:")
        for i, (label, color) in enumerate(zip(all_labels, colors)):
            print(f"  {i+1}. {label}: RGB({color[0]}, {color[1]}, {color[2]})")
    
    return all_masks, all_labels


if __name__ == "__main__":
    input_image = r"e:\vibe coding projects\20250109-AI 装修-agentic版\output\微信图片_20260119173121.png"
    output_image = r"e:\vibe coding projects\20250109-AI 装修-agentic版\output\sam3_precise_result.png"
    
    try:
        # 尝试自动分割所有物体
        run_sam3_auto_mask(input_image, output_image)
    except Exception as e:
        print(f"\n自动分割失败: {e}")
        print("\n尝试使用文本提示分割...")
        
        prompts = ["sofa", "table", "TV", "carpet", "window", "curtain", "lamp", "door"]
        try:
            run_sam3_text_prompt(input_image, output_image, prompts)
        except Exception as e2:
            print(f"\n文本提示分割也失败: {e2}")
            print("\n请确保:")
            print("1. 已安装最新版 transformers: pip install -U transformers")
            print("2. 有足够GPU显存(建议8GB+)或使用CPU(较慢)")
            print("3. 网络可访问Hugging Face下载模型")
