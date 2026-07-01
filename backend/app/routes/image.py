"""
图片处理路由
处理图片上传、效果图生成等请求
"""

import os
import time
import uuid
import aiofiles
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse

from app.services.getgoapi_client import getgoapi_client, GetGoModel, AspectRatio, ImageSize, DEFAULT_MODEL_PRIORITY
from app.services.llm_client import llm_client, LLMModel
from app.services.image_processor import image_processor
from app.utils.prompt_builder import build_prompt, STYLE_PROMPTS, ROOM_TYPE_PROMPTS
from app.utils.trace_logger import write_trace, new_trace_id, image_hash

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
    3. 调用API易平台生成效果图
    """
    # trace 埋点计时起点（只加新代码，不影响生图逻辑）
    _t_start = time.perf_counter()

    # 0. 校验 style 和 room_type
    if style not in STYLE_PROMPTS:
        available_styles = list(STYLE_PROMPTS.keys())
        raise HTTPException(
            status_code=400,
            detail=f"未知风格: {style}，可选值: {', '.join(available_styles)}"
        )
    if room_type and room_type not in ROOM_TYPE_PROMPTS:
        available_room_types = list(ROOM_TYPE_PROMPTS.keys())
        raise HTTPException(
            status_code=400,
            detail=f"未知房间类型: {room_type}，可选值: {', '.join(available_room_types)}"
        )

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
    input_saved = False
    
    # 预处理图片
    processed_image = image_processor.preprocess(image_data)
    # 保存原始图片
    try:
        async with aiofiles.open(input_path, "wb") as f:
            await f.write(processed_image)
        input_saved = True
    except Exception as e:
        print(f"[ERROR] 保存输入图片失败: {e}")
        raise HTTPException(status_code=500, detail="保存输入图片失败")
    
    # 3. 使用 LLM 智能分析并生成提示词
    use_llm = os.getenv("USE_LLM_PROMPT", "true").lower() == "true"
    llm_analysis = None
    vision_analysis_ok = None  # trace 埋点：None=未走LLM / True=视觉成功 / False=静默降级到盲DeepSeek

    if use_llm:
        try:
            print(f"[LLM] 开始分析毛坯房图片...")
            llm_result = await llm_client.analyze_room_and_generate_prompt(
                image_data=processed_image,
                style=style,
                room_type=room_type,
                custom_prompt=custom_prompt,
            )

            if llm_result.get("code") == 0:
                llm_analysis = llm_result.get("data", {})
                prompt = llm_analysis.get("enhanced_prompt", "")
                vision_analysis_ok = llm_analysis.get("vision_used")
                print(f"[LLM] 智能提示词生成成功")
            else:
                print(f"[LLM] 分析失败: {llm_result.get('message')}, 使用静态提示词")
                prompt = build_prompt(style, room_type, custom_prompt)
                vision_analysis_ok = False
        except Exception as e:
            print(f"[LLM] 异常: {str(e)}, 使用静态提示词")
            prompt = build_prompt(style, room_type, custom_prompt)
            vision_analysis_ok = False
    else:
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
    # 6. 处理结果
    if result.get("code") != 0:
        # 生成失败，清理 input 文件
        if input_saved:
            try:
                os.remove(input_path)
            except OSError:
                pass
        return JSONResponse({
            "code": -1,
            "message": result.get("msg", "生成失败"),
            "data": None
        }, status_code=500)
    
    data = result.get("data", {})
    # API易 返回 images 字段（base64 数据列表）
    images = data.get("images", [])
    
    if not images:
        # 生成失败，清理 input 文件
        if input_saved:
            try:
                os.remove(input_path)
            except OSError:
                pass
        return JSONResponse({
            "code": -1,
            "message": "未获取到生成结果",
            "data": None
        }, status_code=500)
    
    # 7. 保存生成的图片并返回 URL
    output_urls = []
    for i, img_data in enumerate(images):
        mime_type = img_data.get("mime_type", "image/jpeg")
        ext = ".jpg" if "jpeg" in mime_type or "jpg" in mime_type else ".png"
        output_filename = f"{timestamp}_{task_id}_output_{i}{ext}"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        async with aiofiles.open(output_path, 'wb') as f:
            await f.write(img_data["data"])
        output_urls.append(f"/output/{output_filename}")

    # 8. trace 埋点：真实用户「上传毛坯 → 首次生图成功」的完整记录（评测集头号来源）
    #    只加新代码；write_trace 内部全程 try/except，绝不拖垮生图。
    write_trace({
        "trace_id": new_trace_id(),
        "session_id": "",  # 第4步前端反馈接入后串联同一人多次操作
        # —— 输入（存相对路径，便于第5步同步到本地评测平台后解析）——
        "input_image_path": f"input/{input_filename}",
        "input_image_hash": image_hash(processed_image),
        # —— 用户真实选择 = 评测「指令」——
        "style": style,
        "room_type": room_type or "",
        "custom_prompt": custom_prompt or "",
        "aspect_ratio": aspect_ratio,
        # —— 产品内部过程（诊断用）——
        "enhanced_prompt": prompt,
        "model_used": data.get("used_model", "unknown"),
        "vision_analysis_ok": vision_analysis_ok,
        "latency_ms": int((time.perf_counter() - _t_start) * 1000),
        # —— 输出 ——
        "output_image_paths": [u.lstrip("/") for u in output_urls],
        "success": True,
        "error": "",
    })

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
            "used_model": data.get("used_model", "unknown"),
            "llm_analysis": llm_analysis.get("analysis") if llm_analysis else None,
            "llm_enabled": use_llm
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
    获取支持的模型列表（API易平台）
    """
    models = [
        {"id": "gemini-2.5-flash-image", "name": "Gemini 2.5 Flash", "description": "快速生成，高质量"},
        {"id": "gemini-3-pro-image-preview", "name": "Gemini 3 Pro", "description": "专业模型，最高质量"},
    ]
    return JSONResponse({
        "code": 0,
        "data": models
    })
