"""
SAM3 分割服务
使用 Meta Segment Anything Model 3 进行图像分割
支持点击选择、文本提示等多种分割方式
"""

import os
import io
import base64
import httpx
from typing import List, Dict, Optional, Tuple
from PIL import Image
import numpy as np


class SAM3Service:
    """
    SAM3 分割服务
    通过 Hugging Face Inference API 调用 SAM3 模型
    """
    
    def __init__(self):
        self.hf_token = os.getenv("HF_TOKEN")
        self.model_id = "facebook/sam2-hiera-large"
        self.api_url = f"https://router.huggingface.co/hf-inference/models/{self.model_id}"
        
    def _image_to_base64(self, image: Image.Image) -> str:
        """将PIL Image转换为base64字符串"""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    def _base64_to_image(self, b64_string: str) -> Image.Image:
        """将base64字符串转换为PIL Image"""
        image_data = base64.b64decode(b64_string)
        return Image.open(io.BytesIO(image_data))
    
    async def segment_by_point(
        self, 
        image: Image.Image, 
        point: Tuple[int, int],
        label: int = 1
    ) -> Dict:
        """
        通过点击坐标分割图像
        
        Args:
            image: PIL Image对象
            point: 点击坐标 (x, y)
            label: 1=正向选择, 0=负向排除
            
        Returns:
            包含mask和边界框的字典
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {}
            if self.hf_token:
                headers["Authorization"] = f"Bearer {self.hf_token}"
            
            image_b64 = self._image_to_base64(image)
            
            payload = {
                "inputs": {
                    "image": image_b64,
                    "input_points": [[[point[0], point[1]]]],
                    "input_labels": [[label]]
                }
            }
            
            response = await client.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"SAM3 API error: {response.status_code} - {response.text}")
    
    async def segment_by_text(
        self, 
        image: Image.Image, 
        text_prompt: str,
        threshold: float = 0.5
    ) -> Dict:
        """
        通过文本提示分割图像
        
        Args:
            image: PIL Image对象
            text_prompt: 文本描述 (如 "sofa", "chair", "lamp")
            threshold: 置信度阈值
            
        Returns:
            包含masks和boxes的字典
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {}
            if self.hf_token:
                headers["Authorization"] = f"Bearer {self.hf_token}"
            
            image_b64 = self._image_to_base64(image)
            
            payload = {
                "inputs": {
                    "image": image_b64,
                    "text": text_prompt
                },
                "parameters": {
                    "threshold": threshold
                }
            }
            
            response = await client.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"SAM3 API error: {response.status_code} - {response.text}")
    
    async def segment_by_box(
        self, 
        image: Image.Image, 
        box: Tuple[int, int, int, int],
        label: int = 1
    ) -> Dict:
        """
        通过边界框分割图像
        
        Args:
            image: PIL Image对象
            box: 边界框 (x1, y1, x2, y2)
            label: 1=正向选择, 0=负向排除
            
        Returns:
            包含mask的字典
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            headers = {}
            if self.hf_token:
                headers["Authorization"] = f"Bearer {self.hf_token}"
            
            image_b64 = self._image_to_base64(image)
            
            payload = {
                "inputs": {
                    "image": image_b64,
                    "input_boxes": [[list(box)]],
                    "input_boxes_labels": [[label]]
                }
            }
            
            response = await client.post(
                self.api_url,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"SAM3 API error: {response.status_code} - {response.text}")


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
