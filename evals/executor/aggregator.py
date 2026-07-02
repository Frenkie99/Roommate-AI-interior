"""结果聚合 Aggregator（Eval Harness 五大要素之⑤）

汇总所有 case 的分数，并**按维度分组**（split / room_type / difficulty /
intrinsic_difficulty / style / tags），直击课程要点：
  「按字段筛选、分组查看，降低人脑判断众多输出好坏的难度」。

产出两份：eval_report.md（人读）+ eval_report.json（程序/看板读）。
只做聚合，不打分、不改评测数据。
"""

import json
import statistics
from typing import Any, Dict, List, Optional

from evals.config import EVAL_REPORT_MD_PATH, EVAL_REPORT_JSON_PATH
from evals.dataset.schemas import EvalResult

# 分组维度：既是数据集的输入属性/富化标签，也是失败地图的切片轴。
# tags 是多值（一个 case 可命中多个标签），单独处理。
GROUP_DIMENSIONS = ["split", "room_type", "difficulty", "intrinsic_difficulty", "style"]

# 维度语义注解——防倒果为因：difficulty 是「结果难度」(人工分反推)，不是输入属性
DIMENSION_NOTES = {
    "difficulty": "结果难度：由人工 overall 反推，属「模型表现」而非输入属性，勿倒果为因",
    "intrinsic_difficulty": "内在难度：看图判定的房间固有难度，是输入属性",
}

# 小样本阈值：组内样本数低于此值时标 ⚠️，均值仅作方向性参考
SMALL_N = 5


def _summarize(values: List[Any]) -> Dict[str, Any]:
    """对一组分值出统计量；None（评分器报错/缺分）计入 null，不参与均值。"""
    nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    n_null = len(values) - len(nums)
    if not nums:
        return {"n": len(values), "scored": 0, "null": n_null,
                "mean": None, "min": None, "max": None, "std": None}
    return {
        "n": len(values),
        "scored": len(nums),
        "null": n_null,
        "mean": round(sum(nums) / len(nums), 4),
        "min": round(min(nums), 4),
        "max": round(max(nums), 4),
        "std": round(statistics.pstdev(nums), 4) if len(nums) > 1 else 0.0,
    }


def _group_block(results: List[EvalResult], metrics: List[str]) -> Dict[str, Any]:
    return {"n": len(results),
            "small_sample": len(results) < SMALL_N,
            "metrics": {m: _summarize([r.scores.get(m) for r in results]) for m in metrics}}


def aggregate(results: List[EvalResult],
              metrics: Optional[List[str]] = None) -> Dict[str, Any]:
    """把结果聚合成 {总览 + 各维度分组} 的结构化字典。"""
    results = list(results)
    if metrics is None:
        metrics = sorted({k for r in results for k, v in r.scores.items() if v is not None})

    report: Dict[str, Any] = {
        "n_results": len(results),
        "metrics": metrics,
        "overall": {m: _summarize([r.scores.get(m) for r in results]) for m in metrics},
        "by_dimension": {},
    }

    for dim in GROUP_DIMENSIONS:
        groups: Dict[str, List[EvalResult]] = {}
        for r in results:
            key = r.metadata.get(dim)
            key = key if key not in (None, "") else "<空>"
            groups.setdefault(key, []).append(r)
        if len(groups) <= 1 and "<空>" in groups:
            continue  # 该维度全空，跳过不占版面
        report["by_dimension"][dim] = {
            k: _group_block(rs, metrics) for k, rs in sorted(groups.items(), key=lambda kv: str(kv[0]))
        }

    # tags：多值维度，一个 case 计入其每个标签
    tag_groups: Dict[str, List[EvalResult]] = {}
    for r in results:
        for t in (r.metadata.get("tags") or []):
            tag_groups.setdefault(t, []).append(r)
    if tag_groups:
        report["by_dimension"]["tags"] = {
            t: _group_block(rs, metrics) for t, rs in sorted(tag_groups.items())
        }

    return report


def _fmt(x: Any) -> str:
    return "N/A" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x))


def to_markdown(report: Dict[str, Any], run_config: Optional[Dict[str, Any]] = None) -> str:
    lines: List[str] = ["# 评测聚合报告"]

    if run_config:
        f = run_config.get("filters", {}) or {}
        active = {k: v for k, v in f.items() if v}
        lines.append("")
        lines.append(f"- 运行时间：{run_config.get('at', '?')}")
        lines.append(f"- 筛选条件：{active or '全量'}")
        lines.append(f"- 指标：{', '.join(run_config.get('metrics', []))}"
                     + ("（mock）" if run_config.get("use_mock") else ""))
        snap = []
        if run_config.get("n_scored") is not None:
            snap.append(f"本次新算 {run_config['n_scored']} 条")
        if run_config.get("n_errors"):
            snap.append(f"评分错误 {run_config['n_errors']} 个")
        if run_config.get("duration_sec") is not None:
            snap.append(f"耗时 {run_config['duration_sec']}s")
        if snap:
            lines.append(f"- 本轮：{' · '.join(snap)}")

    metrics = report["metrics"]
    lines.append("")
    lines.append(f"样本数：**{report['n_results']}** · 指标：{', '.join(metrics) or '（无）'}")

    # 读数护栏——报告是「下结论的界面」，必须自带防误读说明
    lines.append("")
    lines.append("> **读数须知**：")
    lines.append(f"> [1] 组名带 ⚠️ = 小样本（n<{SMALL_N}），均值仅方向性参考，不作结论；")
    lines.append("> [2] 各表附「组间差 vs 全体标准差」——组间差小于全体 std 时，差异大概率是噪声；")
    lines.append("> [3] difficulty 是**结果难度**（人工分反推），解读时勿倒果为因（「hard 组分低」是定义使然）。")

    # 总览
    lines.append("\n## 总览")
    lines.append("| 指标 | n | 均值 | 最小 | 最大 | 标准差 | 空值 |")
    lines.append("|---|---|---|---|---|---|---|")
    for m in metrics:
        s = report["overall"][m]
        lines.append(f"| {m} | {s['n']} | {_fmt(s['mean'])} | {_fmt(s['min'])} | "
                     f"{_fmt(s['max'])} | {_fmt(s['std'])} | {s['null']} |")

    # 分维度：每个维度 × 每个指标一张表
    for dim, groups in report["by_dimension"].items():
        for m in metrics:
            note = DIMENSION_NOTES.get(dim)
            lines.append(f"\n## 按 {dim} 分组 — {m}")
            if note:
                lines.append(f"> {note}")
            lines.append(f"| {dim} | n | 均值 | 最小 | 最大 | 标准差 | 空值 |")
            lines.append("|---|---|---|---|---|---|---|")
            # 按均值降序排，最烂的一眼可见（均值 None 排最后）；小样本组标 ⚠️
            def sort_key(item):
                s = item[1]["metrics"][m]
                return (s["mean"] is None, -(s["mean"] or 0))
            for key, block in sorted(groups.items(), key=sort_key):
                s = block["metrics"][m]
                label = f"{key} ⚠️" if block.get("small_sample") else str(key)
                lines.append(f"| {label} | {block['n']} | {_fmt(s['mean'])} | {_fmt(s['min'])} | "
                             f"{_fmt(s['max'])} | {_fmt(s['std'])} | {s['null']} |")
            # 噪声提示：组间均值差 vs 全体 std（只看非小样本组，够不上就直说没法比）
            overall_std = report["overall"][m]["std"]
            big_means = [b["metrics"][m]["mean"] for b in groups.values()
                         if not b.get("small_sample") and b["metrics"][m]["mean"] is not None]
            if overall_std is not None and len(big_means) >= 2:
                spread = round(max(big_means) - min(big_means), 2)
                verdict = ("**差异在噪声量级内，不宜下结论**" if spread < overall_std
                           else "组间差超过全体 std，可能是真信号（仍建议复核样本）")
                lines.append(f"\n组间差（非小样本组）= {spread}，全体 std = {_fmt(overall_std)} → {verdict}")
            elif len(big_means) < 2:
                lines.append(f"\n非小样本组不足 2 个，本维度暂无法做组间比较。")

    return "\n".join(lines) + "\n"


def save_report(md: str, report: Dict[str, Any],
                md_path: Optional[str] = None, json_path: Optional[str] = None) -> str:
    md_path = md_path or str(EVAL_REPORT_MD_PATH)
    json_path = json_path or str(EVAL_REPORT_JSON_PATH)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return md_path
