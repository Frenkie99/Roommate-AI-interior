"""
Inpainting 局部替换服务
使用 Stable Diffusion Inpainting 模型进行局部图像替换
"""

import os
import io
import base64
import httpx
from typing import Optional
from PIL import Image
import numpy as np


class InpaintService:
    """
    Inpainting 服务
    通过 Grsai API 或其他 Inpainting API 实现局部替换
    """
    
    def __init__(self):
        self.api_key = os.getenv("GRSAI_API_KEY")
        self.api_url = os.getenv("GRSAI_API_URL", "https://grsai.dakka.com.cn")
        
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
        执行局部替换
        
        Args:
            image: 原始图像
            mask: 要替换区域的mask (白色=替换区域)
            prompt: 描述新内容的提示词
            negative_prompt: 负向提示词
            strength: 替换强度 (0-1)
            
        Returns:
            替换后的图像
        """
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        image_b64 = self._image_to_base64(image, "JPEG")
        mask_b64 = self._mask_to_base64(mask)
        
        if negative_prompt is None:
            negative_prompt = "blurry, low quality, distorted, deformed"
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            payload = {
                "model": "nano-banana",
                "input_image": image_b64,
                "mask": mask_b64,
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "strength": strength,
                "num_inference_steps": 30,
                "guidance_scale": 7.5
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = await client.post(
                f"{self.api_url}/api/v1/images/inpaint",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0 and result.get("data", {}).get("output_urls"):
                    output_url = result["data"]["output_urls"][0]
                    img_response = await client.get(output_url)
                    return Image.open(io.BytesIO(img_response.content))
                else:
                    raise Exception(f"Inpaint API error: {result.get('message', 'Unknown error')}")
            else:
                raise Exception(f"Inpaint API error: {response.status_code} - {response.text}")
    
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
