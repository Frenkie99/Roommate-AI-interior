"""概览图表组件"""

from typing import Any, Dict, List

import streamlit as st
import pandas as pd

from evals.config import METRIC_LABELS


def render_summary_charts(store) -> None:
    """渲染概览页：指标卡片 + 分布图"""
    data = store.load()
    results = data.get("results", [])

    if not results:
        st.info("暂无数据")
        return

    # 提取分数
    metrics_data = {}
    for r in results:
        for k, v in r.get("scores", {}).items():
            metrics_data.setdefault(k, []).append(v)

    # 指标卡片
    st.subheader("指标概览")
    cols = st.columns(len(metrics_data))
    for i, (metric, values) in enumerate(metrics_data.items()):
        with cols[i]:
            avg = sum(values) / len(values)
            mn = min(values)
            mx = max(values)
            label = METRIC_LABELS.get(metric, metric)
            st.metric(
                label=label,
                value=f"{avg:.3f}",
                delta=f"最低={mn:.3f} / 最高={mx:.3f}",
            )

    # 分布图
    st.subheader("指标分布")
    metric_names = list(metrics_data.keys())
    tab_cols = st.columns(min(len(metric_names), 3))

    for i, metric in enumerate(metric_names):
        with tab_cols[i % len(tab_cols)]:
            label = METRIC_LABELS.get(metric, metric)
            chart_data = pd.DataFrame({label: metrics_data[metric]})
            st.write(f"**{label}**")
            st.bar_chart(chart_data, height=200)

    # 标签统计
    st.subheader("标签分布")
    tag_data = {}
    for r in results:
        for tag in r.get("metadata", {}).get("tags", []):
            tag_data[tag] = tag_data.get(tag, 0) + 1

    if tag_data:
        tag_df = pd.DataFrame(list(tag_data.items()), columns=["标签", "数量"])
        tag_df = tag_df.sort_values("数量", ascending=False)
        st.dataframe(tag_df, width='stretch', hide_index=True)
