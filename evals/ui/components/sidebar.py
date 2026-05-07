"""侧边栏筛选组件"""

from typing import Dict, List, Optional

import streamlit as st

from evals.config import METRIC_RANGES, METRIC_LABELS
from evals.dataset.loader import DatasetLoader


def render_sidebar(loader: DatasetLoader) -> Dict:
    """渲染侧边栏，返回筛选条件字典"""
    st.sidebar.header("筛选条件")

    filters = {}

    # 标签
    all_tags = loader.get_all_tags()
    filters["tags"] = st.sidebar.multiselect("标签", all_tags, default=[])

    # 风格
    all_styles = loader.get_all_styles()
    filters["style"] = st.sidebar.selectbox("风格", ["全部"] + all_styles, index=0)

    # 房间类型
    all_room_types = loader.get_all_room_types()
    filters["room_type"] = st.sidebar.selectbox("房间类型", ["全部"] + all_room_types, index=0)

    # 分数阈值
    st.sidebar.subheader("分数阈值")
    for metric, (lo, hi, higher_better) in METRIC_RANGES.items():
        label = METRIC_LABELS.get(metric, metric)
        default_val = lo
        if metric == "fid":
            label = f"{label}（≤上限）"
            default_val = hi
        else:
            label = f"{label}（≥下限）"

        filters[f"min_{metric}"] = st.sidebar.slider(
            label,
            min_value=float(lo),
            max_value=float(hi),
            value=float(default_val),
            step=0.01,
        )

    return filters
