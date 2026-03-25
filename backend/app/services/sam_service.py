"""
SAM3 分割服务
使用 Segmind API 调用 SAM3 模型进行图像分割
支持点坐标、文本提示、边界框三种分割方式
"""

import os
import io
import base64
import httpx
import asyncio
from typing import List, Dict, Optional, Tuple
from PIL import Image
import numpy as np


# 中英文家具翻译映射
FURNITURE_TRANSLATIONS = {
    "沙发": "sofa", "美式沙发": "american sofa", "现代沙发": "modern sofa",
    "椅子": "chair", "单人椅": "armchair", "休闲椅": "lounge chair",
    "桌子": "table", "茶几": "coffee table", "餐桌": "dining table", "书桌": "desk",
    "灯": "lamp", "台灯": "table lamp", "落地灯": "floor lamp", "吸顶灯": "ceiling lamp",
    "绿植": "plant", "盆栽": "potted plant", "花": "flower",
    "床": "bed", "地毯": "rug", "窗帘": "curtain", "画": "painting",
    "柜子": "cabinet", "书柜": "bookshelf", "电视柜": "TV stand",
    "墙": "wall", "地板": "floor", "窗户": "window", "门": "door",
}

def translate_furniture(text: str) -> str:
    """提取并翻译家具关键词"""
    text_lower = text.lower()
    # 直接匹配中文关键词
    for cn, en in FURNITURE_TRANSLATIONS.items():
        if cn in text:
            return en
    # 如果是英文，直接返回
    if text.isascii():
        return text_lower
    # 默认返回furniture
    return "furniture"


class SAM3Service:
    """
    SAM3 分割服务
    通过 Segmind API 调用 SAM3 模型
    """
    
    def __init__(self):
        self.api_key = os.getenv("SEGMIND_API_KEY", "SG_63bab65c13127931")
        self.api_url = "https://api.segmind.com/v1/sam3-image"
        
    def _image_to_base64(self, image: Image.Image) -> str:
        """将PIL Image转换为base64字符串"""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    def _base64_to_image(self, b64_string: str) -> Image.Image:
        """将base64字符串转换为PIL Image"""
        image_data = base64.b64decode(b64_string)
        return Image.open(io.BytesIO(image_data))
    
    async def _call_api(self, payload: Dict) -> bytes:
        """
        调用Segmind SAM3 API
        
        Returns:
            二进制PNG图片数据
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json"
            }
            
            response = await client.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                return response.content
            else:
                raise Exception(f"Segmind API error: {response.status_code} - {response.text}")
    
    async def segment_by_text(
        self, 
        image_url: str, 
        text_prompt: str,
        threshold: float = 0.5
    ) -> Dict:
        """
        通过文本提示分割图像
        
        Args:
            image_url: 公网可访问的图片URL
            text_prompt: 文本描述 (支持中文，会自动翻译)
            threshold: 置信度阈值
            
        Returns:
            包含分割结果的字典
        """
        # 翻译中文关键词为英文
        en_prompt = translate_furniture(text_prompt)
        
        payload = {
            "image": image_url,
            "text_prompt": en_prompt,
            "return_preview": False,
            "return_overlay": True,  # 使用overlay效果
            "return_masks": False,
            "threshold": threshold
        }
        
        image_data = await self._call_api(payload)
        
        # 将二进制数据转为base64
        overlay_base64 = base64.b64encode(image_data).decode("utf-8")
        
        return {
            "output": {
                "image_data": image_data,
                "overlay_base64": overlay_base64,
                "translated_prompt": en_prompt
            }
        }
    
    async def segment_by_point(
        self, 
        image_url: str, 
        point: Tuple[int, int],
        label: int = 1
    ) -> Dict:
        """
        通过点击坐标分割图像
        
        Args:
            image_url: 公网可访问的图片URL
            point: (x, y) 点击坐标
            label: 1=选择该区域, 0=排除该区域
        
        优化: 降低pred_iou_thresh让模型更倾向于选择整体物体而非局部纹理
        """
        payload = {
            "image": image_url,
            "points_input": f"[[{point[0]}, {point[1]}]]",
            "point_labels_input": f"[{label}]",
            "return_preview": False,
            "return_overlay": True,
            "return_masks": False,
            "pred_iou_thresh": 0.5,  # 降低IoU阈值，更倾向于选择整体
            "threshold": 0.3  # 降低检测阈值
        }
        
        overlay_data = await self._call_api(payload)
        overlay_base64 = base64.b64encode(overlay_data).decode("utf-8")
        
        return {
            "output": {
                "overlay_base64": overlay_base64,
                "mask_base64": overlay_base64
            }
        }
    
    async def segment_by_box(
        self, 
        image_url: str, 
        box: Tuple[int, int, int, int]
    ) -> Dict:
        """
        通过边界框分割图像 - 只使用框选，返回黑白mask
        
        Args:
            image_url: 公网可访问的图片URL
            box: (x1, y1, x2, y2) 边界框坐标
        """
        x1, y1, x2, y2 = box
        boxes_input = f"[[{x1}, {y1}, {x2}, {y2}]]"
        
        # 只使用框选，不添加中心点，避免选中同类物体
        # SAM3只支持return_overlay，我们获取overlay后在后端提取mask
        payload = {
            "image": image_url,
            "boxes_input": boxes_input,
            "return_preview": False,
            "return_overlay": True,
            "return_masks": False
        }
        
        overlay_data = await self._call_api(payload)
        overlay_base64 = base64.b64encode(overlay_data).decode("utf-8")
        
        # 从overlay提取黑白mask - 在路由层处理
        return {
            "output": {
                "overlay_base64": overlay_base64
            }
        }


def create_rgba_mask(
    image: Image.Image, 
    mask: np.ndarray,
    alpha: int = 128
) -> Image.Image:
    """
    创建RGBA格式的mask覆盖图
    
    Args:
        image: 原始图像
        mask: 二值mask数组
        alpha: 透明度 (0-255)
        
    Returns:
        RGBA格式的mask图像
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    
    mask_array = np.array(mask, dtype=np.uint8)
    if mask_array.max() == 1:
        mask_array = mask_array * 255
    
    rgba_mask = np.zeros((mask_array.shape[0], mask_array.shape[1], 4), dtype=np.uint8)
    rgba_mask[:, :, 0] = 147  # Purple-ish color
    rgba_mask[:, :, 1] = 51
    rgba_mask[:, :, 2] = 234
    rgba_mask[:, :, 3] = (mask_array > 0).astype(np.uint8) * alpha
    
    mask_image = Image.fromarray(rgba_mask, mode="RGBA")
    
    result = Image.alpha_composite(image, mask_image)
    return result


def extract_masked_region(
    image: Image.Image, 
    mask: np.ndarray
) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    """
    提取mask区域
    
    Args:
        image: 原始图像
        mask: 二值mask数组
        
    Returns:
        (提取的区域图像, 边界框坐标)
    """
    mask_array = np.array(mask, dtype=np.uint8)
    if mask_array.max() == 1:
        mask_array = mask_array * 255
    
    coords = np.where(mask_array > 0)
    if len(coords[0]) == 0:
        return None, None
    
    y_min, y_max = coords[0].min(), coords[0].max()
    x_min, x_max = coords[1].min(), coords[1].max()
    
    bbox = (x_min, y_min, x_max + 1, y_max + 1)
    
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    
    extracted = image.crop(bbox)
    
    mask_crop = mask_array[y_min:y_max+1, x_min:x_max+1]
    alpha = Image.fromarray(mask_crop, mode="L")
    extracted.putalpha(alpha)
    
    return extracted, bbox


sam3_service = SAM3Service()
