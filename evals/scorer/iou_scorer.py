"""IoU/mIoU 评分器"""

import random

from evals.config import METRIC_RANGES
from evals.scorer.base import BaseScorer
from evals.dataset.schemas import ImagePair


class MockIoUScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "iou"

    @property
    def description(self) -> str:
        return "IoU - 分割掩码重叠度 (mock)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        lo, hi, _ = METRIC_RANGES["iou"]
        seed = hash((self.name, input_path)) & 0xFFFFFFFF
        rng = random.Random(seed)
        return round(rng.uniform(lo + 0.3, hi), 4)


class RealIoUScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "iou"

    @property
    def description(self) -> str:
        return "IoU - 分割掩码重叠度 (real)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        raise NotImplementedError("Real IoU scorer not yet implemented")


def create_iou_scorer(use_mock: bool = True) -> BaseScorer:
    return MockIoUScorer() if use_mock else RealIoUScorer()
