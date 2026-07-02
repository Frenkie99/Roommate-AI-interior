"""用户使用过程（Trace 回放）可视化组件 —— Eval Harness 五大要素之④「日志记录」的呈现端。

把一次真实用户「上传毛坯 → 选指令 → AI 处理 → 出图 → 反馈」的完整过程，
在看板上按步骤时间线还原出来。真实数据由后端埋点采集（待部署）；
部署前读示例数据 sample_traces.jsonl 预览界面。
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import streamlit as st
from PIL import Image

from evals.config import PROJECT_ROOT, TRACE_LOG_PATH, SAMPLE_TRACES_PATH
from evals.dataset.schemas import Trace

logger = logging.getLogger(__name__)

# trace 里存的是 input/xxx、output/xxx 相对路径（真实用户的图落在这两处）
_ALLOWED_ROOTS = (
    (PROJECT_ROOT / "input").resolve(),
    (PROJECT_ROOT / "output").resolve(),
)


def _resolve(path: str) -> Optional[Path]:
    """安全解析图片相对路径（只允许 input/ 与 output/，防路径遍历）。"""
    if not path:
        return None
    p = Path(path)
    resolved = (p if p.is_absolute() else (PROJECT_ROOT / p)).resolve()
    if any(resolved.is_relative_to(root) for root in _ALLOWED_ROOTS):
        return resolved
    logger.warning(f"REJECTED trace image path: {path!r} -> {resolved}")
    return None


def _load_traces() -> Tuple[List[Trace], bool]:
    """返回 (traces, is_sample)。真实 traces.jsonl 存在且非空则用真实，否则回退示例。"""
    real = str(TRACE_LOG_PATH)
    if os.path.exists(real) and os.path.getsize(real) > 0:
        return _read_jsonl(real), False
    return _read_jsonl(str(SAMPLE_TRACES_PATH)), True


def _read_jsonl(path: str) -> List[Trace]:
    traces: List[Trace] = []
    if not os.path.exists(path):
        return traces
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                traces.append(Trace.from_dict(json.loads(line)))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"跳过坏 trace 行：{e}")
    return traces


def _show_image(path: str, caption: str) -> None:
    resolved = _resolve(path)
    if resolved and resolved.exists():
        try:
            st.image(Image.open(resolved), caption=caption, use_container_width=True)
            return
        except Exception as e:  # 图损坏/读失败不拖垮页面
            logger.warning(f"图片打开失败 {path}: {e}")
    st.warning(f"图片缺失/无法读取：{path}")


def _render_one_trace(t: Trace) -> None:
    ok = "✅ 成功" if t.success else f"❌ 失败：{t.error}"
    st.markdown(f"**trace** `{t.trace_id}` · {t.created_at} · {ok}")

    # [1] 输入 → [4] 输出：左右对照
    c1, c2 = st.columns(2)
    with c1:
        st.caption("① 用户上传（毛坯原图）")
        _show_image(t.input_image_path, f"hash={t.input_image_hash or '?'}")
    with c2:
        st.caption("④ AI 输出（效果图）")
        if t.output_image_paths:
            for i, op in enumerate(t.output_image_paths):
                _show_image(op, f"输出 {i + 1}")
        else:
            st.warning("无输出图")

    # [2] 用户指令（真实选择 = 评测的「指令」）
    st.caption("② 用户指令（真实选择）")
    st.markdown(
        f"- 风格：`{t.style or '—'}`　房型：`{t.room_type or '—'}`　比例：`{t.aspect_ratio or '—'}`\n"
        f"- 自定义描述：{t.custom_prompt or '（无）'}"
    )

    # [3] AI 中间过程（白盒中间步骤 —— 课程强调「中途节点也要记」）
    st.caption("③ AI 中间过程（诊断）")

    # 3.1 提示词走了哪条路（视觉成功 / 盲降级 / 静态回退）
    source_label = {
        "llm_vision": "✅ 视觉识别成功（AI 真的看了图）",
        "blind_deepseek": "⚠️ **视觉失败，静默降级到盲 DeepSeek（没看图）** — 房型/内容判断可能出错",
        "static_on_error": "⚠️ LLM 异常，回退静态模板提示词（没看图）",
        "static": "— 未启用 LLM，用静态模板",
    }.get(t.prompt_source)
    if source_label:
        st.markdown(f"- 提示词来源：{source_label}")
    elif t.vision_analysis_ok is True:
        st.markdown("- 视觉识别：✅ 成功")
    elif t.vision_analysis_ok is False:
        st.markdown("- 视觉识别：⚠️ 静默降级到盲 DeepSeek（没看图）")
    else:
        st.markdown("- 视觉识别：—（未走该分支）")

    # 3.2 分阶段耗时（哪一步慢一眼看到）
    lb = t.latency_breakdown or {}
    parts = []
    if lb.get("vision_ms") is not None:
        parts.append(f"视觉分析 {lb['vision_ms']}ms")
    if lb.get("generate_ms") is not None:
        parts.append(f"生图 {lb['generate_ms']}ms")
    total = f"{t.latency_ms} ms" if t.latency_ms is not None else "—"
    breakdown = f"（{' + '.join(parts)}）" if parts else ""
    st.markdown(f"- 使用模型：`{t.model_used or '—'}`　总耗时：{total}{breakdown}")

    # 3.3 AI 对房间的原始理解（白盒关键产物 —— 出问题先看这里）
    if t.vision_analysis:
        # 自动比对：AI 识别的房型 vs 用户选的房型，跑偏就红字点名（根因一眼定位）
        detected = t.vision_analysis.get("room_analysis", {}).get("detected_room_type")
        if detected and t.room_type and detected != t.room_type:
            st.error(f"🚨 房型跑偏：用户选了 **{t.room_type}**，但 AI 识别成 **{detected}** "
                     f"→ 生成结果很可能不符。根因大概率在上面的「提示词来源」。")
        with st.expander("🔍 AI 对房间的理解（vision_analysis —— 出问题时先看这里）"):
            st.json(t.vision_analysis)

    with st.expander("实际发给图像模型的完整 prompt（enhanced_prompt）"):
        st.code(t.enhanced_prompt or "（空）", language=None)

    # [5] 用户反馈（bad case 金矿；第4步埋点上线后由真实用户回填）
    st.caption("⑤ 用户反馈")
    if t.feedback:
        action = t.feedback.get("action", "—")
        rating = t.feedback.get("rating", "—")
        note = t.feedback.get("note", "")
        emoji = {"满意": "👍", "重新生成": "🔄", "下载": "⬇️", "弃用": "🗑️"}.get(action, "•")
        st.markdown(f"- {emoji} **{action}**　评分：{rating}" + (f"　“{note}”" if note else ""))
    else:
        st.info("暂无反馈（用户点评埋点＝trace 第4步，待上线；上线后这里显示 满意/重生成/下载/弃用）")


def render_trace_viewer() -> None:
    """渲染「用户使用过程」页：按会话选，再逐条还原完整使用过程。"""
    st.subheader("用户使用过程（Trace 回放）")

    traces, is_sample = _load_traces()

    if is_sample:
        st.warning(
            "⚠️ **当前为示例数据（sample_traces.jsonl）**，仅用于预览界面。\n\n"
            "真实用户数据要等后端埋点**部署上线**后才会流入（写到 `backend/data/traces.jsonl`）。"
            "上线后本页自动切换为真实数据、无需改代码。"
        )
    else:
        st.success(f"✅ 正在展示真实用户数据：{TRACE_LOG_PATH}")

    if not traces:
        st.info("暂无 trace 记录。")
        return

    # 按会话分组（同一匿名用户的多次操作串在一起）
    sessions = {}
    for t in traces:
        sessions.setdefault(t.session_id or "（无会话id）", []).append(t)

    total = len(traces)
    st.markdown(f"共 **{total}** 条使用记录，分属 **{len(sessions)}** 个会话。")

    labels = [f"{sid}（{len(ts)} 次操作）" for sid, ts in sessions.items()]
    sid_keys = list(sessions.keys())
    picked = st.selectbox("选择一个会话（用户）", range(len(sid_keys)),
                          format_func=lambda i: labels[i])
    chosen = sorted(sessions[sid_keys[picked]], key=lambda t: t.created_at)

    if len(chosen) > 1:
        st.caption(f"该用户在本会话里操作了 {len(chosen)} 次（按时间从早到晚）：")
    for idx, t in enumerate(chosen, 1):
        with st.container(border=True):
            if len(chosen) > 1:
                st.markdown(f"#### 第 {idx} 次操作")
            _render_one_trace(t)
