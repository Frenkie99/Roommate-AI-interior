"""IoU/mIoU 评分器"""

import logging
import random

from evals.config import METRIC_RANGES
from evals.scorer.base import BaseScorer
from evals.dataset.schemas import ImagePair

logger = logging.getLogger(__name__)


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
    _warned = False

    def __init__(self) -> None:
        if not RealIoUScorer._warned:
            logger.warning(
                "RealIoUScorer is not yet implemented; score() will return None. "
                "Track issue #32."
            )
            RealIoUScorer._warned = True

    @property
    def name(self) -> str:
        return "iou"

    @property
    def description(self) -> str:
        return "IoU - 分割掩码重叠度 (real, 未实现)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs):
        # 返回 None 而不是 raise，避免 runner 在 USE_MOCK=False 时
        # 首对图片就 crash；缺失值由 runner / result_store 处理。
        return None


def create_iou_scorer(use_mock: bool = True) -> BaseScorer:
    return MockIoUScorer() if use_mock else RealIoUScorer()
