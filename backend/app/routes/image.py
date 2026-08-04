"""
图片处理路由
处理图片上传、效果图生成等请求
"""

import io
import os
import time
import uuid
import aiofiles
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
from pydantic import BaseModel

from app.services.getgoapi_client import getgoapi_client, GetGoModel, AspectRatio, ImageSize, DEFAULT_MODEL_PRIORITY, generate_design_image
from app.services.inpaint_service import _aspect_ratio_for_size
from app.services.llm_client import llm_client, LLMModel
from app.services.image_processor import image_processor
from app.utils.prompt_builder import build_prompt, build_prompt_v2, STYLE_PROMPTS, ROOM_TYPE_PROMPTS, resolve_style_id
from app.utils.trace_logger import write_trace, new_trace_id, image_hash, write_feedback, FEEDBACK_ACTIONS

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
    image_size: str = Form("1K", description="输出大小"),
    session_id: str = Form(None, description="前端匿名会话id（点评埋点串联用，可选）")
):
    """
    生成装修效果图

    1. 上传毛坯房图片
    2. 选择装修风格
    3. 调用API易平台生成效果图
    """
    # trace 埋点计时起点（只加新代码，不影响生图逻辑）
    _t_start = time.perf_counter()

    # 0. 旧风格 ID 重映射（老用户缓存/历史记录兼容），然后校验 style 和 room_type
    style = resolve_style_id(style)
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
    vision_analysis = {}       # trace 埋点：AI 对房间的原始理解（白盒中间产物，出问题先看这里）
    prompt_source = "static"   # trace 埋点：enhanced_prompt 走了哪条路径
    _vision_ms = None          # trace 埋点：视觉分析阶段耗时

    if use_llm:
        _t_vision = time.perf_counter()
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
                prompt = build_prompt_v2(style, room_type, llm_analysis, custom_prompt)
                vision_analysis_ok = llm_analysis.get("vision_used")
                vision_analysis = llm_analysis.get("analysis") or {}
                prompt_source = "llm_vision" if vision_analysis_ok else "blind_deepseek"
                print(f"[LLM] 智能提示词生成成功")
            else:
                print(f"[LLM] 分析失败: {llm_result.get('message')}, 使用静态提示词")
                prompt = build_prompt_v2(style, room_type, custom_prompt=custom_prompt)
                vision_analysis_ok = False
                prompt_source = "static_on_error"
        except Exception as e:
            print(f"[LLM] 异常: {str(e)}, 使用静态提示词")
            prompt = build_prompt_v2(style, room_type, custom_prompt=custom_prompt)
            vision_analysis_ok = False
            prompt_source = "static_on_error"
        finally:
            _vision_ms = int((time.perf_counter() - _t_vision) * 1000)
    else:
        prompt = build_prompt_v2(style, room_type, custom_prompt=custom_prompt)

    # 4. 映射宽高比
    # P0 修复（2026-07-10，评测批量归因坐实，见 evals/PRODUCT_CONTRACT.md P0）：
    # "auto" 曾硬编码 "4:3"——手机竖拍毛坯被强转横图，模型被迫横向虚构空间（"盲目扩图"的机械成因）。
    # 现改为按预处理后图片的实际尺寸就近映射（复用 inpaint 路径的 _aspect_ratio_for_size 同款逻辑）。
    ratio_map = {
        "1:1": "1:1",
        "16:9": "16:9",
        "9:16": "9:16",
        "4:3": "4:3",
        "3:4": "3:4",
    }
    if aspect_ratio == "auto":
        try:
            with Image.open(io.BytesIO(processed_image)) as _img:
                mapped_ratio = _aspect_ratio_for_size(*_img.size)
        except Exception as e:
            print(f"[WARN] auto 画幅读图失败，回退 4:3: {e}")
            mapped_ratio = "4:3"
    else:
        mapped_ratio = ratio_map.get(aspect_ratio, "4:3")
    
    # 5. 调用 Gemini 生成效果图（Google 直连优先 → API易 备选）
    _t_gen = time.perf_counter()  # trace: generation phase timer start
    result = await generate_design_image(
        prompt=prompt,
        reference_image=processed_image,
        model_priority=DEFAULT_MODEL_PRIORITY,
        aspect_ratio=mapped_ratio,
        image_size=image_size
    )
    _gen_ms = int((time.perf_counter() - _t_gen) * 1000)  # trace 埋点：生图阶段耗时
    
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
    trace_id = new_trace_id()
    write_trace({
        "trace_id": trace_id,
        "session_id": (session_id or "")[:64],
        # —— 输入（存相对路径，便于第5步同步到本地评测平台后解析）——
        "input_image_path": f"input/{input_filename}",
        "input_image_hash": image_hash(processed_image),
        # —— 用户真实选择 = 评测「指令」——
        "style": style,
        "room_type": room_type or "",
        "custom_prompt": custom_prompt or "",
        "aspect_ratio": aspect_ratio,
        # —— 产品内部过程（诊断用 / 白盒中间步骤）——
        "enhanced_prompt": prompt,
        "prompt_source": prompt_source,
        "vision_analysis": vision_analysis,
        "model_used": data.get("used_model", "unknown"),
        "vision_analysis_ok": vision_analysis_ok,
        "latency_ms": int((time.perf_counter() - _t_start) * 1000),
        "latency_breakdown": {"vision_ms": _vision_ms, "generate_ms": _gen_ms},
        # —— 输出 ——
        "output_image_paths": [u.lstrip("/") for u in output_urls],
        "success": True,
        "error": "",
        # P0 修复留痕：auto 实际映射到的画幅（验证自适应是否生效）
        "metadata": {"aspect_ratio_mapped": mapped_ratio},
    })

    return JSONResponse({
        "code": 0,
        "message": "success",
        "data": {
            "task_id": task_id,
            "trace_id": trace_id,
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




class FeedbackRequest(BaseModel):
    trace_id: str
    action: str
    session_id: str = ""


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """
    用户点评埋点（第4步）：记录对某次生图结果的反馈。

    action 取值：satisfied(满意) / unsatisfied(不要了) / download(下载) / regenerate(重新生成)。
    只追加写 feedback.jsonl，不查证 trace_id 是否存在（评测侧导入时按 trace_id 关联，孤儿记录无害）。
    """
    if req.action not in FEEDBACK_ACTIONS:
        raise HTTPException(status_code=400, detail=f"未知反馈类型: {req.action}，可选: {', '.join(FEEDBACK_ACTIONS)}")
    if not req.trace_id.strip():
        raise HTTPException(status_code=400, detail="缺少 trace_id")
    write_feedback({
        "trace_id": req.trace_id,
        "action": req.action,
        "session_id": req.session_id,
    })
    return JSONResponse({"code": 0, "message": "success", "data": {}})


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
