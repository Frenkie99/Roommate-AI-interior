"""
API易 客户端 - Gemini Image Generation
API文档: https://api.apiyi.com
支持模型: gemini-3-pro-image-preview, gemini-2.5-flash-image
"""

import os
import base64
import httpx
import logging
from typing import Optional, List
from enum import Enum

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class GetGoModel(str, Enum):
    """支持的模型列表"""
    GEMINI_3_PRO_IMAGE = "gemini-3-pro-image-preview"
    GEMINI_25_FLASH_IMAGE = "gemini-2.5-flash-image"
    GEMINI_25_FLASH_IMAGE_PREVIEW = "gemini-2.5-flash-image-preview"


class AspectRatio(str, Enum):
    """支持的宽高比"""
    RATIO_1_1 = "1:1"
    RATIO_16_9 = "16:9"
    RATIO_9_16 = "9:16"
    RATIO_4_3 = "4:3"
    RATIO_3_4 = "3:4"


class ImageSize(str, Enum):
    """支持的图片大小"""
    SIZE_1K = "1K"
    SIZE_2K = "2K"
    SIZE_4K = "4K"


class GetGoAPIClient:
    """GetGoAPI 客户端"""
    
    # 重试配置
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    
    # API 基础 URL (API易平台)
    BASE_URL = "https://api.apiyi.com"
    
    def __init__(self):
        # 增加超时时间
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
        )
    
    @property
    def api_key(self) -> str:
        """每次动态获取 API Key，不缓存"""
        return os.getenv("APIYI_KEY")
    
    def _get_headers(self) -> dict:
        """获取请求头"""
        if not self.api_key:
            raise ValueError("APIYI_KEY not set in environment")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def image_to_base64(self, image_data: bytes) -> str:
        """将图片字节数据转换为 Base64 字符串"""
        return base64.b64encode(image_data).decode('utf-8')
    
    def base64_to_image(self, base64_str: str) -> bytes:
        """将 Base64 字符串转换为图片字节数据"""
        return base64.b64decode(base64_str)
    
    def _detect_mime_type(self, image_data: bytes) -> str:
        """检测图片 MIME 类型"""
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        elif image_data[:2] == b'\xff\xd8':
            return "image/jpeg"
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            return "image/webp"
        else:
            return "image/jpeg"
    
    async def generate_image(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        model: str = GetGoModel.GEMINI_3_PRO_IMAGE,
        aspect_ratio: str = AspectRatio.RATIO_4_3,
        image_size: str = ImageSize.SIZE_1K,
        number_of_images: int = 1
    ) -> dict:
        """
        生成室内设计效果图
        
        Args:
            prompt: 提示词
            reference_image: 参考图片（原始字节数据）
            model: 使用的模型
            aspect_ratio: 输出图像比例
            image_size: 输出图像大小
            number_of_images: 生成图片数量
        
        Returns:
            生成结果
        """
        # 构建 parts
        parts = []
        
        # 如果有参考图片，先添加图片
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
        
        # 构建请求体
        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": aspect_ratio,
                    "imageSize": image_size
                }
            }
        }
        
        # API URL - 确保使用模型名称字符串而非枚举对象
        model_name = model.value if hasattr(model, 'value') else str(model)
        api_url = f"{self.BASE_URL}/v1beta/models/{model_name}:generateContent"
        
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"[API易] 尝试 {attempt + 1}/{self.MAX_RETRIES}，模型: {model}")
                
                response = await self.client.post(
                    api_url,
                    headers=self._get_headers(),
                    json=payload
                )
                
                # 检查响应状态
                if response.status_code == 200:
                    result = response.json()
                    
                    # 解析响应
                    candidates = result.get("candidates", [])
                    if not candidates:
                        return {
                            "code": -1,
                            "msg": "API 返回空结果",
                            "data": None
                        }
                    
                    # 提取图片数据
                    images = []
                    for candidate in candidates:
                        content = candidate.get("content", {})
                        parts = content.get("parts", [])
                        for part in parts:
                            inline_data = part.get("inlineData", {})
                            if inline_data:
                                image_base64 = inline_data.get("data", "")
                                mime_type = inline_data.get("mimeType", "image/jpeg")
                                if image_base64:
                                    images.append({
                                        "data": self.base64_to_image(image_base64),
                                        "mime_type": mime_type
                                    })
                    
                    if not images:
                        return {
                            "code": -1,
                            "msg": "未获取到生成的图片",
                            "data": None
                        }
                    
                    logger.info(f"[API易] 生成成功，获取到 {len(images)} 张图片")
                    return {
                        "code": 0,
                        "msg": "success",
                        "data": {
                            "images": images,
                            "model": model
                        }
                    }
                
                # 处理错误响应
                error_text = response.text
                logger.warning(f"[API易] HTTP {response.status_code}: {error_text}")
                
                # 如果是服务端错误，重试
                if response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}: {error_text}"
                    continue
                
                # 客户端错误，直接返回
                return {
                    "code": -1,
                    "msg": f"API 错误 ({response.status_code}): {error_text}",
                    "data": None
                }
                
            except httpx.TimeoutException as e:
                logger.warning(f"[API易] 超时: {str(e)}")
                last_error = f"请求超时: {str(e)}"
                continue
            except httpx.HTTPError as e:
                logger.warning(f"[API易] 网络错误: {str(e)}")
                last_error = f"网络错误: {str(e)}"
                continue
            except Exception as e:
                logger.error(f"[API易] 未知错误: {str(e)}")
                last_error = f"未知错误: {str(e)}"
                continue
        
        # 所有重试都失败
        return {
            "code": -1,
            "msg": f"API 请求失败（已重试 {self.MAX_RETRIES} 次）: {last_error}",
            "data": None
        }
    
    async def generate_with_fallback(
        self,
        prompt: str,
        reference_image: Optional[bytes] = None,
        model_priority: Optional[List[str]] = None,
        aspect_ratio: str = AspectRatio.RATIO_4_3,
        image_size: str = ImageSize.SIZE_1K,
        number_of_images: int = 1
    ) -> dict:
        """
        带模型降级的图片生成
        
        Args:
            prompt: 提示词
            reference_image: 参考图片
            model_priority: 模型优先级列表
            aspect_ratio: 输出图像比例
            image_size: 输出图像大小
            number_of_images: 生成图片数量
        
        Returns:
            生成结果
        """
        if model_priority is None:
            model_priority = [
                GetGoModel.GEMINI_3_PRO_IMAGE,
                GetGoModel.GEMINI_25_FLASH_IMAGE,
            ]
        
        last_error = None
        for model in model_priority:
            logger.info(f"[API易] 尝试模型: {model}")
            
            result = await self.generate_image(
                prompt=prompt,
                reference_image=reference_image,
                model=model,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                number_of_images=number_of_images
            )
            
            if result.get("code") == 0:
                logger.info(f"[API易] 模型 {model} 生成成功")
                if "data" in result and result["data"]:
                    result["data"]["used_model"] = model
                return result
            
            error_msg = result.get("msg", "")
            last_error = error_msg
            
            # 如果是超时或服务端错误，尝试下一个模型
            if "timeout" in error_msg.lower() or "500" in error_msg or "503" in error_msg:
                logger.warning(f"[API易] 模型 {model} 失败（{error_msg}），尝试下一个模型")
                continue
            
            # 其他错误直接返回
            logger.error(f"[API易] 模型 {model} 失败（不可重试）: {error_msg}")
            return result
        
        return {
            "code": -1,
            "msg": f"所有模型都生成失败，最后错误: {last_error}",
            "data": None
        }
    
    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()


# 模型优先级配置
DEFAULT_MODEL_PRIORITY = [
    GetGoModel.GEMINI_3_PRO_IMAGE,  # 使用 Pro 版本，质量更高，结构保持更好
    GetGoModel.GEMINI_25_FLASH_IMAGE,  # 降级备选
]

# 全局客户端实例
getgoapi_client = GetGoAPIClient()
