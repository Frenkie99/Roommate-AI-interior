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
        return [self.score(p.input_path, p.output_path, p.prompt) for p in pairs]
