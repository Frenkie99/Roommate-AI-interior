"""评分器可信度度量 — 评测平台的"标尺"

核心命题（见 evals/METHODOLOGY.md 第 3 节）：评分器的价值不在"能打分"，而在"分可信"。
可信度 = 三个可量化维度：
  - 对齐度 Validity   : 自动分与人工金标准分的相关性（Spearman / Pearson / 归一化 MAE）
                        —— 回答"分数**排序**对不对"
  - 分类校准 Calibration（2026-07-09 新增，课程框架"把 Judge 当分类器验证"）：
                        自动判定二元化后 vs 人工二元真值的 TPR/TNR + Wilson 95% 区间
                        —— 回答"这个裁判判 **pass/fail** 判得准不准"
  - 稳定性 Reliability: 同一对图重复打分的方差（仅随机性评分器有意义，如 LLM Judge）

本模块的统计计算全部用纯标准库实现，不依赖 numpy/scipy，可在任意环境运行与验证。
仅 measure_reliability() 会真正调用评分器（懒加载，需要重依赖），其余分析只读 JSON。

命令行用法：
    python -m evals.scorer.credibility                                # 相关性对齐报告
    python -m evals.scorer.credibility --classify structural_fidelity --threshold 55
                                                                      # 分类校准报告
    python -m evals.scorer.credibility --classify structural_fidelity --threshold 55 --split dev
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


# ----------------------------- 分类统计（纯标准库） -----------------------------

def wilson_interval(k: int, n: int, z: float = 1.96) -> Optional[tuple]:
    """Wilson 95% 置信区间。小样本下比正态近似稳健得多——n≈30 时区间宽可达 ±15pp，
    所以 TPR/TNR 必须带区间报，点估计单独看没有意义。"""
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def classification_metrics(judge: Sequence[str], gold: Sequence[str]) -> dict:
    """混淆矩阵 + TPR/TNR/准确率（positive = "pass"）。

    judge/gold 为等长序列，元素 ∈ {"pass","fail"}。
      TPR = 金标准 pass 中被裁判判 pass 的比例（漏杀率的反面）
      TNR = 金标准 fail 中被裁判判 fail 的比例（误放率的反面）
    各指标附 Wilson 95% 区间。
    """
    tp = fn = tn = fp = 0
    for j, g in zip(judge, gold):
        if g == "pass":
            tp += (j == "pass")
            fn += (j != "pass")
        else:
            tn += (j == "fail")
            fp += (j != "fail")

    def _rate(k, n):
        if n == 0:
            return {"value": None, "ci": None, "k": k, "n": n}
        ci = wilson_interval(k, n)
        return {"value": _round(k / n), "ci": (_round(ci[0]), _round(ci[1])), "k": k, "n": n}

    n_all = tp + fn + tn + fp
    return {
        "n": n_all,
        "confusion": {"tp": tp, "fn": fn, "tn": tn, "fp": fp},
        "tpr": _rate(tp, tp + fn),
        "tnr": _rate(tn, tn + fp),
        "accuracy": _rate(tp + tn, n_all),
    }


def gold_binary_summary(gold_path: Optional[str] = None) -> dict:
    """金标准二元真值盘点：人工裁决 / 阈值派生 / 模糊待裁决 / 校准剔除。"""
    from evals.scorer.gold_store import GoldStore, effective_binary, is_excluded

    gold = GoldStore(gold_path).load()
    manual = derived = 0
    dist = {"pass": 0, "fail": 0}
    pending, excluded = [], []
    for pid, entry in gold.items():
        if is_excluded(entry):
            excluded.append(pid)
            continue
        verdict, source = effective_binary(entry)
        if verdict is None:
            pending.append(pid)
            continue
        dist[verdict] += 1
        if source == "manual":
            manual += 1
        else:
            derived += 1
    return {
        "n_gold": len(gold), "n_binary": manual + derived,
        "manual": manual, "derived": derived,
        "dist": dist, "pending_fuzzy": sorted(pending),
        "excluded": sorted(excluded),
    }


def classification_analysis(metric: str, threshold: float,
                            results_path: Optional[str] = None,
                            gold_path: Optional[str] = None,
                            split: Optional[str] = None) -> dict:
    """把连续自动分按阈值二元化，与金标准二元真值对齐，产出 TPR/TNR 校准报告。

    - 金标准二元 = 显式人工裁决优先，否则 overall 阈值派生；模糊未裁决 case 剔除并计数。
    - threshold：自动分 ≥ threshold 判 pass（higher_is_better=False 的指标则 ≤ 判 pass）。
    - split：可选 "fewshot"/"dev"/"test"，按 judge_split 划分过滤（test 只应在最终验收时看）。
    - 返回含 misclassified 明细（FP/FN 的 pair_id），供错误分析下钻。
    """
    from evals.config import METRIC_RANGES, EVAL_RESULTS_PATH
    from evals.scorer.gold_store import GoldStore, effective_binary

    with open(str(results_path or EVAL_RESULTS_PATH), "r", encoding="utf-8") as f:
        data = json.load(f)
    auto = {r["pair_id"]: r.get("scores", {}).get(metric)
            for r in data.get("results", [])}
    gold = GoldStore(gold_path).load()

    allowed = None
    if split:
        from evals.dataset.judge_split import pair_ids as _split_ids
        allowed = set(_split_ids(split))

    _, _, higher_better = METRIC_RANGES.get(metric, (0.0, 1.0, True))

    from evals.scorer.gold_store import is_excluded
    judge_v, gold_v, used, fuzzy_skipped = [], [], [], []
    fp_ids, fn_ids = [], []
    for pid in sorted(set(auto) & set(gold)):
        if allowed is not None and pid not in allowed:
            continue
        if is_excluded(gold[pid]):   # 评测集缺陷 case，不参与校准
            continue
        a = auto.get(pid)
        if a is None:
            continue
        gv, _src = effective_binary(gold[pid])
        if gv is None:
            fuzzy_skipped.append(pid)
            continue
        jv = "pass" if ((a >= threshold) if higher_better else (a <= threshold)) else "fail"
        judge_v.append(jv)
        gold_v.append(gv)
        used.append(pid)
        if jv == "pass" and gv == "fail":
            fp_ids.append(pid)
        elif jv == "fail" and gv == "pass":
            fn_ids.append(pid)

    report = classification_metrics(judge_v, gold_v)
    report.update({
        "metric": metric, "threshold": threshold, "split": split or "all",
        "higher_is_better": higher_better,
        "n_fuzzy_skipped": len(fuzzy_skipped), "fuzzy_skipped": fuzzy_skipped,
        "misclassified": {"fp": fp_ids, "fn": fn_ids},
        "gold_summary": gold_binary_summary(gold_path),
    })
    return report


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


def _fmt_rate(r: dict) -> str:
    if r["value"] is None:
        return "  -  "
    lo, hi = r["ci"]
    return f"{r['value']*100:5.1f}%  [{lo*100:.0f}%, {hi*100:.0f}%]  ({r['k']}/{r['n']})"


def print_classification(rep: dict) -> None:
    gs = rep["gold_summary"]
    print("\n===== 分类校准报告（TPR / TNR） =====")
    print(f"评分器: {rep['metric']}  阈值: {'≥' if rep['higher_is_better'] else '≤'}{rep['threshold']} 判 pass"
          f"  范围: {rep['split']}")
    print(f"金标准二元真值: {gs['n_binary']}/{gs['n_gold']}"
          f"（人工裁决 {gs['manual']} + 阈值派生 {gs['derived']}；"
          f"pass {gs['dist']['pass']} / fail {gs['dist']['fail']}）")
    if gs["pending_fuzzy"]:
        print(f"⚠️  {len(gs['pending_fuzzy'])} 条模糊地带（overall=3）待人工二元裁决，本次已剔除: "
              f"{', '.join(gs['pending_fuzzy'])}")
    c = rep["confusion"]
    print(f"\n混淆矩阵 (n={rep['n']}):")
    print(f"                裁判=pass   裁判=fail")
    print(f"  金标准=pass   TP={c['tp']:<8}  FN={c['fn']}")
    print(f"  金标准=fail   FP={c['fp']:<8}  TN={c['tn']}")
    print(f"\n  TPR (pass召回): {_fmt_rate(rep['tpr'])}")
    print(f"  TNR (fail召回): {_fmt_rate(rep['tnr'])}")
    print(f"  准确率        : {_fmt_rate(rep['accuracy'])}")
    if rep["misclassified"]["fp"] or rep["misclassified"]["fn"]:
        print(f"\n  误判明细（供错误分析）:")
        if rep["misclassified"]["fp"]:
            print(f"    FP（金标准fail被判pass）: {', '.join(rep['misclassified']['fp'])}")
        if rep["misclassified"]["fn"]:
            print(f"    FN（金标准pass被判fail）: {', '.join(rep['misclassified']['fn'])}")
    print("\n  读数须知: n 小时区间宽是常态；结论只用于「过/不过门槛」判定，不用于版本间精细排序。")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="评分器可信度报告")
    ap.add_argument("--classify", metavar="METRIC",
                    help="分类校准模式：指定评分器名（如 structural_fidelity）")
    ap.add_argument("--threshold", type=float, help="二元化阈值（classify 模式必填）")
    ap.add_argument("--split", choices=["fewshot", "dev", "test"],
                    help="按 judge_split 划分过滤（test 只应在最终验收时使用）")
    args = ap.parse_args()

    if args.classify:
        if args.threshold is None:
            ap.error("--classify 模式需要 --threshold")
        print_classification(classification_analysis(
            args.classify, args.threshold, split=args.split))
    else:
        print_report(analyze())
