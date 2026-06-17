"""评分器可信度面板 — 自动分与人工金标准的对齐度 + 稳定性

展示 evals/scorer/credibility.py 的分析结果：
- 对齐度：每个评分器 vs 各人工维度的 Spearman / Pearson / 归一化 MAE
- 散点：所选评分器 vs 其主对齐维度的成对点
- 稳定性：按需对 LLM Judge 等随机性评分器重复打分，量化方差
"""

import streamlit as st
import pandas as pd

from evals.config import METRIC_LABELS
from evals.scorer import credibility


def _corr_badge(v):
    """把相关系数转成直观档位文字。"""
    if v is None:
        return "—"
    a = abs(v)
    level = "强" if a >= 0.7 else "中" if a >= 0.4 else "弱"
    return f"{v:+.3f}（{level}）"


def render_credibility_panel(loader) -> None:
    st.subheader("评分器可信度")
    st.caption(
        "可信度 = 对齐度（与人工金标准的相关性）+ 稳定性（重复打分的方差）。"
        "Spearman 是主指标（对量纲/非线性鲁棒）；归一 MAE 越小越好。"
    )

    report = credibility.analyze()
    o = report["n_overlap"]
    m1, m2, m3 = st.columns(3)
    m1.metric("自动分样本", report["n_auto"])
    m2.metric("人工金标准", report["n_gold"])
    m3.metric("可对齐重叠", o)

    if o < 2:
        st.info("重叠样本 < 2，无法计算相关性。请先到「金标准标注」给若干样本打分。")
        return
    if o < 15:
        st.warning(f"重叠样本仅 {o} 条，相关性估计不稳定，建议标到 20-30 条再下结论。")

    axes = report["axes"]

    # ---- 对齐度表 ----
    st.markdown("#### 对齐度（Validity）")
    for metric, info in report["scorers"].items():
        primary = info.get("primary_axis")
        label = METRIC_LABELS.get(metric, metric)
        direction = "越高越好" if info["higher_is_better"] else "越低越好"
        st.markdown(f"**{label}** · `{metric}` — 主对齐维度: "
                    f"{axes.get(primary, primary)}（{direction}）")

        rows = []
        for axis, axis_label in axes.items():
            stats = info["vs_axis"].get(axis)
            rows.append({
                "人工维度": ("★ " if axis == primary else "") + axis_label,
                "n": stats["n"] if stats else 0,
                "Spearman": _corr_badge(stats["spearman"]) if stats else "—",
                "Pearson": _corr_badge(stats["pearson"]) if stats else "—",
                "归一MAE": f"{stats['nmae']:.3f}" if stats and stats["nmae"] is not None else "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # 主维度散点
        if primary and info["vs_axis"].get(primary):
            pts = credibility.aligned_points(metric, primary)
            if pts:
                df = pd.DataFrame([{"人工分": p["human"], "自动分": p["auto"]} for p in pts])
                st.scatter_chart(df, x="人工分", y="自动分", height=240)
        st.divider()

    # ---- 稳定性 ----
    st.markdown("#### 稳定性（Reliability）")
    st.caption("对随机性评分器（如 LLM Judge）重复打分，统计标准差/变异系数。"
               "确定性评分器（CLIP/结构保真）方差应≈0。注意：会真实调用评分器与外部 API。")
    rc1, rc2, rc3 = st.columns([2, 1, 1])
    metric_opts = list(report["scorers"].keys())
    with rc1:
        sel = st.selectbox("评分器", metric_opts,
                           index=metric_opts.index("llm_judge") if "llm_judge" in metric_opts else 0)
    with rc2:
        repeats = st.number_input("重复次数", 2, 10, 3)
    with rc3:
        n_sample = st.number_input("抽样对数", 1, 30, 5)

    if st.button("测量稳定性"):
        pairs = loader.load()[: int(n_sample)]
        with st.spinner(f"对 {len(pairs)} 对图各打分 {repeats} 次…"):
            try:
                rows = credibility.measure_reliability(sel, pairs, repeats=int(repeats),
                                                       use_mock=False)
            except Exception as e:
                st.error(f"稳定性测量失败（评分器依赖或 API 未就绪）：{e}")
                rows = None
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            mean_std = sum(r["std"] for r in rows) / len(rows)
            st.metric("平均标准差", f"{mean_std:.4f}")
        elif rows is not None:
            st.info("没有可用的重复打分结果（评分器可能返回 None）。")
