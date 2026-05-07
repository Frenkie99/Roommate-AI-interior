"""FID 评分器"""

import random

from evals.config import METRIC_RANGES
from evals.scorer.base import BaseScorer


class MockFIDScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "fid"

    @property
    def description(self) -> str:
        return "FID - 生成图像真实感 (mock, 越低越好)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        lo, hi, _ = METRIC_RANGES["fid"]
        seed = hash((self.name, input_path)) & 0xFFFFFFFF
        rng = random.Random(seed)
        return round(rng.uniform(lo + 10, hi * 0.8), 2)


class RealFIDScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "fid"

    @property
    def description(self) -> str:
        return "FID - 生成图像真实感 (real)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        raise NotImplementedError("Real FID scorer not yet implemented")


def create_fid_scorer(use_mock: bool = True) -> BaseScorer:
    return MockFIDScorer() if use_mock else RealFIDScorer()
