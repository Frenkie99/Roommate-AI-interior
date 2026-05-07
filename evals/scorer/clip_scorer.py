"""CLIP Score 评分器 — 图像间语义相似度"""

import random
from pathlib import Path

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from evals.config import METRIC_RANGES, EVALS_DIR, PROJECT_ROOT
from evals.scorer.base import BaseScorer

# 模型单例
_model = None
_processor = None


def _load_clip():
    global _model, _processor
    if _model is None:
        _processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        _model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _model.eval()
    return _model, _processor


def _resolve(path: str) -> Path:
    """将 metadata 中的相对路径转为绝对路径"""
    p = Path(path)
    if p.is_absolute():
        return p
    # input_path 相对于 evals/，output_path 相对于项目根目录
    if path.startswith("data/"):
        return EVALS_DIR / p
    return PROJECT_ROOT / p


class MockCLIPScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "clip_score"

    @property
    def description(self) -> str:
        return "CLIP Score - 图像语义相似度 (mock)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        lo, hi, _ = METRIC_RANGES["clip_score"]
        seed = hash((self.name, input_path)) & 0xFFFFFFFF
        rng = random.Random(seed)
        return round(rng.uniform(lo + 0.2, hi * 0.95), 4)


class RealCLIPScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "clip_score"

    @property
    def description(self) -> str:
        return "CLIP Score - 图像语义相似度 (real)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        model, processor = _load_clip()

        img_in = Image.open(_resolve(input_path)).convert("RGB")
        img_out = Image.open(_resolve(output_path)).convert("RGB")

        inputs = processor(images=[img_in, img_out], return_tensors="pt", padding=True)
        with torch.no_grad():
            feats = model.get_image_features(**inputs)
        feats = feats / feats.norm(dim=-1, keepdim=True)
        sim = (feats[0] @ feats[1]).item()
        return round(max(0.0, min(1.0, (sim + 1) / 2)), 4)  # 归一化到 [0, 1]


def create_clip_scorer(use_mock: bool = True) -> BaseScorer:
    return MockCLIPScorer() if use_mock else RealCLIPScorer()
