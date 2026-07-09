"""AI 分析组件 — case 级一键归因按钮 + 全局失败模式分布

嵌入 Badcase 面板：每个 case 一个「🤖 AI 分析」按钮，后台调 evals.analysis.ai_analyst
（claude CLI headless，只读工具），结果沉淀后在此展示并可复用。

沉淀的归因结论聚合成 root_cause_stage 分布 = 半自动化的失败模式开放编码，
是模块五（迭代优化）的直接输入。
"""

import subprocess
import sys
from collections import Counter

import streamlit as st

from evals.config import PROJECT_ROOT
from evals.analysis import ai_analyst

_CONF_BADGE = {"high": "🟢 高", "medium": "🟡 中", "low": "🔴 低"}


def _launch_background(pair_id: str) -> None:
    """后台起分析子进程（detached）：Streamlit 交互重跑不会杀掉它。"""
    subprocess.Popen(
        [sys.executable, "-m", "evals.analysis.ai_analyst", "--pair-id", pair_id],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def render_ai_analysis(pair_id: str) -> None:
    """渲染单 case 的 AI 分析区（缓存结果 / 进行中 / 触发按钮三态）。"""
    running = ai_analyst.is_running(pair_id)
    if running:
        st.info(f"🔄 AI 分析进行中（自 {running.get('started_at', '')[:19]} 起，"
                f"通常 2-5 分钟）…")
        if st.button("刷新状态", key=f"ai_refresh_{pair_id}"):
            st.rerun()
        return

    rec = ai_analyst.load_result(pair_id)
    if rec and rec.get("status") == "ok" and rec.get("verdict"):
        v = rec["verdict"]
        stage = v.get("root_cause_stage", "unknown")
        st.markdown(
            f"**🤖 AI 归因（假设，待人工确认）**：`{ai_analyst.STAGES.get(stage, stage)}` · "
            f"置信度 {_CONF_BADGE.get(v.get('confidence'), v.get('confidence'))}"
        )
        st.markdown(f"> {v.get('summary', '')}")
        with st.expander("归因详情（证据 / 波及范围 / 修复建议 / 完整分析）"):
            for e in v.get("evidence", []):
                st.markdown(f"- 证据：{e}")
            if v.get("affected_scope"):
                st.markdown(f"- **可能波及**：{v['affected_scope']}")
            if v.get("suggested_fix"):
                st.markdown(f"- **修复方向**：{v['suggested_fix']}")
            if v.get("uncertainty"):
                st.markdown(f"- **不确定性**：{v['uncertainty']}")
            st.caption(f"分析于 {rec.get('analyzed_at', '')[:19]} · 模型 {rec.get('model')} · "
                       f"{rec.get('duration_sec')}s / {rec.get('num_turns')} 回合")
            st.text_area("完整分析全文", rec.get("full_text", ""), height=240,
                         key=f"ai_full_{pair_id}", disabled=True)
        if st.button("重新分析（花订阅额度）", key=f"ai_rerun_{pair_id}"):
            _launch_background(pair_id)
            st.rerun()
        return

    if rec and rec.get("status") == "error":
        st.warning(f"上次 AI 分析失败：{rec.get('error')}")

    if st.button("🤖 AI 分析该 case（开天眼归因，约 2-5 分钟，花订阅额度）",
                 key=f"ai_run_{pair_id}"):
        _launch_background(pair_id)
        st.rerun()


def render_cause_distribution() -> None:
    """全局失败模式分布（已分析 case 的 root_cause_stage 聚合）。"""
    verdicts = ai_analyst.all_verdicts()
    if not verdicts:
        return
    with st.expander(f"🧭 AI 归因分布（已分析 {len(verdicts)} 个 case）", expanded=False):
        st.caption("root_cause_stage 聚合 = 半自动化的失败模式开放编码。"
                   "全部为归因假设，采信前须人工复核。")
        counts = Counter(v.get("root_cause_stage", "unknown") for v in verdicts.values())
        rows = [{"归因环节": ai_analyst.STAGES.get(k, k), "case 数": n}
                for k, n in counts.most_common()]
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)
        by_stage = {}
        for pid, v in verdicts.items():
            by_stage.setdefault(v.get("root_cause_stage", "unknown"), []).append(pid)
        for stage, pids in by_stage.items():
            st.markdown(f"- **{ai_analyst.STAGES.get(stage, stage)}**: {', '.join(sorted(pids))}")
