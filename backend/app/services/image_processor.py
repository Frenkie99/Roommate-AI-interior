"""
图片处理服务
负责图片的预处理和后处理
"""

from PIL import Image
import io
from typing import Tuple


class ImageProcessor:
    """图片处理器"""
    
    # 支持的图片格式
    SUPPORTED_FORMATS = ["PNG", "JPEG", "JPG"]
    
    # 最大图片尺寸
    MAX_SIZE = (2048, 2048)
    
    # 最大文件大小 (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    @staticmethod
    def validate_image(image_data: bytes) -> Tuple[bool, str]:
        """
        验证图片是否有效
        
        Returns:
            (是否有效, 错误信息)
        """
        if len(image_data) > ImageProcessor.MAX_FILE_SIZE:
            return False, "图片文件过大，请上传小于10MB的图片"
        
        try:
            image = Image.open(io.BytesIO(image_data))
            if image.format.upper() not in ImageProcessor.SUPPORTED_FORMATS:
                return False, f"不支持的图片格式，请上传 PNG 或 JPG 格式"
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
        
        # 转换为RGB模式（去除alpha通道）
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        
        # 调整尺寸
        if image.size[0] > ImageProcessor.MAX_SIZE[0] or image.size[1] > ImageProcessor.MAX_SIZE[1]:
            image.thumbnail(ImageProcessor.MAX_SIZE, Image.Resampling.LANCZOS)
        
        # 输出为JPEG
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=90)
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
