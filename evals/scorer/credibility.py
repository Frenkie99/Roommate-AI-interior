"""评分器可信度度量 — 评测平台的"标尺"

核心命题（见 evals/METHODOLOGY.md 第 3 节）：评分器的价值不在"能打分"，而在"分可信"。
可信度 = 两个可量化维度：
  - 对齐度 Validity   : 自动分与人工金标准分的相关性（Spearman / Pearson / 归一化 MAE）
  - 稳定性 Reliability: 同一对图重复打分的方差（仅随机性评分器有意义，如 LLM Judge）

本模块的统计计算全部用纯标准库实现，不依赖 numpy/scipy，可在任意环境运行与验证。
仅 measure_reliability() 会真正调用评分器（懒加载，需要重依赖），其余分析只读 JSON。

命令行用法：
    python -m evals.scorer.credibility            # 打印可信度报告
"""

import json
from typing import Dict, List, Optional, Sequence


# ----------------------------- 纯标准库统计 -----------------------------

def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """皮尔逊线性相关系数；样本不足或某一序列零方差时返回 None。"""
    n = len(xs)
    if n < 2:
        return None
    mx, my = _mean(xs), _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _rank(xs: Sequence[float]) -> List[float]:
    """转换为秩，平级取平均秩（1-based）。"""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-based 平均秩
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """斯皮尔曼秩相关；对量纲与单调非线性更鲁棒，是可信度对齐的主指标。"""
    if len(xs) < 2:
        return None
    return pearson(_rank(xs), _rank(ys))


def normalized_mae(auto: Sequence[float], human: Sequence[float],
                   auto_range, human_range=(1.0, 5.0)) -> Optional[float]:
    """把两个序列各自归一化到 [0,1] 后求平均绝对误差，用于跨量纲比较绝对偏差。"""
    alo, ahi = auto_range
    hlo, hhi = human_range
    if ahi == alo or hhi == hlo:
        return None
    diffs = [
        abs((a - alo) / (ahi - alo) - (h - hlo) / (hhi - hlo))
        for a, h in zip(auto, human)
    ]
    return sum(diffs) / len(diffs)


def _round(v: Optional[float], n: int = 4) -> Optional[float]:
    return round(v, n) if v is not None else None


# ----------------------------- 对齐度分析 -----------------------------

# 每个自动评分器最该对齐的人工维度（用于报告高亮主线）
PRIMARY_AXIS = {
    "structural_fidelity": "structural",
    "llm_judge": "overall",
    "clip_score": "overall",
    "iou": "structural",
    "fid": "aesthetic",
}


def analyze(results_path: Optional[str] = None,
            gold_path: Optional[str] = None) -> dict:
    """对比 eval_results 的自动分与 gold_labels 的人工分，输出可信度报告。"""
    from evals.config import METRIC_RANGES, EVAL_RESULTS_PATH
    from evals.scorer.gold_store import GoldStore, GOLD_AXES

    rp = str(results_path or EVAL_RESULTS_PATH)
    with open(rp, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 自动分: pair_id -> {metric: value}（剔除 None）
    auto: Dict[str, Dict[str, float]] = {}
    for r in data.get("results", []):
        auto[r["pair_id"]] = {
            k: v for k, v in r.get("scores", {}).items() if v is not None
        }

    gold = GoldStore(gold_path).load()  # pair_id -> entry
    overlap = sorted(set(auto) & set(gold))

    report = {
        "n_auto": len(auto),
        "n_gold": len(gold),
        "n_overlap": len(overlap),
        "axes": GOLD_AXES,
        "scorers": {},
    }

    metric_names = sorted({m for v in auto.values() for m in v})
    for metric in metric_names:
        lo, hi, higher_better = METRIC_RANGES.get(metric, (0.0, 1.0, True))
        per_axis = {}
        for axis in GOLD_AXES:
            xs, ys = [], []
            for pid in overlap:
                a = auto[pid].get(metric)
                h = gold[pid].get("scores", {}).get(axis)
                if a is None or h is None:
                    continue
                xs.append(a)
                ys.append(h)
            if len(xs) >= 2:
                per_axis[axis] = {
                    "n": len(xs),
                    "pearson": _round(pearson(xs, ys)),
                    "spearman": _round(spearman(xs, ys)),
                    "nmae": _round(normalized_mae(xs, ys, (lo, hi))),
                }
        report["scorers"][metric] = {
            "primary_axis": PRIMARY_AXIS.get(metric),
            "higher_is_better": higher_better,
            "vs_axis": per_axis,
        }
    return report


def aligned_points(metric: str, axis: str, results_path: Optional[str] = None,
                   gold_path: Optional[str] = None) -> List[dict]:
    """取某评分器与某人工维度的成对点 [{pair_id, auto, human}]，供散点图等使用。"""
    from evals.config import EVAL_RESULTS_PATH
    from evals.scorer.gold_store import GoldStore

    with open(str(results_path or EVAL_RESULTS_PATH), "r", encoding="utf-8") as f:
        data = json.load(f)
    auto = {r["pair_id"]: r.get("scores", {}) for r in data.get("results", [])}
    gold = GoldStore(gold_path).load()

    pts = []
    for pid in sorted(set(auto) & set(gold)):
        a = auto[pid].get(metric)
        h = gold[pid].get("scores", {}).get(axis)
        if a is not None and h is not None:
            pts.append({"pair_id": pid, "auto": a, "human": h})
    return pts


# ----------------------------- 稳定性度量（按需，调真·评分器） -----------------------------

def measure_reliability(metric_name: str, pairs, repeats: int = 5,
                        use_mock: bool = False) -> List[dict]:
    """对同一批 pair 重复打分 repeats 次，统计每对的均值与样本标准差。

    仅对随机性评分器（如 LLM Judge）有意义；确定性评分器（CLIP/结构保真）方差应≈0。
    会真正调用评分器（懒加载 registry，需重依赖），故单独成函数、按需触发。
    """
    from evals.scorer.registry import ScorerRegistry

    ScorerRegistry.initialize(use_mock=use_mock)
    scorer = ScorerRegistry.get(metric_name)

    out = []
    for p in pairs:
        runs = []
        for _ in range(repeats):
            v = scorer.score(p.input_path, p.output_path, p.prompt,
                             style=p.style, room_type=p.room_type)
            if v is not None:
                runs.append(v)
        if len(runs) >= 2:
            m = _mean(runs)
            sd = (sum((x - m) ** 2 for x in runs) / (len(runs) - 1)) ** 0.5
            out.append({
                "pair_id": p.pair_id,
                "mean": _round(m),
                "std": _round(sd),
                "cv": _round(sd / m if m else None),  # 变异系数
                "runs": [_round(r) for r in runs],
            })
    return out


# ----------------------------- 命令行报告 -----------------------------

def _fmt(v: Optional[float]) -> str:
    return f"{v:+.3f}" if isinstance(v, float) else "  -  "


def print_report(report: dict) -> None:
    print("\n===== 评分器可信度报告 =====")
    print(f"自动分样本: {report['n_auto']}  人工金标准: {report['n_gold']}  "
          f"可对齐重叠: {report['n_overlap']}")
    if report["n_overlap"] < 2:
        print("\n⚠️  重叠样本 < 2，无法计算相关性。请先在「金标准标注」中打分。")
        return
    if report["n_overlap"] < 15:
        print(f"\n⚠️  重叠样本仅 {report['n_overlap']} 条，相关性估计不稳定，"
              f"建议至少标注 20-30 条。")

    axes = report["axes"]
    for metric, info in report["scorers"].items():
        primary = info.get("primary_axis")
        print(f"\n── {metric}  (主对齐维度: {primary}, "
              f"{'越高越好' if info['higher_is_better'] else '越低越好'})")
        header = f"{'人工维度':<14}{'n':>4}{'Spearman':>12}{'Pearson':>12}{'归一MAE':>12}"
        print("   " + header)
        for axis, label in axes.items():
            stats = info["vs_axis"].get(axis)
            mark = "★" if axis == primary else " "
            name = f"{mark}{label}"
            if not stats:
                print(f"   {name:<14}{'  -  ':>4}{'  -  ':>12}{'  -  ':>12}{'  -  ':>12}")
            else:
                print(f"   {name:<14}{stats['n']:>4}"
                      f"{_fmt(stats['spearman']):>12}{_fmt(stats['pearson']):>12}"
                      f"{_fmt(stats['nmae']):>12}")


if __name__ == "__main__":
    print_report(analyze())
