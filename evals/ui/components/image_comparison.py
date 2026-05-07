"""图像对比可视化组件"""

from pathlib import Path

import streamlit as st
from PIL import Image

from evals.config import METRIC_RANGES, METRIC_LABELS, EVALS_DIR, PROJECT_ROOT


def _resolve(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    if path.startswith("data/"):
        return EVALS_DIR / p
    return PROJECT_ROOT / p


def render_image_comparison(store, loader) -> None:
    """渲染图像对比：原图 vs 生成图 + 分数"""
    data = store.load()
    results = data.get("results", [])

    if not results:
        st.info("暂无评测结果")
        return

    # 选择 pair
    pair_ids = [r["pair_id"] for r in results]
    selected = st.selectbox("选择评测样本", pair_ids, index=0)

    # 找到对应结果和 pair 信息
    result = next((r for r in results if r["pair_id"] == selected), None)
    if not result:
        return

    pairs = loader.load()
    pair = next((p for p in pairs if p.pair_id == selected), None)
    if not pair:
        return

    input_path = _resolve(pair.input_path)
    output_path = _resolve(pair.output_path) if pair.output_path else None

    # 图片对比
    col_img1, col_img2 = st.columns(2)
    with col_img1:
        st.subheader("毛坯原图")
        if input_path.exists():
            st.image(str(input_path), use_container_width=True)
        else:
            st.warning(f"图片不存在: {input_path}")

    with col_img2:
        st.subheader("AI 效果图")
        if output_path and output_path.exists():
            st.image(str(output_path), use_container_width=True)
        else:
            st.warning(f"效果图不存在: {output_path}")

    # 评分详情
    st.subheader("评分详情")
    scores = result.get("scores", {})
    score_cols = st.columns(len(scores))
    for i, (metric, value) in enumerate(scores.items()):
        with score_cols[i]:
            label = METRIC_LABELS.get(metric, metric)
            lo, hi, higher_better = METRIC_RANGES.get(metric, (0, 1, True))
            if hi > lo:
                normalized = (value - lo) / (hi - lo)
            else:
                normalized = 0
            normalized = max(0.0, min(1.0, normalized))

            st.metric(label=label, value=f"{value:.4f}")
            st.progress(normalized)

    # 元数据
    meta = result.get("metadata", {})
    if meta.get("style") or meta.get("room_type"):
        st.divider()
        info_cols = st.columns(3)
        with info_cols[0]:
            if meta.get("style"):
                st.write(f"**风格**: {meta['style']}")
        with info_cols[1]:
            if meta.get("room_type"):
                st.write(f"**房间**: {meta['room_type']}")
        with info_cols[2]:
            if meta.get("tags"):
                st.write(f"**标签**: {', '.join(meta['tags'])}")

    # Prompt
    if pair.prompt:
        st.info(f"**提示词**: {pair.prompt[:500]}")
