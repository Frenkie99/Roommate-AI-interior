"""LLM-as-Judge 评分器 — 基于 DeepSeek 文本评估"""

import json
import os
import random
import re

import httpx

from evals.config import METRIC_RANGES
from evals.scorer.base import BaseScorer

# API 配置
_LLM_BASE = "https://api.apiyi.com"
_LLM_MODEL = "deepseek-chat"


def _call_deepseek(prompt: str) -> str:
    key = os.getenv("LLM_APIYI_KEY")
    if not key:
        raise RuntimeError("LLM_APIYI_KEY not set")
    resp = httpx.post(
        f"{_LLM_BASE}/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": _LLM_MODEL,
            "messages": [
                {"role": "system", "content": "你是专业室内设计评审专家。只输出 JSON，不要解释。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 200,
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_score(text: str) -> float:
    try:
        data = json.loads(text)
        return float(data.get("score", 3.0))
    except (json.JSONDecodeError, ValueError):
        m = re.search(r"(\d+(?:\.\d+)?)", text)
        return float(m.group(1)) if m else 3.0


_JUDGE_TEMPLATE = """请根据以下信息评估 AI 室内设计生成质量。

风格: {style}
房间类型: {room_type}
生成提示词摘要: {prompt}

评分标准 (1-5 分):
- 5: 设计专业、风格准确、空间利用合理
- 4: 整体良好、风格基本准确
- 3: 一般水平、有明显可改进之处
- 2: 较差、风格混乱或空间不协调
- 1: 很差、完全不符合要求

输出格式: {{"score": <1-5>, "reason": "<一句话理由>"}}"""


class MockLLMJudgeScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "llm_judge"

    @property
    def description(self) -> str:
        return "LLM-as-Judge - 设计质量综合评分 (mock, 1-5)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        lo, hi, _ = METRIC_RANGES["llm_judge"]
        seed = hash((self.name, input_path)) & 0xFFFFFFFF
        rng = random.Random(seed)
        return round(rng.uniform(lo + 0.5, hi), 2)


class RealLLMJudgeScorer(BaseScorer):
    @property
    def name(self) -> str:
        return "llm_judge"

    @property
    def description(self) -> str:
        return "LLM-as-Judge - 设计质量综合评分 (real, 1-5)"

    def score(self, input_path: str, output_path: str,
              prompt: str = "", **kwargs) -> float:
        style = kwargs.get("style", "unknown")
        room_type = kwargs.get("room_type", "unknown")
        prompt_summary = (prompt or "")[:300]

        user_msg = _JUDGE_TEMPLATE.format(
            style=style, room_type=room_type, prompt=prompt_summary
        )
        try:
            resp_text = _call_deepseek(user_msg)
            score = _parse_score(resp_text)
            return round(max(1.0, min(5.0, score)), 2)
        except Exception:
            return 3.0  # fallback


def create_llm_judge_scorer(use_mock: bool = True) -> BaseScorer:
    return MockLLMJudgeScorer() if use_mock else RealLLMJudgeScorer()
