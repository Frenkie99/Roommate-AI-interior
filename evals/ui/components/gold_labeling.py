"""金标准标注面板 — 人工为图像对打分，作为评分器可信度的真值

设计要点（见 evals/METHODOLOGY.md 第 3 节）：
- 标注时**刻意不展示自动评分**，避免锚定效应污染人工金标准的独立性。
- 1-5 分制覆盖 结构保真 / 美学质量 / 指令遵循 / 综合 四个可解释维度。
- 二元判定 + critique（2026-07-09）：Likert 喂相关性对齐；TPR/TNR 校准需要二元真值。
  overall≥4/≤2 自动派生 pass/fail；overall=3 为模糊地带，须在此人工二元裁决。
"""

import streamlit as st

from evals.scorer.gold_store import (
    GoldStore, GOLD_AXES, GOLD_SCALE, derive_binary, effective_binary,
)
from evals.ui.components.image_comparison import _resolve

_AXIS_HELP = {
    "structural": "毛坯的墙体/门窗/承重/户型结构是否被如实保留（不该被 AI 乱改）",
    "aesthetic": "设计感、配色、材质、光影、整体美观度",
    "instruction": "是否符合目标风格/房型/提示词中的具体需求",
    "overall": "抛开单项，你对这张效果图的综合主观评价",
}


def render_gold_labeling(loader) -> None:
    """渲染金标准标注页。"""
    st.subheader("金标准标注")
    st.caption(
        "人工打分是度量评分器是否可信的唯一真值。**标注时请勿参考自动分**，"
        "凭专业判断独立打分。建议先标 20-30 条，覆盖好/中/差与不同难度。"
    )

    pairs = loader.load()
    if not pairs:
        st.info("暂无数据集样本。")
        return

    store = GoldStore()
    labels = store.load()

    # 进度（含二元仲裁队列）
    pending_ids = {pid for pid, e in labels.items() if effective_binary(e)[0] is None}
    done, total = len(labels), len(pairs)
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.metric("已标注 / 总数", f"{done} / {total}")
    with c2:
        st.metric("待二元仲裁", len(pending_ids),
                  help="overall=3 的模糊地带且无显式 pass/fail 裁决，TPR/TNR 计算会剔除它们")
    with c3:
        st.progress(done / total if total else 0.0)

    # 标注人（会话内记忆）
    labeler = st.text_input("标注人", value=st.session_state.get("gold_labeler", ""),
                            placeholder="例如 frenkie")
    st.session_state["gold_labeler"] = labeler

    fc1, fc2 = st.columns(2)
    with fc1:
        only_unlabeled = st.checkbox("只看未标注", value=True)
    with fc2:
        adjudicate = st.checkbox(
            f"只看待二元仲裁（{len(pending_ids)} 条）", value=False,
            help="模糊地带（overall=3）逐条裁决 pass/fail，喂 TPR/TNR 校准")
    if adjudicate:
        candidates = [p for p in pairs if p.pair_id in pending_ids]
    else:
        candidates = [p for p in pairs if not only_unlabeled or p.pair_id not in labels]
    if not candidates:
        st.success("🎉 在当前筛选下没有待标注样本了。")
        return

    def _fmt(p):
        flag = "✅" if p.pair_id in labels else "⬜"
        extra = f" · {p.style}/{p.room_type}".rstrip("/")
        return f"{flag} {p.pair_id}{extra if extra.strip(' ·') else ''}"

    pair = st.selectbox("选择样本", candidates, format_func=_fmt)
    if pair is None:
        return

    existing = labels.get(pair.pair_id)

    # 图像对比（不显示任何自动分）
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**毛坯原图**")
        ip = _resolve(pair.input_path)
        if ip and ip.exists():
            st.image(str(ip), width='stretch')
        else:
            st.warning("原图不可用")
    with col2:
        st.markdown("**AI 效果图**")
        op = _resolve(pair.output_path) if pair.output_path else None
        if op and op.exists():
            st.image(str(op), width='stretch')
        else:
            st.warning("效果图不可用")

    meta_bits = [b for b in [
        f"风格: {pair.style}" if pair.style else "",
        f"房间: {pair.room_type}" if pair.room_type else "",
        f"标签: {', '.join(pair.tags)}" if pair.tags else "",
    ] if b]
    if meta_bits:
        st.write(" · ".join(meta_bits))
    if pair.prompt:
        st.info(f"**提示词**: {pair.prompt[:500]}")

    # 打分滑块
    st.divider()
    lo, hi = int(GOLD_SCALE[0]), int(GOLD_SCALE[1])
    scores = {}
    score_cols = st.columns(len(GOLD_AXES))
    for i, (axis, label) in enumerate(GOLD_AXES.items()):
        with score_cols[i]:
            default = int((existing or {}).get("scores", {}).get(axis, 3))
            scores[axis] = st.slider(
                label, lo, hi, default, help=_AXIS_HELP.get(axis),
                key=f"gold_{pair.pair_id}_{axis}",
            )

    # 二元判定（TPR/TNR 校准的真值侧）+ critique
    derived = derive_binary({"overall": float(scores["overall"])})
    existing_bv = (existing or {}).get("binary_verdict")
    bv_options = ["自动派生", "通过 pass", "失败 fail"]
    bv_index = {"pass": 1, "fail": 2}.get(existing_bv, 0)
    bc1, bc2 = st.columns([2, 3])
    with bc1:
        bv_choice = st.radio(
            "二元判定", bv_options, index=bv_index, horizontal=True,
            key=f"gold_bv_{pair.pair_id}",
            help="喂 TPR/TNR 校准的 pass/fail 真值。「自动派生」= overall≥4 pass / ≤2 fail",
        )
    with bc2:
        if bv_choice == "自动派生":
            if derived:
                st.caption(f"当前派生结果：**{derived}**（overall={int(scores['overall'])}）")
            else:
                st.warning("overall=3 为模糊地带，自动派生无结果——请手工裁决 pass/fail，"
                           "否则此条不参与 TPR/TNR 计算。")
        else:
            st.caption("显式裁决优先于派生；改回「自动派生」即清除。")

    critique = st.text_input(
        "Critique（一句话为什么过/不过；喂 few-shot 示例与错误分析）",
        value=(existing or {}).get("critique", ""),
        key=f"gold_critique_{pair.pair_id}",
        placeholder="例如：光影和材质假、床的比例失真；或：风格准确、结构如实保留",
    )

    notes = st.text_input("备注（可选）",
                          value=(existing or {}).get("notes", ""),
                          key=f"gold_notes_{pair.pair_id}")

    # 校准剔除（评测集缺陷 case：题目本身无效，如房型随机分配错误）
    excluded_now = bool((existing or {}).get("calibration_excluded"))
    exclude = st.checkbox(
        "🚫 从校准剔除（评测集缺陷：题目无效，非产品输出问题）",
        value=excluded_now, key=f"gold_excl_{pair.pair_id}",
        help="剔除范围=二元校准(TPR/TNR)+few-shot池；分维度相关性对齐不受影响")
    excl_reason = ""
    if exclude:
        excl_reason = st.text_input(
            "剔除原因", value=(existing or {}).get("exclusion_reason", ""),
            key=f"gold_excl_reason_{pair.pair_id}",
            placeholder="例如：房型随机分配错误，源图明显是卫生间")

    save_label = "更新标注" if existing else "保存标注"
    if st.button(save_label, type="primary"):
        bv_param = {"通过 pass": "pass", "失败 fail": "fail"}.get(bv_choice, "derived")
        store.upsert(pair.pair_id, scores, labeler=labeler, notes=notes,
                     binary_verdict=bv_param, critique=critique,
                     calibration_excluded=exclude, exclusion_reason=excl_reason)
        st.success(f"已保存 {pair.pair_id} 的标注。")
        st.rerun()

    if existing:
        st.caption(f"上次标注: {existing.get('labeled_at', '')} · "
                   f"标注人: {existing.get('labeler') or '未填'}")
