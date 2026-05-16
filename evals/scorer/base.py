"""评分器基类"""

from abc import ABC, abstractmethod
from typing import List

from evals.dataset.schemas import ImagePair


class BaseScorer(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @abstractmethod
    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        ...

    def score_batch(self, pairs: List[ImagePair]) -> List[float]:
        # 透传 style / room_type / tags 等元数据，避免 LLM Judge 等
        # 依赖元数据的 scorer 在 batch 路径下悄无声息退化（issue #37）。
        # 用 getattr(..., None) 防御不同 schema 版本缺字段。
        return [
            self.score(
                p.input_path,
                p.output_path,
                p.prompt,
                style=getattr(p, "style", None),
                room_type=getattr(p, "room_type", None),
                tags=getattr(p, "tags", None),
            )
            for p in pairs
        ]
