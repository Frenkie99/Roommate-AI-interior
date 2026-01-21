"""
DMXAPI Gemini 图像生成客户端
使用 DMXAPI 的 Gemini 接口生成室内设计效果图
API文档: https://docs.dmxapi.cn
"""

import os
import base64
import httpx
import asyncio
import logging
from typing import Optional, List
from enum import Enum

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class GeminiModel(str, Enum):
    """支持的模型列表"""
    GEMINI_3_PRO_IMAGE = "gemini-3-pro-image-preview"  # 支持 1K/2K/4K
    GEMINI_25_FLASH_IMAGE = "gemini-2.5-flash-image"   # 快速生成，固定 1K
    NANO_BANANA_2 = "nano-banana-2"  # DMXAPI 文档中的备选模型


class AspectRatio(str, Enum):
    """支持的宽高比"""
    RATIO_1_1 = "1:1"
    RATIO_16_9 = "16:9"
    RATIO_9_16 = "9:16"
    RATIO_4_3 = "4:3"
    RATIO_3_4 = "3:4"
    RATIO_3_2 = "3:2"
    RATIO_2_3 = "2:3"
    RATIO_5_4 = "5:4"
    RATIO_4_5 = "4:5"
    RATIO_21_9 = "21:9"


class ImageSize(str, Enum):
    """支持的图片大小"""
    SIZE_1K = "1K"
    SIZE_2K = "2K"
    SIZE_4K = "4K"


class DMXAPIClient:
    """DMXAPI Gemini 图像生成客户端"""
    
    # 重试配置
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # 秒
    
    # API 配置
    BASE_URL = "https://www.dmxapi.cn"
    
    def __init__(self):
        self._api_key = None
        # DMXAPI 是同步返回，但生成可能需要较长时间
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30.0, read=300.0, write=60.0, pool=30.0)
        )
    
    @property
    def api_key(self) -> str:
        """动态获取API Key"""
        if self._api_key is None:
            self._api_key = os.getenv("DMXAPI_KEY")
        return self._api_key
    
    def _get_headers(self) -> dict:
        """获取请求头"""
        if not self.api_key:
            raise ValueError("DMXAPI_KEY not set in environment")
        return {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    @staticmethod
    def image_to_base64(image_data: bytes) -> str:
        """将图片数据转换为Base64字符串"""
        return base64.b64encode(image_data).decode("utf-8")
    
    @staticmethod
    def base64_to_image(base64_data: str) -> bytes:
        """将Base64字符串转换为图片数据"""
        return base64.b64decode(base64_data)
    
    def _detect_mime_type(self, image_data: bytes) -> str:
        """检测图片MIME类型"""
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        elif image_data[:2] == b'\xff\xd8':
            return "image/jpeg"
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            return "image/webp"
        else:
            return "image/jpeg"  # 默认
    
    async def generate_image(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        model: str = GeminiModel.NANO_BANANA_2,  # 使用 nano-banana-2 模型
        aspect_ratio: str = AspectRatio.RATIO_4_3,
        image_size: str = ImageSize.SIZE_1K
    ) -> dict:
        """
        生成室内设计效果图
        
        Args:
            prompt: 提示词
            reference_image: 参考图片（原始字节数据）
            model: 使用的模型
            aspect_ratio: 输出图像比例
            image_size: 输出图像大小（仅 gemini-3-pro-image-preview 支持 2K/4K）
        
        Returns:
            包含生成结果的字典
        """
        # 构建请求内容
        parts = []
        
        # 添加参考图片（如果有）
        if reference_image:
            mime_type = self._detect_mime_type(reference_image)
            image_base64 = self.image_to_base64(reference_image)
            parts.append({
                "inlineData": {
                    "mimeType": mime_type,
                    "data": image_base64
                }
            })
        
        # 添加提示词
        parts.append({"text": prompt})
        
        # 构建请求体 - 统一使用简化格式，避免模型兼容性问题
        payload = {
            "contents": [{
                "parts": parts
            }]
        }
        
        # API URL
        api_url = f"{self.BASE_URL}/v1beta/models/{model}:generateContent"
        
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"[DMXAPI] 尝试 {attempt + 1}/{self.MAX_RETRIES}，模型: {model}")
                
                response = await self.client.post(
                    api_url,
                    headers=self._get_headers(),
                    json=payload
                )
                
                if response.status_code != 200:
                    error_text = response.text[:500]
                    last_error = f"HTTP {response.status_code}: {error_text}"
                    logger.warning(f"[DMXAPI] HTTP错误 (尝试 {attempt + 1}): {last_error}")
                    if attempt < self.MAX_RETRIES - 1:
                        await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                
                result = response.json()
                
                # 解析响应
                candidates = result.get("candidates", [])
                if not candidates:
                    last_error = "响应中没有 candidates"
                    logger.warning(f"[DMXAPI] 无结果 (尝试 {attempt + 1}): {last_error}")
                    if attempt < self.MAX_RETRIES - 1:
                        await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                
                # 提取图片数据
                image_data_list = []
                for part in parts:
                    if "inlineData" in part:
                        inline_data = part["inlineData"]
                        image_bytes = self.base64_to_image(inline_data["data"])
                        image_data_list.append({
                            "data": image_bytes,
                            "mime_type": inline_data.get("mimeType", "image/png")
                        })
                
                if not image_data_list:
                    last_error = "响应中没有图片数据"
                    logger.warning(f"[DMXAPI] 无图片 (尝试 {attempt + 1}): {last_error}")
                    if attempt < self.MAX_RETRIES - 1:
                        await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                
                logger.info(f"[DMXAPI] 生成成功！获取到 {len(image_data_list)} 张图片")
                
                return {
                    "code": 0,
                    "msg": "success",
                    "data": {
                        "images": image_data_list,
                        "model": model
                    }
                }
                
            except httpx.TimeoutException as e:
                last_error = f"请求超时: {str(e)}"
                logger.warning(f"[DMXAPI] 超时 (尝试 {attempt + 1}): {last_error}")
            except httpx.HTTPError as e:
                last_error = f"网络错误: {str(e)}"
                logger.warning(f"[DMXAPI] 网络错误 (尝试 {attempt + 1}): {last_error}")
            except Exception as e:
                last_error = f"未知错误: {str(e)}"
                logger.error(f"[DMXAPI] 未知错误 (尝试 {attempt + 1}): {last_error}")
            
            # 重试前等待
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
        
        logger.error(f"[DMXAPI] 所有重试失败: {last_error}")
        return {
            "code": -1,
            "msg": f"生成失败（已重试{self.MAX_RETRIES}次）: {last_error}",
            "data": None
        }
    
    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()


# 全局客户端实例
dmxapi_client = DMXAPIClient()
