"""结构保真评分器 — 低分辨率布局 SSIM（经消融实验选定）

迭代记录（见 evals/scorer/structural_ablation.py、PROGRESS.md 阶段 2）：
旧版 = 0.6*Canny边缘SSIM + 0.4*灰度SSIM，vs 人工结构金标准仅 Spearman +0.170（未达显著）。
85 条金标准消融发现：Canny 边缘 SSIM 几乎零相关（+0.08）——好装修会新增大量家具/装饰边缘，
把 Canny 淹没，根本没在测建筑结构。而 64×64 低分辨率灰度 SSIM（粗布局明暗块）= +0.417，
对家具增减鲁棒，是现版的 2.5 倍。故改用低分辨率 SSIM 单度量。
"""

import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from evals.config import METRIC_RANGES, EVALS_DIR, PROJECT_ROOT
from evals.scorer.base import BaseScorer


def _resolve(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    if path.startswith("data/"):
        return EVALS_DIR / p
    return PROJECT_ROOT / p


def _load_gray(path: str, size=(256, 256)) -> np.ndarray:
    img = Image.open(_resolve(path)).convert("RGB")
    img = img.resize(size)
    arr = np.array(img)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)


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
        return "结构保真 - 低分辨率布局 SSIM (real, 百分制)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        gray_in = _load_gray(input_path)    # 256x256 灰度
        gray_out = _load_gray(output_path)

        # 降到 64×64：只比「粗布局/明暗块」（墙体走向、门窗位置、户型几何），
        # 抹掉家具/装饰细节，对家具增减鲁棒。消融实验证明此度量对齐人工结构判断最佳。
        a = cv2.resize(gray_in, (64, 64))
        b = cv2.resize(gray_out, (64, 64))
        s = ssim(a, b, data_range=255)  # [-1, 1]，本场景多为正

        score = (s + 1) / 2 * 100  # → [0, 100]
        return round(max(0.0, min(100.0, score)), 2)


def create_structural_fidelity_scorer(use_mock: bool = True) -> BaseScorer:
    return MockStructuralFidelityScorer() if use_mock else RealStructuralFidelityScorer()
