"""
分割与局部替换 API 路由
提供 SAM3 分割和 Inpainting 替换功能
"""

import io
import base64
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from PIL import Image
import numpy as np

from app.services.sam_service import sam3_service, create_rgba_mask, extract_masked_region
from app.services.inpaint_service import inpaint_service


router = APIRouter(prefix="/api/v1/segment", tags=["Segmentation"])


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


@router.post("/by-point")
async def segment_by_point(
    image: UploadFile = File(...),
    x: int = Form(...),
    y: int = Form(...),
    label: int = Form(1)
):
    """
    通过点击坐标分割图像
    
    - **image**: 上传的图像文件
    - **x**: 点击的X坐标
    - **y**: 点击的Y坐标  
    - **label**: 1=选择该区域, 0=排除该区域
    """
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        result = await sam3_service.segment_by_point(
            image=pil_image,
            point=(x, y),
            label=label
        )
        
        return JSONResponse({
            "code": 0,
            "message": "分割成功",
            "data": {
                "masks": result.get("masks", []),
                "boxes": result.get("boxes", []),
                "scores": result.get("scores", [])
            }
        })
        
    except Exception as e:
        return JSONResponse({
            "code": -1,
            "message": f"分割失败: {str(e)}",
            "data": None
        }, status_code=500)


@router.post("/by-text")
async def segment_by_text(
    image: UploadFile = File(...),
    text: str = Form(...),
    threshold: float = Form(0.5)
):
    """
    通过文本提示分割图像
    
    - **image**: 上传的图像文件
    - **text**: 文本描述 (如 "sofa", "chair", "lamp")
    - **threshold**: 置信度阈值
    """
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        result = await sam3_service.segment_by_text(
            image=pil_image,
            text_prompt=text,
            threshold=threshold
        )
        
        return JSONResponse({
            "code": 0,
            "message": "分割成功",
            "data": {
                "masks": result.get("masks", []),
                "boxes": result.get("boxes", []),
                "scores": result.get("scores", []),
                "labels": result.get("labels", [])
            }
        })
        
    except Exception as e:
        return JSONResponse({
            "code": -1,
            "message": f"分割失败: {str(e)}",
            "data": None
        }, status_code=500)


@router.post("/by-box")
async def segment_by_box(
    image: UploadFile = File(...),
    x1: int = Form(...),
    y1: int = Form(...),
    x2: int = Form(...),
    y2: int = Form(...),
    label: int = Form(1)
):
    """
    通过边界框分割图像
    
    - **image**: 上传的图像文件
    - **x1, y1**: 左上角坐标
    - **x2, y2**: 右下角坐标
    - **label**: 1=选择, 0=排除
    """
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        result = await sam3_service.segment_by_box(
            image=pil_image,
            box=(x1, y1, x2, y2),
            label=label
        )
        
        return JSONResponse({
            "code": 0,
            "message": "分割成功",
            "data": {
                "masks": result.get("masks", []),
                "boxes": result.get("boxes", []),
                "scores": result.get("scores", [])
            }
        })
        
    except Exception as e:
        return JSONResponse({
            "code": -1,
            "message": f"分割失败: {str(e)}",
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
        
    except Exception as e:
        return JSONResponse({
            "code": -1,
            "message": f"预览失败: {str(e)}",
            "data": None
        }, status_code=500)


@router.post("/inpaint")
async def inpaint_region(
    image: UploadFile = File(...),
    mask_base64: str = Form(...),
    prompt: str = Form(...),
    negative_prompt: Optional[str] = Form(None),
    strength: float = Form(0.85)
):
    """
    局部替换 (Inpainting)
    
    - **image**: 原始图像
    - **mask_base64**: 要替换区域的mask (白色=替换区域)
    - **prompt**: 描述新内容的提示词
    - **negative_prompt**: 负向提示词
    - **strength**: 替换强度 (0-1)
    """
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        mask_data = base64.b64decode(mask_base64)
        mask_image = Image.open(io.BytesIO(mask_data)).convert("L")
        mask_array = np.array(mask_image)
        
        result_image = await inpaint_service.inpaint(
            image=pil_image,
            mask=mask_array,
            prompt=prompt,
            negative_prompt=negative_prompt,
            strength=strength
        )
        
        result_b64 = image_to_base64(result_image, "PNG")
        
        return JSONResponse({
            "code": 0,
            "message": "替换成功",
            "data": {
                "result_image": f"data:image/png;base64,{result_b64}"
            }
        })
        
    except Exception as e:
        return JSONResponse({
            "code": -1,
            "message": f"替换失败: {str(e)}",
            "data": None
        }, status_code=500)


@router.post("/replace-furniture")
async def replace_furniture(
    image: UploadFile = File(...),
    mask_base64: str = Form(...),
    furniture_type: str = Form(...),
    style: str = Form("modern")
):
    """
    替换家具
    
    - **image**: 原始图像
    - **mask_base64**: 家具区域的mask
    - **furniture_type**: 家具类型 (sofa, chair, table, lamp, bed, desk, cabinet)
    - **style**: 风格 (modern, scandinavian, chinese, light_luxury, industrial)
    """
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        mask_data = base64.b64decode(mask_base64)
        mask_image = Image.open(io.BytesIO(mask_data)).convert("L")
        mask_array = np.array(mask_image)
        
        result_image = await inpaint_service.replace_furniture(
            image=pil_image,
            mask=mask_array,
            furniture_type=furniture_type,
            style=style
        )
        
        result_b64 = image_to_base64(result_image, "PNG")
        
        return JSONResponse({
            "code": 0,
            "message": "家具替换成功",
            "data": {
                "result_image": f"data:image/png;base64,{result_b64}"
            }
        })
        
    except Exception as e:
        return JSONResponse({
            "code": -1,
            "message": f"替换失败: {str(e)}",
            "data": None
        }, status_code=500)


@router.post("/replace-decoration")
async def replace_decoration(
    image: UploadFile = File(...),
    mask_base64: str = Form(...),
    decoration_type: str = Form(...),
    description: Optional[str] = Form(None)
):
    """
    替换装饰物
    
    - **image**: 原始图像
    - **mask_base64**: 装饰物区域的mask
    - **decoration_type**: 装饰物类型 (painting, plant, vase, curtain, rug, lamp)
    - **description**: 额外描述
    """
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        mask_data = base64.b64decode(mask_base64)
        mask_image = Image.open(io.BytesIO(mask_data)).convert("L")
        mask_array = np.array(mask_image)
        
        result_image = await inpaint_service.replace_decoration(
            image=pil_image,
            mask=mask_array,
            decoration_type=decoration_type,
            description=description
        )
        
        result_b64 = image_to_base64(result_image, "PNG")
        
        return JSONResponse({
            "code": 0,
            "message": "装饰物替换成功",
            "data": {
                "result_image": f"data:image/png;base64,{result_b64}"
            }
        })
        
    except Exception as e:
        return JSONResponse({
            "code": -1,
            "message": f"替换失败: {str(e)}",
            "data": None
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
