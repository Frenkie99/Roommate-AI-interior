"""可排序数据表组件"""

from typing import Dict, List, Any

import pandas as pd
import streamlit as st

from evals.config import METRIC_RANGES, METRIC_LABELS
from evals.executor.result_store import ResultStore


# 列名中文映射
COLUMN_NAMES = {
    "pair_id": "样本编号",
    "style": "风格",
    "room_type": "房间类型",
    "tags": "标签",
    "split": "分片",
    "iou": "IoU 分割精度",
    "fid": "FID 图像真实感",
    "clip_score": "CLIP 语义匹配度",
    "structural_fidelity": "结构保真度",
    "llm_judge": "LLM 综合评分",
    "notes": "备注",
}


def _apply_filters(df: pd.DataFrame, filters: Dict) -> pd.DataFrame:
    """应用侧边栏筛选条件"""
    if filters.get("tags"):
        df = df[df["tags"].apply(lambda t: any(tag in t for tag in filters["tags"]))]

    if filters.get("style") and filters["style"] != "全部":
        df = df[df["style"] == filters["style"]]

    if filters.get("room_type") and filters["room_type"] != "全部":
        df = df[df["room_type"] == filters["room_type"]]

    # 分数阈值
    for metric, (lo, hi, higher_better) in METRIC_RANGES.items():
        if metric in df.columns:
            threshold = filters.get(f"min_{metric}", lo)
            if metric == "fid":
                df = df[df[metric] <= threshold]
            else:
                df = df[df[metric] >= threshold]

    return df


def render_data_table(store: ResultStore, filters: Dict) -> pd.DataFrame:
    """渲染可排序数据表，返回筛选后的 DataFrame"""
    data = store.load()
    results = data.get("results", [])

    if not results:
        st.warning("暂无评测结果")
        return pd.DataFrame()

    rows = []
    for r in results:
        row = {
            "pair_id": r["pair_id"],
            "style": r.get("metadata", {}).get("style", ""),
            "room_type": r.get("metadata", {}).get("room_type", ""),
            "tags": r.get("metadata", {}).get("tags", []),
            "split": r.get("metadata", {}).get("split", ""),
        }
        row.update(r.get("scores", {}))
        rows.append(row)

    df = pd.DataFrame(rows)
    df = _apply_filters(df, filters)

    # 重命名列为中文
    df_display = df.rename(columns=COLUMN_NAMES)

    st.subheader(f"评测结果（{len(df_display)} 条）")
    st.dataframe(
        df_display,
        width='stretch',
        hide_index=True,
        column_config={
            COLUMN_NAMES["pair_id"]: st.column_config.TextColumn("样本编号", width="small"),
            COLUMN_NAMES["style"]: st.column_config.TextColumn("风格", width="small"),
            COLUMN_NAMES["room_type"]: st.column_config.TextColumn("房间类型", width="small"),
            COLUMN_NAMES["iou"]: st.column_config.NumberColumn("IoU 分割精度", format="%.4f"),
            COLUMN_NAMES["fid"]: st.column_config.NumberColumn("FID 图像真实感", format="%.2f"),
            COLUMN_NAMES["clip_score"]: st.column_config.NumberColumn("CLIP 语义匹配度", format="%.4f"),
            COLUMN_NAMES["structural_fidelity"]: st.column_config.NumberColumn("结构保真度", format="%.2f"),
            COLUMN_NAMES["llm_judge"]: st.column_config.NumberColumn("LLM 综合评分", format="%.2f"),
        },
    )

    return df
