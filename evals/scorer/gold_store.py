"""人工金标准标注存储 — 评分器可信度度量的真值来源

人工金标准是度量评分器可信度的唯一真值（见 evals/METHODOLOGY.md 第 3 节）。
标注采用可解释的 1-5 分制，覆盖三个核心维度 + 综合：
  - structural : 结构保真（墙/窗/承重等硬结构是否被保留）
  - aesthetic  : 美学质量（设计/配色/质感）
  - instruction: 指令遵循（风格/房型/需求是否匹配）
  - overall    : 综合主观评价

二元判定（2026-07-09 新增，课程框架「把 Judge 当分类器验证」的真值侧）：
  - Likert 分继续喂相关性对齐（Spearman）；TPR/TNR 校准需要二元 pass/fail 真值。
  - 不重标 85 条：从 overall 阈值派生（≥4 → pass，≤2 → fail）；
    overall=3 是模糊地带，需在标注 UI 人工二元裁决（binary_verdict 显式字段优先于派生）。
  - critique：一句话"为什么过/不过"，喂 few-shot 池与错误分析（Hamel: Likert 缺 critique 之补）。

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

# 二元判定的阈值派生（overall 维度）：≥PASS_MIN → pass；≤FAIL_MAX → fail；两者之间=模糊地带
BINARY_PASS_MIN = 4.0
BINARY_FAIL_MAX = 2.0


def derive_binary(scores: Optional[Dict[str, float]]) -> Optional[str]:
    """从 Likert overall 阈值派生二元判定；模糊地带（如 overall=3）或缺分返回 None。"""
    ov = (scores or {}).get("overall")
    if ov is None:
        return None
    if ov >= BINARY_PASS_MIN:
        return "pass"
    if ov <= BINARY_FAIL_MAX:
        return "fail"
    return None


def effective_binary(entry: Optional[dict]) -> tuple:
    """取一条金标准的二元真值：显式人工裁决（binary_verdict）优先，否则阈值派生。

    返回 (verdict, source)：
      verdict ∈ {"pass", "fail", None}
      source  ∈ {"manual"(人工裁决), "derived"(阈值派生), None(模糊待裁决/无标注)}
    """
    if not entry:
        return None, None
    bv = entry.get("binary_verdict")
    if bv in ("pass", "fail"):
        return bv, "manual"
    d = derive_binary(entry.get("scores"))
    return d, ("derived" if d else None)


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
               labeler: str = "", notes: str = "",
               binary_verdict: Optional[str] = None,
               critique: Optional[str] = None) -> None:
        """新增或更新一条标注。scores 仅保留 GOLD_AXES 中的合法维度。

        binary_verdict：显式二元裁决。"pass"/"fail" 写入；"derived" 清除显式裁决
        （回退到阈值派生）；None 保留旧值不动。critique 同理（None 保留旧值）。
        """
        labels = self.load()
        old = labels.get(pair_id, {})
        clean = {k: float(v) for k, v in scores.items() if k in GOLD_AXES}
        entry = {
            "pair_id": pair_id,
            "scores": clean,
            "labeler": labeler,
            "labeled_at": datetime.now().isoformat(),
            "notes": notes,
        }
        # 二元裁决：显式设置 / 清除 / 保留
        if binary_verdict in ("pass", "fail"):
            entry["binary_verdict"] = binary_verdict
        elif binary_verdict == "derived":
            pass  # 不写字段 = 清除显式裁决
        elif old.get("binary_verdict") in ("pass", "fail"):
            entry["binary_verdict"] = old["binary_verdict"]
        # critique：None 保留旧值；空串=显式清空
        if critique is not None:
            if critique.strip():
                entry["critique"] = critique.strip()
        elif old.get("critique"):
            entry["critique"] = old["critique"]
        labels[pair_id] = entry
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
