"""
图片处理路由
处理图片上传、效果图生成等请求
"""

import os
import uuid
import aiofiles
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse

from app.services.getgoapi_client import getgoapi_client, GetGoModel, AspectRatio, ImageSize, DEFAULT_MODEL_PRIORITY
from app.services.image_processor import image_processor
from app.utils.prompt_builder import build_prompt

router = APIRouter()

# 输入输出目录
INPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "input")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "output")

# 确保目录存在
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@router.post("/generate")
async def generate_renovation_image(
    image: UploadFile = File(..., description="毛坯房图片(PNG/JPG)"),
    style: str = Form(..., description="装修风格"),
    room_type: str = Form(None, description="房间类型"),
    custom_prompt: str = Form(None, description="自定义提示词"),
    aspect_ratio: str = Form("auto", description="输出比例"),
    image_size: str = Form("1K", description="输出大小")
):
    """
    生成装修效果图
    
    1. 上传毛坯房图片
    2. 选择装修风格
    3. 调用Grsai Nano Banana API生成效果图
    """
    # 1. 读取并验证图片
    image_data = await image.read()
    is_valid, error_msg = image_processor.validate_image(image_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # 2. 保存原始图片到input目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = str(uuid.uuid4())[:8]
    input_filename = f"{timestamp}_{task_id}_input.jpg"
    input_path = os.path.join(INPUT_DIR, input_filename)
    
    # 预处理图片
    processed_image = image_processor.preprocess(image_data)
    async with aiofiles.open(input_path, 'wb') as f:
        await f.write(processed_image)
    
    # 3. 构建提示词
    prompt = build_prompt(style, room_type, custom_prompt)
    
    # 4. 映射宽高比
    ratio_map = {
        "auto": "4:3",
        "1:1": "1:1",
        "16:9": "16:9",
        "9:16": "9:16",
        "4:3": "4:3",
        "3:4": "3:4",
    }
    mapped_ratio = ratio_map.get(aspect_ratio, "4:3")
    
    # 5. 调用 API易 生成效果图（使用模型降级机制）
    result = await getgoapi_client.generate_with_fallback(
        prompt=prompt,
        reference_image=processed_image,
        model_priority=DEFAULT_MODEL_PRIORITY,
        aspect_ratio=mapped_ratio,
        image_size=image_size
    )
    
    # 6. 处理结果
    if result.get("code") != 0:
        return JSONResponse({
            "code": -1,
            "message": result.get("msg", "生成失败"),
            "data": None
        }, status_code=500)
    
    data = result.get("data", {})
    images = data.get("images", [])
    
    if not images:
        return JSONResponse({
            "code": -1,
            "message": "未获取到生成结果",
            "data": None
        }, status_code=500)
    
    # 7. 保存生成的图片并返回 URL
    output_urls = []
    for i, img_data in enumerate(images):
        output_filename = f"{timestamp}_{task_id}_output_{i}.png"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        async with aiofiles.open(output_path, 'wb') as f:
            await f.write(img_data["data"])
        output_urls.append(f"/output/{output_filename}")
    
    return JSONResponse({
        "code": 0,
        "message": "success",
        "data": {
            "task_id": task_id,
            "status": "succeeded",
            "input_image": input_filename,
            "output_urls": output_urls,
            "style": style,
            "prompt": prompt,
            "used_model": data.get("used_model", "unknown")
        }
    })


@router.post("/generate-async")
async def generate_renovation_image_async(
    image: UploadFile = File(..., description="毛坯房图片(PNG/JPG)"),
    style: str = Form(..., description="装修风格"),
    room_type: str = Form(None, description="房间类型"),
    custom_prompt: str = Form(None, description="自定义提示词"),
    aspect_ratio: str = Form("auto", description="输出比例"),
    image_size: str = Form("1K", description="输出大小")
):
    """
    异步生成装修效果图（立即返回任务ID，需轮询获取结果）
    """
    # 1. 读取并验证图片
    image_data = await image.read()
    is_valid, error_msg = image_processor.validate_image(image_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # 2. 保存原始图片
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_task_id = str(uuid.uuid4())[:8]
    input_filename = f"{timestamp}_{local_task_id}_input.jpg"
    input_path = os.path.join(INPUT_DIR, input_filename)
    
    processed_image = image_processor.preprocess(image_data)
    async with aiofiles.open(input_path, 'wb') as f:
        await f.write(processed_image)
    
    # 3. 构建提示词并调用API
    prompt = build_prompt(style, room_type, custom_prompt)
    image_base64 = nano_banana_client.image_to_base64(processed_image)
    
    result = await nano_banana_client.generate_image(
        prompt=prompt,
        image_base64_list=[image_base64],
        model=NanoBananaModel.NANO_BANANA,
        aspect_ratio=aspect_ratio,
        image_size=image_size
    )
    
    if result.get("code") != 0:
        return JSONResponse({
            "code": -1,
            "message": result.get("msg", "提交任务失败"),
            "data": None
        }, status_code=500)
    
    task_id = result.get("data", {}).get("id")
    
    return JSONResponse({
        "code": 0,
        "message": "success",
        "data": {
            "task_id": task_id,
            "status": "processing",
            "input_image": input_filename,
            "estimated_time": 60
        }
    })


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态
    """
    result = await nano_banana_client.get_result(task_id)
    
    if result.get("code") == -22:
        return JSONResponse({
            "code": -1,
            "message": "任务不存在",
            "data": None
        }, status_code=404)
    
    if result.get("code") != 0:
        return JSONResponse({
            "code": -1,
            "message": result.get("msg", "查询失败"),
            "data": None
        }, status_code=500)
    
    data = result.get("data", {})
    
    return JSONResponse({
        "code": 0,
        "message": "success",
        "data": {
            "task_id": data.get("id"),
            "status": data.get("status"),
            "progress": data.get("progress", 0),
            "results": data.get("results", []),
            "failure_reason": data.get("failure_reason"),
            "error": data.get("error")
        }
    })


@router.get("/styles")
async def get_styles():
    """
    获取支持的装修风格列表（从提示词库读取）
    """
    from app.utils.prompt_builder import list_available_styles
    styles = list_available_styles()
    return JSONResponse({
        "code": 0,
        "data": styles
    })


@router.get("/room-types")
async def get_room_types():
    """
    获取支持的房间类型列表
    """
    from app.utils.prompt_builder import list_available_room_types
    room_types = list_available_room_types()
    return JSONResponse({
        "code": 0,
        "data": room_types
    })


@router.get("/models")
async def get_models():
    """
    获取支持的模型列表
    """
    models = [
        {"id": "nano-banana-fast", "name": "Nano Banana Fast", "description": "快速生成，适合预览"},
        {"id": "nano-banana", "name": "Nano Banana", "description": "标准模型，平衡速度和质量"},
        {"id": "nano-banana-pro", "name": "Nano Banana Pro", "description": "专业模型，更高质量"},
        {"id": "nano-banana-pro-vt", "name": "Nano Banana Pro VT", "description": "专业增强版"},
        {"id": "nano-banana-pro-cl", "name": "Nano Banana Pro CL", "description": "专业色彩增强版"},
        {"id": "nano-banana-pro-vip", "name": "Nano Banana Pro VIP", "description": "VIP专享，支持1K/2K"},
        {"id": "nano-banana-pro-4k-vip", "name": "Nano Banana Pro 4K VIP", "description": "4K超高清专享"},
    ]
    return JSONResponse({
        "code": 0,
        "data": models
    })
