"""结构保真评分器 — 边缘 SSIM 对比"""

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

        score = (ssim_edge * 0.6 + ssim_gray * 0.4 + 1) / 2 * 100  # → [0, 100]
        return round(max(0.0, min(100.0, score)), 2)


def create_structural_fidelity_scorer(use_mock: bool = True) -> BaseScorer:
    return MockStructuralFidelityScorer() if use_mock else RealStructuralFidelityScorer()
