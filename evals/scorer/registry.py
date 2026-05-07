"""评分器注册表"""

from typing import Dict

from evals.scorer.base import BaseScorer
from evals.scorer.iou_scorer import create_iou_scorer
from evals.scorer.fid_scorer import create_fid_scorer
from evals.scorer.clip_scorer import create_clip_scorer
from evals.scorer.structural_fidelity import create_structural_fidelity_scorer
from evals.scorer.llm_judge import create_llm_judge_scorer


class ScorerRegistry:
    _scorers: Dict[str, BaseScorer] = {}

    @classmethod
    def register(cls, name: str, scorer: BaseScorer) -> None:
        cls._scorers[name] = scorer

    @classmethod
    def get(cls, name: str) -> BaseScorer:
        return cls._scorers[name]

    @classmethod
    def get_all(cls) -> Dict[str, BaseScorer]:
        return cls._scorers.copy()

    @classmethod
    def initialize(cls, use_mock: bool = True) -> None:
        cls._scorers = {}
        factories = [
            create_iou_scorer,
            create_fid_scorer,
            create_clip_scorer,
            create_structural_fidelity_scorer,
            create_llm_judge_scorer,
        ]
        for factory in factories:
            scorer = factory(use_mock=use_mock)
            cls.register(scorer.name, scorer)
