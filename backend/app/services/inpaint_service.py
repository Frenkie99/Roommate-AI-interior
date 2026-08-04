"""
Inpainting 局部替换服务
多供应商 fallback: 自定义平台 → API易
"""

import asyncio
import base64
import io
import os
import logging
from typing import Optional, List, Tuple

import httpx
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def _aspect_ratio_for_size(width: int, height: int) -> str:
    """根据图片尺寸计算最接近的宽高比"""
    ratio = width / height
    candidates = {"1:1": 1.0, "4:3": 4 / 3, "3:4": 3 / 4, "16:9": 16 / 9, "9:16": 9 / 16}
    return min(candidates.items(), key=lambda kv: abs(kv[1] - ratio))[0]


def _load_inpaint_providers() -> List[Tuple[str, str, str]]:
    """
    Load inpaint providers in priority order.
    Returns list of (name, base_url, api_key).
    """
    providers = []

    # Custom providers from env vars (gaps allowed)
    for i in range(1, 11):
        url = os.getenv(f"CUSTOM_API_{i}_URL")
        key = os.getenv(f"CUSTOM_API_{i}_KEY")
        if not url or not key:
            continue
        name = os.getenv(f"CUSTOM_API_{i}_NAME", f"custom_{i}")
        providers.append((name, url.rstrip("/"), key))

    # API易 as fallback
    apiyi_key = os.getenv("APIYI_KEY") or os.getenv("LLM_APIYI_KEY")
    if apiyi_key:
        providers.append(("apiyi", "https://api.apiyi.com", apiyi_key))

    return providers


class InpaintService:
    """Inpainting 服务 — 多供应商自动降级"""

    def __init__(self):
        self.model = "gemini-3-pro-image-preview"
        self.client = httpx.AsyncClient(timeout=300.0)

    async def close(self):
        await self.client.aclose()

    def _image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _mask_to_base64(self, mask: np.ndarray) -> str:
        mask_array = np.array(mask, dtype=np.uint8)
        if mask_array.max() == 1:
            mask_array = mask_array * 255
        mask_image = Image.fromarray(mask_array, mode="L")
        return self._image_to_base64(mask_image)

    async def _try_inpaint(
        self,
        provider_name: str,
        base_url: str,
        api_key: str,
        image: Image.Image,
        mask: np.ndarray,
        prompt: str,
        edit_prompt: str,
        aspect_ratio: str,
    ) -> Image.Image:
        """Try inpaint with a specific provider. Raises on failure."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        api_url = f"{base_url}/v1beta/models/{self.model}:generateContent"

        image_b64 = self._image_to_base64(image, "JPEG")
        mask_b64 = self._mask_to_base64(mask)

        payload = {
            "contents": [{
                "parts": [
                    {"inlineData": {"mimeType": "image/jpeg", "data": image_b64}},
                    {"inlineData": {"mimeType": "image/png", "data": mask_b64}},
                    {"text": edit_prompt},
                ]
            }],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": aspect_ratio,
                    "imageSize": "1K",
                },
            },
        }

        for attempt in range(3):
            try:
                response = await self.client.post(api_url, headers=headers, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    candidates = result.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        for part in parts:
                            if "inlineData" in part:
                                img_data = part["inlineData"].get("data", "")
                                if img_data:
                                    logger.info(f"[Inpaint] {provider_name} success")
                                    return Image.open(io.BytesIO(base64.b64decode(img_data)))
                    raise Exception("API returned no image data")

                if response.status_code >= 500 and attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue

                raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                raise

        raise Exception(f"{provider_name} inpaint failed after 3 retries")

    async def inpaint(
        self,
        image: Image.Image,
        mask: np.ndarray,
        prompt: str,
        negative_prompt: Optional[str] = None,
        strength: float = 0.85,
    ) -> Image.Image:
        """局部替换 — 多供应商自动降级"""
        if image.mode != "RGB":
            image = image.convert("RGB")

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

        aspect_ratio = _aspect_ratio_for_size(image.size[0], image.size[1])
        providers = _load_inpaint_providers()

        if not providers:
            raise Exception("No API key configured for inpaint (check CUSTOM_API_*_KEY or APIYI_KEY/LLM_APIYI_KEY)")

        last_error = None
        for name, url, key in providers:
            logger.info(f"[Inpaint] trying provider '{name}'...")
            try:
                result = await self._try_inpaint(name, url, key, image, mask, prompt, edit_prompt, aspect_ratio)
                logger.info(f"[Inpaint] ✅ {name} success")
                return result
            except Exception as e:
                logger.warning(f"[Inpaint] ❌ {name} failed: {e}")
                last_error = e
                continue

        raise last_error or Exception("All inpaint providers failed")

    async def replace_furniture(
        self,
        image: Image.Image,
        mask: np.ndarray,
        furniture_type: str,
        style: str = "modern",
    ) -> Image.Image:
        """替换家具"""
        style_prompts = {
            "modern": "modern minimalist style, clean lines, elegant",
            "scandinavian": "scandinavian style, natural wood, light colors",
            "chinese": "chinese traditional style, carved wood, oriental",
            "light_luxury": "luxury style, premium materials, sophisticated",
            "industrial": "industrial style, metal and wood, rustic",
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
        description: Optional[str] = None,
    ) -> Image.Image:
        """替换装饰物"""
        decoration_prompts = {
            "painting": "beautiful framed artwork, oil painting, gallery quality",
            "plant": "lush green indoor plant, potted plant, natural",
            "vase": "elegant decorative vase, ceramic, artistic",
            "curtain": "luxurious curtains, draped fabric, elegant",
            "rug": "beautiful area rug, patterned carpet, cozy",
            "lamp": "designer lamp, ambient lighting, stylish",
        }
        base_prompt = decoration_prompts.get(decoration_type, f"beautiful {decoration_type}")

        if description:
            prompt = f"{base_prompt}, {description}, interior design, high quality photo"
        else:
            prompt = f"{base_prompt}, interior design, high quality photo"

        negative_prompt = "blurry, low quality, distorted, out of place"
        return await self.inpaint(image, mask, prompt, negative_prompt)


inpaint_service = InpaintService()
