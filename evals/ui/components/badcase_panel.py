"""Badcase/Goodcase 分析面板"""

import json
import logging
from pathlib import Path
from typing import Optional

import streamlit as st
from PIL import Image

from evals.config import METRIC_RANGES, METRIC_LABELS, BADCASE_NOTES_PATH, EVALS_DIR, PROJECT_ROOT

logger = logging.getLogger(__name__)

_ALLOWED_ROOTS = (
    EVALS_DIR.resolve(),
    (PROJECT_ROOT / "output").resolve(),
)

def _resolve(path: str) -> Optional[Path]:
    """
    安全地解析路径，防止路径遍历攻击：
    1. 不接受绝对路径
    2. resolve() 后必须仍在允许的目录内
    """
    if not path:
        return None

    p = Path(path)
    if p.is_absolute():
        resolved = p.resolve()
        if any(resolved.is_relative_to(root) for root in _ALLOWED_ROOTS):
            return resolved
        logger.warning(f"REJECTED absolute path: {path!r}")
        return None

    if path.startswith("data/") or path.startswith("evals/"):
        resolved = (PROJECT_ROOT / p).resolve() if path.startswith("evals/") else (EVALS_DIR / p).resolve()
    elif path.startswith("output/"):
        resolved = (PROJECT_ROOT / p).resolve()
    else:
        logger.warning(f"REJECTED unsupported path prefix: {path!r}")
        return None

    if any(resolved.is_relative_to(root) for root in _ALLOWED_ROOTS):
        return resolved

    logger.warning(f"REJECTED path escape: {path!r} -> {resolved}")
    return None


def _normalize_score(scores: dict) -> float:
    """计算综合分数（归一化后平均）"""
    total = 0
    count = 0
    for metric, value in scores.items():
        if value is None:
            continue
        lo, hi, higher_better = METRIC_RANGES.get(metric, (0, 1, True))
        if hi <= lo:
            continue
        normalized = (value - lo) / (hi - lo)
        if not higher_better:
            normalized = 1 - normalized
        total += normalized
        count += 1
    return total / count if count else 0


def _load_notes() -> dict:
    path = Path(BADCASE_NOTES_PATH)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_notes(notes: dict) -> None:
    path = Path(BADCASE_NOTES_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)


def render_badcase_panel(store, loader) -> None:
    """渲染 Badcase/Goodcase 面板"""
    data = store.load()
    results = data.get("results", [])

    if not results:
        st.info("暂无评测结果")
        return

    pairs = loader.load()
    pair_map = {p.pair_id: p for p in pairs}
    notes = _load_notes()

    # AI 归因分布（已分析 case 的失败模式聚合）
    from evals.ui.components.ai_analysis import render_cause_distribution
    render_cause_distribution()

    # 计算综合分数并排序
    ranked = []
    for r in results:
        pair_id = r["pair_id"]
        scores = r.get("scores", {})
        composite = _normalize_score(scores)
        ranked.append((composite, pair_id, r))

    ranked.sort(key=lambda x: x[0])

    # Badcase（最低分）
    st.subheader("Badcase（最差表现）")
    for composite, pair_id, result in ranked[:5]:
        pair = pair_map.get(pair_id)
        with st.expander(f"{pair_id} — 综合分: {composite:.3f}", expanded=False):
            _render_case(pair, result, notes)

    st.divider()

    # Goodcase（最高分）
    st.subheader("Goodcase（最佳表现）")
    for composite, pair_id, result in reversed(ranked[-5:]):
        pair = pair_map.get(pair_id)
        with st.expander(f"{pair_id} — 综合分: {composite:.3f}", expanded=False):
            _render_case(pair, result, notes)


def _render_case(pair, result: dict, notes: dict) -> None:
    """渲染单个 case"""
    pair_id = result["pair_id"]
    scores = result.get("scores", {})

    col1, col2 = st.columns(2)
    with col1:
        st.write("**毛坯原图**")
        if pair:
            input_path = _resolve(pair.input_path)
            if input_path is None:
                st.caption("图片路径不安全，已跳过")
            elif input_path.exists():
                st.image(str(input_path), width='stretch')

    with col2:
        st.write("**AI 效果图**")
        if pair and pair.output_path:
            output_path = _resolve(pair.output_path)
            if output_path is None:
                st.caption("效果图路径不安全或为空，已跳过")
            elif output_path.exists():
                st.image(str(output_path), width='stretch')

    # 评分
    score_cols = st.columns(len(scores))
    for i, (metric, value) in enumerate(scores.items()):
        with score_cols[i]:
            label = METRIC_LABELS.get(metric, metric)
            lo, hi, higher_better = METRIC_RANGES.get(metric, (0, 1, True))
            if value is None:
                st.metric(label=label, value="N/A")
                continue
            if hi > lo:
                normalized = (value - lo) / (hi - lo)
            else:
                normalized = 0
            st.metric(label=label, value=f"{value:.4f}")
            st.progress(max(0.0, min(1.0, normalized)))

    if pair:
        st.write(f"**风格**: {pair.style} | **标签**: {', '.join(pair.tags)}")

    # 标注
    current_note = notes.get(pair_id, "")
    new_note = st.text_area("标注", value=current_note, key=f"note_{pair_id}")
    if new_note != current_note:
        notes[pair_id] = new_note
        _save_notes(notes)
        st.success("标注已保存")

    # AI 一键归因（预配置上下文 + 固化框架的 Claude Code 快捷方式）
    st.divider()
    from evals.ui.components.ai_analysis import render_ai_analysis
    render_ai_analysis(pair_id)
