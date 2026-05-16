"""结构保真评分器 — 边缘 SSIM 对比"""

import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from evals.config import METRIC_RANGES, EVALS_DIR, PROJECT_ROOT
from evals.scorer.base import BaseScorer


# 评分语义版本号：v2 起 SSIM->百分制 直接映射 [0,1]->[0,100]，
# 不再使用 (ssim+1)/2 的对称映射；与 v1 历史结果不可直接比较。
__metric_version__ = 2


def _resolve(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    if path.startswith("data/"):
        return EVALS_DIR / p
    return PROJECT_ROOT / p


def _load_gray(path: str, size=(256, 256)) -> np.ndarray:
    """以保持纵横比的方式加载灰度图：thumbnail + 中灰 letterbox 填充。

    之前 Image.resize((256,256)) 会强制拉伸非方形图，
    将横向/纵向墙线扭曲后再做 Canny+SSIM，把 resize 噪声混入"结构差异"。
    现在使用 LANCZOS 重采样按比例缩放到 fit，剩余区域用中灰 (128) 填充，
    使 input 与 output 经历相同的 letterbox 变换、SSIM 比较等价画布。
    """
    img = Image.open(_resolve(path)).convert("L")
    img.thumbnail(size, Image.LANCZOS)  # 按比例缩放，最长边 = size 对应边
    canvas = Image.new("L", size, 128)
    x = (size[0] - img.width) // 2
    y = (size[1] - img.height) // 2
    canvas.paste(img, (x, y))
    return np.array(canvas)


class MockStructuralFidelityScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "structural_fidelity"

    @property
    def description(self) -> str:
        return "结构保真 - 边缘 SSIM (mock, 百分制)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        lo, hi, _ = METRIC_RANGES["structural_fidelity"]
        seed = hash((self.name, input_path)) & 0xFFFFFFFF
        rng = random.Random(seed)
        return round(rng.uniform(lo + 30, hi * 0.98), 2)


class RealStructuralFidelityScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "structural_fidelity"

    @property
    def description(self) -> str:
        return "结构保真 - 边缘 SSIM (real, 百分制)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        gray_in = _load_gray(input_path)
        gray_out = _load_gray(output_path)

        # 边缘图
        edge_in = cv2.Canny(gray_in, 100, 200)
        edge_out = cv2.Canny(gray_out, 100, 200)

        # SSIM: 边缘 + 灰度
        ssim_edge = ssim(edge_in, edge_out, data_range=255)
        ssim_gray = ssim(gray_in, gray_out, data_range=255)

        # v2: SSIM 在自然图像上几乎总落在 [0, 1]，直接映射到 [0, 100]。
        # 之前 (ssim+1)/2*100 把 SSIM=0 也算 50/100，灾难性失败仍像及格。
        weighted = max(0.0, ssim_edge * 0.6 + ssim_gray * 0.4)
        score = weighted * 100
        return round(max(0.0, min(100.0, score)), 2)


def create_structural_fidelity_scorer(use_mock: bool = True) -> BaseScorer:
    return MockStructuralFidelityScorer() if use_mock else RealStructuralFidelityScorer()
