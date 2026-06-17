"""人工金标准标注存储 — 评分器可信度度量的真值来源

人工金标准是度量评分器可信度的唯一真值（见 evals/METHODOLOGY.md 第 3 节）。
标注采用可解释的 1-5 分制，覆盖三个核心维度 + 综合：
  - structural : 结构保真（墙/窗/承重等硬结构是否被保留）
  - aesthetic  : 美学质量（设计/配色/质感）
  - instruction: 指令遵循（风格/房型/需求是否匹配）
  - overall    : 综合主观评价

纯标准库实现，不依赖 numpy/pandas/streamlit，便于在任意环境运行与验证。
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional

from evals.config import GOLD_LABELS_PATH

# 人工标注维度（key -> 中文显示名），1-5 分制
GOLD_AXES = {
    "structural": "结构保真",
    "aesthetic": "美学质量",
    "instruction": "指令遵循",
    "overall": "综合",
}
GOLD_SCALE = (1.0, 5.0)


class GoldStore:
    """金标准标注的读写，按 pair_id 去重 upsert。"""

    def __init__(self, path: Optional[str] = None):
        self.path = str(path or GOLD_LABELS_PATH)

    def load(self) -> Dict[str, dict]:
        """返回 {pair_id: label_entry}；文件不存在或损坏时返回空字典。"""
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                return {}
        return {e["pair_id"]: e for e in data.get("labels", []) if "pair_id" in e}

    def get(self, pair_id: str) -> Optional[dict]:
        return self.load().get(pair_id)

    def upsert(self, pair_id: str, scores: Dict[str, float],
               labeler: str = "", notes: str = "") -> None:
        """新增或更新一条标注。scores 仅保留 GOLD_AXES 中的合法维度。"""
        labels = self.load()
        clean = {k: float(v) for k, v in scores.items() if k in GOLD_AXES}
        labels[pair_id] = {
            "pair_id": pair_id,
            "scores": clean,
            "labeler": labeler,
            "labeled_at": datetime.now().isoformat(),
            "notes": notes,
        }
        self._save(labels)

    def delete(self, pair_id: str) -> bool:
        labels = self.load()
        if pair_id in labels:
            del labels[pair_id]
            self._save(labels)
            return True
        return False

    def _save(self, labels: Dict[str, dict]) -> None:
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "total": len(labels),
            "axes": GOLD_AXES,
            "labels": list(labels.values()),
        }
        # 原子写入：先写临时文件再 rename，避免中途崩溃损坏数据
        tmp_path = self.path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise
