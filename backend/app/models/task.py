"""
任务数据模型
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    """任务模型"""
    task_id: str
    status: TaskStatus
    style: str
    room_type: Optional[str] = None
    original_image_url: Optional[str] = None
    result_image_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GenerateRequest(BaseModel):
    """生成请求模型"""
    style: str
    room_type: Optional[str] = None
    custom_prompt: Optional[str] = None


class GenerateResponse(BaseModel):
    """生成响应模型"""
    code: int
    message: str
    data: dict
