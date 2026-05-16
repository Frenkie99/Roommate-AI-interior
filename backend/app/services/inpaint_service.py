"""
Inpainting 局部替换服务
使用 API易平台 进行局部图像编辑
"""

import os
import io
import asyncio
import base64
import httpx
from typing import Optional
from PIL import Image
import numpy as np


# #73: 支持的 aspectRatio 候选集（来自 API易 Gemini 文档）
_SUPPORTED_ASPECT_RATIOS = {
    "1:1": 1.0,
    "4:3": 4 / 3,
    "3:4": 3 / 4,
    "16:9": 16 / 9,
    "9:16": 9 / 16,
}


def _aspect_ratio_for_size(width: int, height: int) -> str:
    """
    #73: 根据原图尺寸映射到 API 支持的最接近宽高比。
    避免硬编码 4:3 导致 16:9 / 1:1 输入被压缩变形，违反
    "keep all other parts of the image exactly the same" 的契约。
    """
    if height <= 0 or width <= 0:
        return "1:1"
    ratio = width / height
    return min(_SUPPORTED_ASPECT_RATIOS.items(), key=lambda kv: abs(kv[1] - ratio))[0]


class InpaintService:
    """
    Inpainting 服务
    通过 API易平台 Gemini模型实现局部替换
    """

    # #74: 失败重试次数（对齐 getgoapi_client / llm_client）
    MAX_RETRIES = 3

    def __init__(self):
        # 使用API易平台 - 与基础生图相同的配置
        self.api_key = os.getenv("APIYI_KEY", "sk-5Cd5C9UJNSYfblvr375057376f6746Eb9b3818D27b3e00A3")
        self.api_url = "https://api.apiyi.com"
        self.model = "gemini-3-pro-image-preview"
        # #75: 长生命 AsyncClient，复用 TLS 握手与连接池
        self.client = httpx.AsyncClient(timeout=300.0)

    async def close(self):
        """关闭客户端连接（建议在 FastAPI shutdown hook 中调用）"""
        await self.client.aclose()

    def _image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        """将PIL Image转换为base64字符串"""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _mask_to_base64(self, mask: np.ndarray) -> str:
        """将mask数组转换为base64字符串"""
        mask_array = np.array(mask, dtype=np.uint8)
        if mask_array.max() == 1:
            mask_array = mask_array * 255
        mask_image = Image.fromarray(mask_array, mode="L")
        return self._image_to_base64(mask_image)

    async def inpaint(
        self,
        image: Image.Image,
        mask: np.ndarray,
        prompt: str,
        negative_prompt: Optional[str] = None,
        strength: float = 0.85
    ) -> Image.Image:
        """
        执行局部替换 - 使用API易平台的Gemini模型
        发送原图+mask两张图，mask作为位置参考
        
        Args:
            image: 原始图像
            mask: 要替换区域的mask (白色=替换区域)
            prompt: 描述新内容的提示词
            negative_prompt: 负向提示词（暂未使用）
            strength: 替换强度（暂未使用）
            
        Returns:
            替换后的图像
        """
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        image_b64 = self._image_to_base64(image, "JPEG")
        mask_b64 = self._mask_to_base64(mask)
        
        # 构建编辑提示词 - 发送两张图，第二张是mask指示位置
        edit_prompt = f"""I'm providing two images:
1. First image: An interior design photo
2. Second image: A black and white mask where WHITE areas indicate the region to be edited

Please edit the FIRST image by replacing ONLY the white areas shown in the mask with: {prompt}

Important requirements:
- Keep all other parts of the image exactly the same
- Maintain the same room layout, lighting, and perspective
- The result should be a clean interior design image
- Only modify the area indicated by the white region in the mask

Generate a new interior design image with the masked area replaced."""
        
        # 使用API易的generateContent接口 - 发送原图+mask两张图
        payload = {
            "contents": [{
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": image_b64
                        }
                    },
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": mask_b64
                        }
                    },
                    {
                        "text": edit_prompt
                    }
                ]
            }],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    # #73: 按原图尺寸映射宽高比，不再硬编码 4:3
                    "aspectRatio": _aspect_ratio_for_size(image.size[0], image.size[1]),
                    "imageSize": "1K"
                }
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        api_url = f"{self.api_url}/v1beta/models/{self.model}:generateContent"

        # #74: 5xx / Timeout 重试 3 次，4xx 直接抛错（对齐 getgoapi_client）
        last_error: Optional[str] = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self.client.post(api_url, headers=headers, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    # 解析返回的图片（与基础生图相同格式）
                    candidates = result.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            if "inlineData" in part:
                                img_data = part["inlineData"].get("data", "")
                                if img_data:
                                    return Image.open(io.BytesIO(base64.b64decode(img_data)))
                    raise Exception("API返回中未找到图片")

                if response.status_code >= 500:
                    # 服务端错误，重试
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    if attempt < self.MAX_RETRIES - 1:
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                    raise Exception(f"API错误（已重试 {self.MAX_RETRIES} 次）: {last_error}")

                # 4xx：客户端错误，不重试
                raise Exception(f"API错误: {response.status_code} - {response.text}")

            except httpx.TimeoutException as e:
                last_error = f"请求超时: {e}"
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                raise Exception(f"API请求超时（已重试 {self.MAX_RETRIES} 次）: {last_error}")

        # 理论上不应到达此处（循环内总会 return 或 raise），保底兜底
        raise Exception(f"API请求失败: {last_error}")
    
    async def replace_furniture(
        self,
        image: Image.Image,
        mask: np.ndarray,
        furniture_type: str,
        style: str = "modern"
    ) -> Image.Image:
        """
        替换家具
        
        Args:
            image: 原始图像
            mask: 家具区域的mask
            furniture_type: 家具类型 (sofa, chair, table, lamp等)
            style: 风格 (modern, scandinavian, chinese等)
            
        Returns:
            替换后的图像
        """
        style_prompts = {
            "modern": "modern minimalist style, clean lines, elegant",
            "scandinavian": "scandinavian style, natural wood, light colors",
            "chinese": "chinese traditional style, carved wood, oriental",
            "light_luxury": "luxury style, premium materials, sophisticated",
            "industrial": "industrial style, metal and wood, rustic"
        }
        
        style_desc = style_prompts.get(style, style_prompts["modern"])
        
        prompt = f"high quality {furniture_type}, {style_desc}, interior design, professional photo, 8k"
        negative_prompt = "blurry, low quality, distorted, cartoon, anime, sketch"
        
        return await self.inpaint(image, mask, prompt, negative_prompt)
    
    async def replace_decoration(
        self,
        image: Image.Image,
        mask: np.ndarray,
        decoration_type: str,
        description: Optional[str] = None
    ) -> Image.Image:
        """
        替换装饰物
        
        Args:
            image: 原始图像
            mask: 装饰物区域的mask
            decoration_type: 装饰物类型 (painting, plant, vase, curtain等)
            description: 额外描述
            
        Returns:
            替换后的图像
        """
        decoration_prompts = {
            "painting": "beautiful framed artwork, oil painting, gallery quality",
            "plant": "lush green indoor plant, potted plant, natural",
            "vase": "elegant decorative vase, ceramic, artistic",
            "curtain": "luxurious curtains, draped fabric, elegant",
            "rug": "beautiful area rug, patterned carpet, cozy",
            "lamp": "designer lamp, ambient lighting, stylish"
        }
        
        base_prompt = decoration_prompts.get(decoration_type, f"beautiful {decoration_type}")
        
        if description:
            prompt = f"{base_prompt}, {description}, interior design, high quality photo"
        else:
            prompt = f"{base_prompt}, interior design, high quality photo"
        
        negative_prompt = "blurry, low quality, distorted, out of place"
        
        return await self.inpaint(image, mask, prompt, negative_prompt)


inpaint_service = InpaintService()
