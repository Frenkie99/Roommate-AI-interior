"""评分器注册表"""

from typing import Dict

from evals.scorer.base import BaseScorer
from evals.scorer.structural_fidelity import create_structural_fidelity_scorer

# 已退役评分器（见 PROGRESS.md / METHODOLOGY.md 第8节）：
#   - clip_score：vs 人工美学 Spearman -0.31，显著负相关 = 反指标，图-图相似度评毛坯→精装语义反（2026-06-21）。
#   - llm_judge ：盲评（只喂文本不看图），全维度无有效对齐 = 噪声（2026-06-21）。
#   - iou / fid ：从未实现真值——Real 桩 score() 直接返回 None，Mock 用随机种子伪造分；
#                 从未对金标准验证、也从不在 eval_results.json 出现。注册它们只会在 runner 重跑时
#                 往数据里注入假分/null，违背「平台与判决一致」，故退役（2026-06-25）。
# 代码文件 clip_scorer.py / llm_judge.py / iou_scorer.py / fid_scorer.py 保留备查，但不再注册。
# clip 退役后 torch 依赖随之解除；llm_judge 的"看图"重做方案见 VISION_JUDGE_DESIGN.md（阶段3）。


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
            create_structural_fidelity_scorer,
        ]
        for factory in factories:
            scorer = factory(use_mock=use_mock)
            cls.register(scorer.name, scorer)
