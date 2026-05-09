"""
图片处理服务
负责图片的预处理和后处理
"""

import io
import logging
from typing import Tuple

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


class ImageProcessor:
    """图片处理器"""

    # 支持的图片格式
    SUPPORTED_FORMATS = ["PNG", "JPEG", "JPG", "WEBP"]

    # 最大图片尺寸
    MAX_SIZE = (2048, 2048)

    # 最大文件大小 (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    # 最小图片尺寸（防 1×1 / 几像素恶意输入烧上游配额）
    MIN_DIMENSION = 64

    @staticmethod
    def validate_image(image_data: bytes) -> Tuple[bool, str]:
        """
        验证图片是否有效

        Returns:
            (是否有效, 错误信息)
        """
        if len(image_data) > ImageProcessor.MAX_FILE_SIZE:
            return False, "图片文件过大，请上传小于10MB的图片"

        if len(image_data) < 64:
            return False, "图片文件过小或为空"

        try:
            image = Image.open(io.BytesIO(image_data))
            fmt = image.format
            if not fmt or fmt.upper() not in ImageProcessor.SUPPORTED_FORMATS:
                return False, "不支持的图片格式，请上传 PNG / JPG / WebP 格式"

            # 完整性校验（verify 会消耗 image，调用者需重新 open）
            try:
                image.verify()
            except Exception:
                return False, "图片文件损坏或格式无效"

            # 重新 open 检查尺寸下界
            image = Image.open(io.BytesIO(image_data))
            w, h = image.size
            if w < ImageProcessor.MIN_DIMENSION or h < ImageProcessor.MIN_DIMENSION:
                return False, f"图片尺寸过小，至少需要 {ImageProcessor.MIN_DIMENSION}×{ImageProcessor.MIN_DIMENSION}"

            return True, ""
        except Exception:
            logger.exception("validate_image 内部错误")
            return False, "无法识别的图片文件"

    @staticmethod
    def preprocess(image_data: bytes) -> bytes:
        """
        预处理图片
        - 自动按 EXIF orientation 旋正（修复手机横拍被识别成竖向的问题）
        - 调整尺寸
        - 转换格式
        - 优化质量
        - 剥离 EXIF（避免 GPS 等隐私信息回传给前端）
        """
        image = Image.open(io.BytesIO(image_data))

        # 按 EXIF orientation 旋正——iPhone 横拍照片在 EXIF 里是 portrait+rotate flag，
        # 不调用 exif_transpose 的话，下游 LLM 看到的是侧躺的图片，分析会得出
        # "tall ceiling"（实际是宽阔房间）等错误结论
        image = ImageOps.exif_transpose(image)

        # 转换为RGB模式（去除alpha通道）
        if image.mode in ("RGBA", "P", "LA"):
            image = image.convert("RGB")

        # 调整尺寸
        if image.size[0] > ImageProcessor.MAX_SIZE[0] or image.size[1] > ImageProcessor.MAX_SIZE[1]:
            image.thumbnail(ImageProcessor.MAX_SIZE, Image.Resampling.LANCZOS)

        # 输出为JPEG，显式不带 EXIF（隐私 + 重新编码本身也起到剥离恶意 metadata 的作用）
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=90, exif=b"")
        return output.getvalue()
    
    @staticmethod
    def postprocess(image_data: bytes) -> bytes:
        """
        后处理生成的图片
        - 优化输出质量
        """
        image = Image.open(io.BytesIO(image_data))
        
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()


# 全局处理器实例
image_processor = ImageProcessor()
