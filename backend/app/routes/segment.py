"""
分割与局部替换 API 路由
提供 SAM3 分割和 Inpainting 替换功能
使用 RunComfy API 进行 SAM3 分割
"""

import os
import io
import uuid
import base64
import logging
import httpx
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from PIL import Image, ImageFilter, ImageDraw
import numpy as np
from scipy import ndimage

from app.routes.auth import require_user, reserve_generation_or_raise
from app.services.auth_service import AuthUser, auth_service
from app.services.inpaint_service import inpaint_service
from app.services.sam_service import sam3_service, create_rgba_mask, extract_masked_region

logger = logging.getLogger(__name__)


def extract_mask_from_segmented_image(segmented_img: Image.Image) -> np.ndarray:
    """
    从分割后的图片中提取mask（非透明/非白色区域）
    """
    img_array = np.array(segmented_img.convert("RGBA"))
    
    # 检测alpha通道或非白色区域
    if img_array.shape[2] == 4:
        # 有alpha通道，使用alpha作为mask
        mask = img_array[:, :, 3] > 128
    else:
        # 检测非白色区域
        is_white = (img_array[:, :, 0] > 250) & (img_array[:, :, 1] > 250) & (img_array[:, :, 2] > 250)
        mask = ~is_white
    
    return mask.astype(np.uint8) * 255


def create_outline_image(mask: np.ndarray, color=(255, 200, 50), thickness=3) -> Image.Image:
    """
    从mask创建边缘轮廓图（亮黄色虚线）
    """
    # 提取边缘
    dilated = ndimage.binary_dilation(mask > 128, iterations=thickness)
    eroded = ndimage.binary_erosion(mask > 128, iterations=1)
    outline = dilated & ~eroded
    
    # 创建RGBA图像
    h, w = mask.shape
    outline_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pixels = outline_img.load()
    
    # 绘制虚线边缘
    for y in range(h):
        for x in range(w):
            if outline[y, x]:
                # 虚线效果：每隔几个像素绘制
                if (x + y) % 8 < 5:
                    pixels[x, y] = (*color, 255)
    
    return outline_img

# 图片保存目录
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/var/www/roommate/output")
BASE_URL = os.getenv("BASE_URL", "https://roommate-ai.cn")


router = APIRouter(
    prefix="/api/v1/segment",
    tags=["Segmentation"],
    dependencies=[Depends(require_user)],
)


class PointInput(BaseModel):
    x: int
    y: int
    label: int = 1  # 1=正向, 0=负向


class BoxInput(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    label: int = 1


class SegmentResponse(BaseModel):
    code: int
    message: str
    data: Optional[dict] = None


def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """将PIL Image转换为base64"""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _mask_base64_from_overlay(overlay_base64: str, original_image: Optional[Image.Image] = None) -> str:
    overlay_data = base64.b64decode(overlay_base64)
    overlay_image = Image.open(io.BytesIO(overlay_data)).convert("RGBA")

    if original_image is not None:
        overlay_rgb = overlay_image.convert("RGB")
        original_resized = original_image.convert("RGB").resize(overlay_rgb.size)
        diff = np.abs(np.array(overlay_rgb).astype(int) - np.array(original_resized).astype(int))
        mask_array = (np.sum(diff, axis=2) > 30).astype(np.uint8) * 255
    else:
        mask_array = extract_mask_from_segmented_image(overlay_image)

    return image_to_base64(Image.fromarray(mask_array, mode="L"), "PNG")


@router.post("/by-point")
async def segment_by_point(
    x: int = Form(...),
    y: int = Form(...),
    label: int = Form(1),
    image_url: str = Form(None),
    image: UploadFile = File(default=None)
):
    """
    通过点击坐标分割图像 (使用RunComfy SAM3 API)
    注意: RunComfy API暂不支持点选择，将使用通用物体识别
    
    - **image**: 上传的图像文件 (与image_url二选一)
    - **image_url**: 图片的公网URL (与image二选一)
    - **x**: 点击的X坐标
    - **y**: 点击的Y坐标  
    - **label**: 1=选择该区域, 0=排除该区域
    """
    try:
        final_image_url = image_url
        pil_image = None

        if image and not image_url:
            contents = await image.read()
            pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
            img_b64 = base64.b64encode(contents).decode("utf-8")
            final_image_url = f"data:image/jpeg;base64,{img_b64}"

        if not final_image_url:
            return JSONResponse({
                "code": -1,
                "message": "请提供image或image_url参数",
                "data": None
            }, status_code=400)

        result = await sam3_service.segment_by_point(
            image_url=final_image_url,
            point=(x, y),
            label=label
        )
        
        output = result.get("output", {})
        overlay_base64 = output.get("overlay_base64")
        if not overlay_base64:
            raise ValueError("SAM response missing overlay_base64")
        mask_base64 = _mask_base64_from_overlay(overlay_base64, pil_image)
        
        return JSONResponse({
            "code": 0,
            "message": "分割成功",
            "data": {
                "overlay": overlay_base64,
                "mask": mask_base64,
                "input_image": final_image_url,
                "click_point": {"x": x, "y": y}
            }
        })
        
    except Exception:
        logger.exception("分割失败")
        return JSONResponse({
            "code": -1,
            "message": "服务器内部错误，请稍后重试",
            "data": None
        }, status_code=500)


@router.post("/by-text")
async def segment_by_text(
    text: str = Form(...),
    threshold: float = Form(0.5),
    image_url: str = Form(None),
    image: UploadFile = File(default=None)
):
    """
    通过文本提示分割图像 (使用RunComfy SAM3 API)
    
    - **image**: 上传的图像文件 (与image_url二选一)
    - **image_url**: 图片的公网URL (与image二选一)
    - **text**: 文本描述 (如 "sofa", "chair", "lamp")
    - **threshold**: 置信度阈值
    """
    try:
        # 确定图片URL
        final_image_url = image_url

        if image and not image_url:
            # 上传文件模式：转为 base64 data URI
            contents = await image.read()
            img_b64 = base64.b64encode(contents).decode("utf-8")
            final_image_url = f"data:image/jpeg;base64,{img_b64}"

        if not final_image_url:
            return JSONResponse({
                "code": -1,
                "message": "请提供image或image_url参数",
                "data": None
            }, status_code=400)

        # 调用RunComfy SAM3 API
        result = await sam3_service.segment_by_text(
            image_url=final_image_url,
            text_prompt=text,
            threshold=threshold
        )
        
        # RunComfy返回分割后的图片URL
        output = result.get("output", {})
        segmented_image_url = output.get("image") or (output.get("images", [None])[0] if output.get("images") else None)
        
        return JSONResponse({
            "code": 0,
            "message": "分割成功",
            "data": {
                "segmented_image": segmented_image_url,
                "request_id": result.get("request_id"),
                "input_image": final_image_url
            }
        })
        
    except Exception:
        logger.exception("分割失败")
        return JSONResponse({
            "code": -1,
            "message": "服务器内部错误，请稍后重试",
            "data": None
        }, status_code=500)


@router.post("/by-box")
async def segment_by_box(
    image: UploadFile = File(...),
    x1: int = Form(...),
    y1: int = Form(...),
    x2: int = Form(...),
    y2: int = Form(...)
):
    """
    通过边界框分割图像 - 框选比点选更精准
    
    - **image**: 上传的图像文件
    - **x1, y1**: 左上角坐标
    - **x2, y2**: 右下角坐标
    """
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")

        # 优先使用 base64 data URI（本地和线上都可用）
        img_b64 = base64.b64encode(contents).decode("utf-8")
        image_source = f"data:image/jpeg;base64,{img_b64}"

        result = await sam3_service.segment_by_box(
            image_url=image_source,
            box=(x1, y1, x2, y2)
        )

        output = result.get("output", {})
        overlay_base64 = output.get("overlay_base64", "")

        mask_base64 = _mask_base64_from_overlay(overlay_base64, pil_image)
        
        return JSONResponse({
            "code": 0,
            "message": "分割成功",
            "data": {
                "mask": mask_base64,
                "overlay": overlay_base64,  # 返回overlay用于高亮显示
                "box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
            }
        })
        
    except Exception:
        logger.exception("分割失败")
        return JSONResponse({
            "code": -1,
            "message": "服务器内部错误，请稍后重试",
            "data": None
        }, status_code=500)


@router.post("/preview-mask")
async def preview_mask(
    image: UploadFile = File(...),
    mask_base64: str = Form(...),
    alpha: int = Form(128)
):
    """
    预览mask叠加效果 (RGBA)
    
    - **image**: 原始图像
    - **mask_base64**: mask的base64编码
    - **alpha**: 透明度 (0-255)
    """
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGBA")
        
        mask_data = base64.b64decode(mask_base64)
        mask_image = Image.open(io.BytesIO(mask_data)).convert("L")
        mask_array = np.array(mask_image)
        
        result_image = create_rgba_mask(pil_image, mask_array, alpha)
        
        result_b64 = image_to_base64(result_image, "PNG")
        
        return JSONResponse({
            "code": 0,
            "message": "预览生成成功",
            "data": {
                "preview_image": f"data:image/png;base64,{result_b64}"
            }
        })
        
    except Exception:
        logger.exception("预览失败")
        return JSONResponse({
            "code": -1,
            "message": "服务器内部错误，请稍后重试",
            "data": None
        }, status_code=500)


@router.post("/inpaint")
async def inpaint_region(
    image: UploadFile = File(...),
    mask_base64: str = Form(...),
    prompt: str = Form(...),
    negative_prompt: Optional[str] = Form(None),
    strength: float = Form(0.85),
    current_user: AuthUser = Depends(require_user),
):
    """
    局部替换 (Inpainting)
    
    - **image**: 原始图像
    - **mask_base64**: 黑白mask的base64（白色=替换区域）
    - **prompt**: 描述新内容的提示词
    - **negative_prompt**: 负向提示词
    - **strength**: 替换强度 (0-1)
    """
    reservation = None
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # 解码黑白mask
        mask_data = base64.b64decode(mask_base64)
        mask_image = Image.open(io.BytesIO(mask_data)).convert("L")
        mask_array = np.array(mask_image)

        reservation = reserve_generation_or_raise(
            current_user, "/api/v1/segment/inpaint"
        )
        quota = reservation.quota
        
        result_image = await inpaint_service.inpaint(
            image=pil_image,
            mask=mask_array,
            prompt=prompt,
            negative_prompt=negative_prompt,
            strength=strength
        )
        
        result_b64 = image_to_base64(result_image, "PNG")
        quota = auth_service.quota_snapshot(current_user.id)
        
        return JSONResponse({
            "code": 0,
            "message": "替换成功",
            "data": {
                "result_image": f"data:image/png;base64,{result_b64}",
                "quota": quota,
            }
        })
        
    except HTTPException:
        if reservation:
            auth_service.refund_generation(reservation.id, current_user.id)
        raise
    except Exception:
        logger.exception("替换失败")
        quota = (
            auth_service.refund_generation(reservation.id, current_user.id)
            if reservation else None
        )
        return JSONResponse({
            "code": -1,
            "message": "服务器内部错误，请稍后重试",
            "data": {"quota": quota} if quota else None
        }, status_code=500)


@router.post("/replace-furniture")
async def replace_furniture(
    image: UploadFile = File(...),
    mask_base64: str = Form(...),
    furniture_type: str = Form(...),
    style: str = Form("modern"),
    current_user: AuthUser = Depends(require_user),
):
    """
    替换家具
    
    - **image**: 原始图像
    - **mask_base64**: 家具区域的mask
    - **furniture_type**: 家具类型 (sofa, chair, table, lamp, bed, desk, cabinet)
    - **style**: 风格 (modern, scandinavian, chinese, light_luxury, industrial)
    """
    reservation = None
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        mask_data = base64.b64decode(mask_base64)
        mask_image = Image.open(io.BytesIO(mask_data)).convert("L")
        mask_array = np.array(mask_image)

        reservation = reserve_generation_or_raise(
            current_user, "/api/v1/segment/replace-furniture"
        )
        quota = reservation.quota
        
        result_image = await inpaint_service.replace_furniture(
            image=pil_image,
            mask=mask_array,
            furniture_type=furniture_type,
            style=style
        )
        
        result_b64 = image_to_base64(result_image, "PNG")
        quota = auth_service.quota_snapshot(current_user.id)
        
        return JSONResponse({
            "code": 0,
            "message": "家具替换成功",
            "data": {
                "result_image": f"data:image/png;base64,{result_b64}",
                "quota": quota,
            }
        })
        
    except HTTPException:
        if reservation:
            auth_service.refund_generation(reservation.id, current_user.id)
        raise
    except Exception:
        logger.exception("替换失败")
        quota = (
            auth_service.refund_generation(reservation.id, current_user.id)
            if reservation else None
        )
        return JSONResponse({
            "code": -1,
            "message": "服务器内部错误，请稍后重试",
            "data": {"quota": quota} if quota else None
        }, status_code=500)


@router.post("/replace-decoration")
async def replace_decoration(
    image: UploadFile = File(...),
    mask_base64: str = Form(...),
    decoration_type: str = Form(...),
    description: Optional[str] = Form(None),
    current_user: AuthUser = Depends(require_user),
):
    """
    替换装饰物
    
    - **image**: 原始图像
    - **mask_base64**: 装饰物区域的mask
    - **decoration_type**: 装饰物类型 (painting, plant, vase, curtain, rug, lamp)
    - **description**: 额外描述
    """
    reservation = None
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        mask_data = base64.b64decode(mask_base64)
        mask_image = Image.open(io.BytesIO(mask_data)).convert("L")
        mask_array = np.array(mask_image)

        reservation = reserve_generation_or_raise(
            current_user, "/api/v1/segment/replace-decoration"
        )
        quota = reservation.quota
        
        result_image = await inpaint_service.replace_decoration(
            image=pil_image,
            mask=mask_array,
            decoration_type=decoration_type,
            description=description
        )
        
        result_b64 = image_to_base64(result_image, "PNG")
        quota = auth_service.quota_snapshot(current_user.id)
        
        return JSONResponse({
            "code": 0,
            "message": "装饰物替换成功",
            "data": {
                "result_image": f"data:image/png;base64,{result_b64}",
                "quota": quota,
            }
        })
        
    except HTTPException:
        if reservation:
            auth_service.refund_generation(reservation.id, current_user.id)
        raise
    except Exception:
        logger.exception("替换失败")
        quota = (
            auth_service.refund_generation(reservation.id, current_user.id)
            if reservation else None
        )
        return JSONResponse({
            "code": -1,
            "message": "服务器内部错误，请稍后重试",
            "data": {"quota": quota} if quota else None
        }, status_code=500)


@router.get("/furniture-types")
async def get_furniture_types():
    """获取支持的家具类型列表"""
    return JSONResponse({
        "code": 0,
        "data": [
            {"id": "sofa", "name": "沙发", "emoji": "🛋️"},
            {"id": "chair", "name": "椅子", "emoji": "🪑"},
            {"id": "table", "name": "桌子", "emoji": "🪵"},
            {"id": "bed", "name": "床", "emoji": "🛏️"},
            {"id": "desk", "name": "书桌", "emoji": "📝"},
            {"id": "cabinet", "name": "柜子", "emoji": "🗄️"},
            {"id": "lamp", "name": "灯具", "emoji": "💡"},
            {"id": "bookshelf", "name": "书架", "emoji": "📚"}
        ]
    })


@router.get("/decoration-types")
async def get_decoration_types():
    """获取支持的装饰物类型列表"""
    return JSONResponse({
        "code": 0,
        "data": [
            {"id": "painting", "name": "挂画", "emoji": "🖼️"},
            {"id": "plant", "name": "绿植", "emoji": "🌿"},
            {"id": "vase", "name": "花瓶", "emoji": "🏺"},
            {"id": "curtain", "name": "窗帘", "emoji": "🪟"},
            {"id": "rug", "name": "地毯", "emoji": "🧶"},
            {"id": "clock", "name": "挂钟", "emoji": "🕐"},
            {"id": "mirror", "name": "镜子", "emoji": "🪞"},
            {"id": "sculpture", "name": "摆件", "emoji": "🗿"}
        ]
    })
