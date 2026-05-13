"""
图片处理服务
负责图片的预处理和后处理
"""

from PIL import Image, ImageOps
import io
from typing import Tuple


class ImageProcessor:
    """图片处理器"""
    
    # 支持的图片格式
    SUPPORTED_FORMATS = ["PNG", "JPEG", "JPG", "WEBP"]
    
    # 最大图片尺寸
    MAX_SIZE = (2048, 2048)
    
    # 最大文件大小 (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    # 最小文件大小 (64 字节)
    MIN_FILE_SIZE = 64

    # 最小图片尺寸 (64x64)
    MIN_IMAGE_SIZE = (64, 64)

    @staticmethod
    def validate_image(image_data: bytes) -> Tuple[bool, str]:
        """
        验证图片是否有效

        Returns:
            (是否有效, 错误信息)
        """
        if len(image_data) > ImageProcessor.MAX_FILE_SIZE:
            return False, "图片文件过大，请上传小于10MB的图片"

        if len(image_data) < ImageProcessor.MIN_FILE_SIZE:
            return False, "图片文件过小或已损坏"

        try:
            image = Image.open(io.BytesIO(image_data))

            # 检查格式
            fmt = image.format
            if not fmt or fmt.upper() not in ImageProcessor.SUPPORTED_FORMATS:
                return False, f"不支持的图片格式，请上传 PNG、JPG 或 WEBP 格式"

            # 验证图片完整性
            try:
                image.verify()
            except Exception:
                return False, "图片损坏或格式无效"

            # 重新打开图片（verify 后需要重新 open）
            image = Image.open(io.BytesIO(image_data))

            # 检查最小尺寸
            if image.size[0] < ImageProcessor.MIN_IMAGE_SIZE[0] or image.size[1] < ImageProcessor.MIN_IMAGE_SIZE[1]:
                return False, f"图片尺寸过小，最小要求 {ImageProcessor.MIN_IMAGE_SIZE[0]}x{ImageProcessor.MIN_IMAGE_SIZE[1]}"

            return True, ""
        except Exception as e:
            return False, f"无法识别的图片文件: {str(e)}"
    
    @staticmethod
    def preprocess(image_data: bytes) -> bytes:
        """
        预处理图片
        - 调整尺寸
        - 转换格式
        - 优化质量
        """
        image = Image.open(io.BytesIO(image_data))

        # 按 EXIF 方向自动旋转（iPhone 横拍照片会变成竖向）
        image = ImageOps.exif_transpose(image)

        # 转换为RGB模式（去除alpha通道）
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # 调整尺寸
        if image.size[0] > ImageProcessor.MAX_SIZE[0] or image.size[1] > ImageProcessor.MAX_SIZE[1]:
            image.thumbnail(ImageProcessor.MAX_SIZE, Image.Resampling.LANCZOS)

        # 输出为JPEG（剥离 EXIF，含 GPS 坐标隐私问题）
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
