"""
Grsai Nano Banana API 封装
负责与 Grsai API 进行通信，实现图片生成功能
API文档: https://grsai.dakka.com.cn
"""

import os
import base64
import httpx
import asyncio
import logging
from typing import Optional, List, Union
from enum import Enum

# 配置日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class NanoBananaModel(str, Enum):
    """支持的模型列表"""
    NANO_BANANA_FAST = "nano-banana-fast"
    NANO_BANANA = "nano-banana"
    NANO_BANANA_PRO = "nano-banana-pro"
    NANO_BANANA_PRO_VT = "nano-banana-pro-vt"
    NANO_BANANA_PRO_CL = "nano-banana-pro-cl"
    NANO_BANANA_PRO_VIP = "nano-banana-pro-vip"
    NANO_BANANA_PRO_4K_VIP = "nano-banana-pro-4k-vip"


class AspectRatio(str, Enum):
    """支持的宽高比"""
    AUTO = "auto"
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


class TaskStatus(str, Enum):
    """任务状态"""
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NanoBananaClient:
    """Grsai Nano Banana API 客户端"""
    
    # 重试配置
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # 秒
    
    def __init__(self):
        # 延迟获取环境变量，确保main.py已加载
        self._api_key = None
        self._api_url = None
        # 增加超时时间，连接超时30秒，读取超时300秒
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
        )
    
    @property
    def api_key(self) -> str:
        """动态获取API Key"""
        if self._api_key is None:
            self._api_key = os.getenv("GRSAI_API_KEY")
        return self._api_key
    
    @property
    def api_url(self) -> str:
        """动态获取API URL"""
        if self._api_url is None:
            self._api_url = os.getenv("GRSAI_API_URL", "https://grsai.dakka.com.cn")
        return self._api_url
    
    def _get_headers(self) -> dict:
        """获取请求头"""
        if not self.api_key:
            raise ValueError("GRSAI_API_KEY not set in environment")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    @staticmethod
    def image_to_base64(image_data: bytes) -> str:
        """将图片数据转换为Base64字符串"""
        return base64.b64encode(image_data).decode("utf-8")
    
    async def generate_image(
        self,
        prompt: str,
        image_urls: Optional[List[str]] = None,
        image_base64_list: Optional[List[str]] = None,
        model: str = NanoBananaModel.NANO_BANANA,
        aspect_ratio: str = AspectRatio.AUTO,
        image_size: str = ImageSize.SIZE_1K,
        shut_progress: bool = True
    ) -> dict:
        """
        生成装修效果图
        
        Args:
            prompt: 提示词
            image_urls: 参考图URL列表
            image_base64_list: 参考图Base64列表
            model: 使用的模型
            aspect_ratio: 输出图像比例
            image_size: 输出图像大小
            shut_progress: 关闭进度回复，直接返回最终结果
        
        Returns:
            API响应结果
        """
        # 构建urls参数（支持URL或Base64）
        urls = []
        if image_urls:
            urls.extend(image_urls)
        if image_base64_list:
            urls.extend(image_base64_list)
        
        payload = {
            "model": model,
            "prompt": prompt,
            "aspectRatio": aspect_ratio,
            "imageSize": image_size,
            "shutProgress": shut_progress,
            "webHook": "-1"  # 使用轮询方式获取结果
        }
        
        if urls:
            payload["urls"] = urls
        
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(f"[generate_image] 尝试 {attempt + 1}/{self.MAX_RETRIES}，模型: {model}")
                response = await self.client.post(
                    f"{self.api_url}/v1/draw/nano-banana",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                logger.info(f"[generate_image] 成功，task_id: {result.get('data', {}).get('id')}")
                return result
            except httpx.TimeoutException as e:
                last_error = f"请求超时: {str(e)}"
                logger.warning(f"[generate_image] 超时 (尝试 {attempt + 1}): {last_error}")
            except httpx.HTTPStatusError as e:
                last_error = f"HTTP错误 {e.response.status_code}: {e.response.text[:200]}"
                logger.warning(f"[generate_image] HTTP错误 (尝试 {attempt + 1}): {last_error}")
            except httpx.HTTPError as e:
                last_error = f"网络错误: {str(e)}"
                logger.warning(f"[generate_image] 网络错误 (尝试 {attempt + 1}): {last_error}")
            except Exception as e:
                last_error = f"未知错误: {str(e)}"
                logger.error(f"[generate_image] 未知错误 (尝试 {attempt + 1}): {last_error}")
            
            # 重试前等待
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
        
        logger.error(f"[generate_image] 所有重试失败: {last_error}")
        return {
            "code": -1,
            "msg": f"API请求失败（已重试{self.MAX_RETRIES}次）: {last_error}",
            "data": None
        }
    
    async def get_result(self, task_id: str) -> dict:
        """
        获取任务结果
        
        Args:
            task_id: 任务ID
        
        Returns:
            任务结果
        """
        payload = {"id": task_id}
        
        try:
            response = await self.client.post(
                f"{self.api_url}/v1/draw/result",
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            status = result.get('data', {}).get('status', 'unknown')
            logger.debug(f"[get_result] task_id={task_id}, status={status}")
            return result
        except httpx.TimeoutException as e:
            logger.warning(f"[get_result] 超时: {str(e)}")
            return {
                "code": -1,
                "msg": f"查询超时: {str(e)}",
                "data": None
            }
        except httpx.HTTPError as e:
            logger.warning(f"[get_result] 网络错误: {str(e)}")
            return {
                "code": -1,
                "msg": f"获取结果失败: {str(e)}",
                "data": None
            }
    
    async def generate_and_wait(
        self,
        prompt: str,
        image_urls: Optional[List[str]] = None,
        image_base64_list: Optional[List[str]] = None,
        model: str = NanoBananaModel.NANO_BANANA,
        aspect_ratio: str = AspectRatio.AUTO,
        image_size: str = ImageSize.SIZE_1K,
        max_wait_seconds: int = 300,
        poll_interval: float = 2.0
    ) -> dict:
        """
        生成图片并等待结果（轮询模式）
        
        Args:
            prompt: 提示词
            image_urls: 参考图URL列表
            image_base64_list: 参考图Base64列表
            model: 使用的模型
            aspect_ratio: 输出图像比例
            image_size: 输出图像大小
            max_wait_seconds: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）
        
        Returns:
            生成结果
        """
        # 1. 提交生成任务
        submit_result = await self.generate_image(
            prompt=prompt,
            image_urls=image_urls,
            image_base64_list=image_base64_list,
            model=model,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            shut_progress=True
        )
        
        if submit_result.get("code") != 0:
            return submit_result
        
        task_id = submit_result.get("data", {}).get("id")
        if not task_id:
            return {"code": -1, "msg": "未获取到任务ID", "data": None}
        
        # 2. 轮询获取结果
        elapsed = 0
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        logger.info(f"[generate_and_wait] 开始轮询，task_id={task_id}，最大等待{max_wait_seconds}秒")
        
        while elapsed < max_wait_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            
            result = await self.get_result(task_id)
            
            if result.get("code") != 0:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"[generate_and_wait] 连续{max_consecutive_errors}次查询失败，放弃")
                    return {
                        "code": -1,
                        "msg": f"查询结果连续失败{max_consecutive_errors}次: {result.get('msg')}",
                        "data": {"task_id": task_id}
                    }
                continue
            
            consecutive_errors = 0  # 重置错误计数
            data = result.get("data", {})
            status = data.get("status")
            progress = data.get("progress", 0)
            
            if elapsed % 10 < poll_interval:  # 每10秒打印一次进度
                logger.info(f"[generate_and_wait] task_id={task_id}, status={status}, progress={progress}, elapsed={elapsed:.0f}s")
            
            if status == TaskStatus.SUCCEEDED:
                logger.info(f"[generate_and_wait] 生成成功！task_id={task_id}，耗时{elapsed:.0f}秒")
                return result
            elif status == TaskStatus.FAILED:
                failure_reason = data.get('failure_reason', '')
                error_msg = data.get('error', '')
                logger.error(f"[generate_and_wait] 生成失败: {failure_reason} - {error_msg}")
                return {
                    "code": -1,
                    "msg": f"生成失败: {failure_reason} - {error_msg}",
                    "data": data
                }
        
        logger.error(f"[generate_and_wait] 超时！task_id={task_id}，已等待{max_wait_seconds}秒")
        return {"code": -1, "msg": f"生成超时（已等待{max_wait_seconds}秒）", "data": {"task_id": task_id}}
    
    async def generate_with_fallback(
        self,
        prompt: str,
        image_urls: Optional[List[str]] = None,
        image_base64_list: Optional[List[str]] = None,
        model_priority: Optional[List[str]] = None,
        aspect_ratio: str = AspectRatio.AUTO,
        image_size: str = ImageSize.SIZE_1K,
        max_wait_seconds: int = 300,
        poll_interval: float = 2.0
    ) -> dict:
        """
        带模型降级的图片生成（自动尝试备选模型）
        
        Args:
            prompt: 提示词
            image_urls: 参考图URL列表
            image_base64_list: 参考图Base64列表
            model_priority: 模型优先级列表，按顺序尝试
            aspect_ratio: 输出图像比例
            image_size: 输出图像大小
            max_wait_seconds: 最大等待时间（秒）
            poll_interval: 轮询间隔（秒）
        
        Returns:
            生成结果，包含实际使用的模型信息
        """
        # 默认模型优先级：pro > 普通 > fast
        if model_priority is None:
            model_priority = [
                NanoBananaModel.NANO_BANANA_PRO,
                NanoBananaModel.NANO_BANANA,
                NanoBananaModel.NANO_BANANA_FAST,
            ]
        
        last_error = None
        for model in model_priority:
            logger.info(f"[generate_with_fallback] 尝试模型: {model}")
            
            result = await self.generate_and_wait(
                prompt=prompt,
                image_urls=image_urls,
                image_base64_list=image_base64_list,
                model=model,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                max_wait_seconds=max_wait_seconds,
                poll_interval=poll_interval
            )
            
            # 检查是否成功
            if result.get("code") == 0:
                logger.info(f"[generate_with_fallback] 模型 {model} 生成成功")
                # 添加实际使用的模型信息
                if "data" in result and result["data"]:
                    result["data"]["used_model"] = model
                return result
            
            # 检查是否是可重试的错误（超时、服务不可用等）
            error_msg = result.get("msg", "")
            last_error = error_msg
            
            # 如果是 timeout 或服务端错误，尝试下一个模型
            if "timeout" in error_msg.lower() or "gemini" in error_msg.lower():
                logger.warning(f"[generate_with_fallback] 模型 {model} 失败（{error_msg}），尝试下一个模型")
                continue
            
            # 其他错误（如参数错误）直接返回，不再尝试
            logger.error(f"[generate_with_fallback] 模型 {model} 失败（不可重试）: {error_msg}")
            return result
        
        # 所有模型都失败
        logger.error(f"[generate_with_fallback] 所有模型都失败，最后错误: {last_error}")
        return {
            "code": -1,
            "msg": f"所有模型都生成失败，最后错误: {last_error}",
            "data": None
        }
    
    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()


# 模型优先级配置（可在此处调整）
DEFAULT_MODEL_PRIORITY = [
    NanoBananaModel.NANO_BANANA_PRO,      # 优先使用 Pro 版本
    NanoBananaModel.NANO_BANANA,          # 备选：普通版本
    NanoBananaModel.NANO_BANANA_FAST,     # 最后：快速版本
]

# 全局客户端实例
nano_banana_client = NanoBananaClient()
