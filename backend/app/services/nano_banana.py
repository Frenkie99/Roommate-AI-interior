"""
Grsai Nano Banana API 封装
负责与 Grsai API 进行通信，实现图片生成功能
API文档: https://grsai.dakka.com.cn
"""

import os
import base64
import httpx
import asyncio
from typing import Optional, List, Union
from enum import Enum


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
    
    def __init__(self):
        # 延迟获取环境变量，确保main.py已加载
        self._api_key = None
        self._api_url = None
        self.client = httpx.AsyncClient(timeout=180.0)
    
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
        
        try:
            response = await self.client.post(
                f"{self.api_url}/v1/draw/nano-banana",
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {
                "code": -1,
                "msg": f"API请求失败: {str(e)}",
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
            return response.json()
        except httpx.HTTPError as e:
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
        while elapsed < max_wait_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            
            result = await self.get_result(task_id)
            
            if result.get("code") != 0:
                continue
            
            data = result.get("data", {})
            status = data.get("status")
            
            if status == TaskStatus.SUCCEEDED:
                return result
            elif status == TaskStatus.FAILED:
                return {
                    "code": -1,
                    "msg": f"生成失败: {data.get('failure_reason', '')} - {data.get('error', '')}",
                    "data": data
                }
        
        return {"code": -1, "msg": "生成超时", "data": {"task_id": task_id}}
    
    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()


# 全局客户端实例
nano_banana_client = NanoBananaClient()
