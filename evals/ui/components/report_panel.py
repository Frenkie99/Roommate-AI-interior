"""分维度聚合报告看板页 —— Eval Harness 要素⑤ Aggregator 的网页呈现。

读 eval_report.json（由 runner/aggregator 产出），把「总览 + 按维度分组」搬进看板：
带小样本 ⚠️ 标记与「组间差 vs 全体 std」噪声判定，防止把噪声读成信号。
"""

import json
import os

import pandas as pd
import streamlit as st

from evals.config import EVAL_REPORT_JSON_PATH
from evals.dataset.schemas import EvalResult
from evals.executor import aggregator


def _regenerate(store) -> None:
    """从现有 eval_results 重新聚合并落盘（免费，不打分）。"""
    doc = store.load()
    results = [EvalResult.from_dict(r) for r in doc.get("results", [])]
    report = aggregator.aggregate(results)
    md = aggregator.to_markdown(report, run_config=doc.get("metadata", {}).get("last_run"))
    aggregator.save_report(md, report)


def _dim_table(groups: dict, metric: str) -> pd.DataFrame:
    rows = []
    for key, block in groups.items():
        s = block["metrics"][metric]
        rows.append({
            "分组": f"{key} ⚠️" if block.get("small_sample") else str(key),
            "n": block["n"],
            "均值": s["mean"], "最小": s["min"], "最大": s["max"],
            "标准差": s["std"], "空值": s["null"],
        })
    df = pd.DataFrame(rows)
    return df.sort_values("均值", ascending=False, na_position="last").reset_index(drop=True)


def render_report_panel(store) -> None:
    st.subheader("分维度聚合报告")

    col_a, col_b = st.columns([1, 3])
    with col_a:
        if st.button("🔄 重新生成报告（免费，不打分）"):
            _regenerate(store)
            st.success("已从现有评测结果重新聚合。")

    if not os.path.exists(EVAL_REPORT_JSON_PATH):
        st.info("尚无报告。点上方按钮生成，或命令行跑 "
                "`python -m evals.executor.runner --report-only`。")
        return

    with open(EVAL_REPORT_JSON_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    # 本轮 run 快照（可复现信息）
    last_run = store.load().get("metadata", {}).get("last_run")
    if last_run:
        active = {k: v for k, v in (last_run.get("filters") or {}).items() if v}
        st.caption(f"最近一轮：{last_run.get('at', '?')} · 筛选 {active or '全量'} · "
                   f"新算 {last_run.get('n_scored', '?')} 条 · 错误 {last_run.get('n_errors', 0)} · "
                   f"耗时 {last_run.get('duration_sec', '?')}s")

    metrics = report.get("metrics", [])
    if not metrics:
        st.warning("报告中没有任何有分值的指标。")
        return

    st.markdown(
        f"样本数 **{report['n_results']}**\n\n"
        f"> **读数须知**：[1] ⚠️ = 小样本（n<{aggregator.SMALL_N}），只作方向参考；"
        f"[2] 组间差小于全体 std ≈ 噪声；"
        f"[3] difficulty 是**结果难度**（人工分反推），勿倒果为因。"
    )

    metric = metrics[0] if len(metrics) == 1 else st.selectbox("指标", metrics)

    # 总览
    o = report["overall"][metric]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("均值", o["mean"] if o["mean"] is not None else "N/A")
    c2.metric("最小", o["min"] if o["min"] is not None else "N/A")
    c3.metric("最大", o["max"] if o["max"] is not None else "N/A")
    c4.metric("全体标准差", o["std"] if o["std"] is not None else "N/A")

    # 分维度
    by_dim = report.get("by_dimension", {})
    if not by_dim:
        st.info("无可分组的维度。")
        return

    dim = st.selectbox("分组维度", list(by_dim.keys()),
                       format_func=lambda d: {"difficulty": "difficulty（结果难度·反推）",
                                              "intrinsic_difficulty": "intrinsic_difficulty（内在难度·看图）"}.get(d, d))
    note = aggregator.DIMENSION_NOTES.get(dim)
    if note:
        st.caption(note)

    groups = by_dim[dim]
    st.dataframe(_dim_table(groups, metric), width="stretch", hide_index=True)

    # 噪声判定：组间差（非小样本组） vs 全体 std
    big_means = [b["metrics"][metric]["mean"] for b in groups.values()
                 if not b.get("small_sample") and b["metrics"][metric]["mean"] is not None]
    overall_std = o["std"]
    if overall_std is not None and len(big_means) >= 2:
        spread = round(max(big_means) - min(big_means), 2)
        if spread < overall_std:
            st.warning(f"组间差（非小样本组）= {spread} < 全体 std {overall_std} → "
                       f"**差异在噪声量级内，不宜下结论**")
        else:
            st.success(f"组间差（非小样本组）= {spread} ≥ 全体 std {overall_std} → "
                       f"可能是真信号（仍建议点开样本复核）")
    elif len(big_means) < 2:
        st.info("非小样本组不足 2 个，本维度暂无法做组间比较。")
