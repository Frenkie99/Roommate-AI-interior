"""AI 分析模块 — 单 case 一键深度归因（课程"Agent 裁判/开天眼"思路的落地）

本质：一个**预配置好上下文 + 固化分析框架**的 Claude Code 快捷方式。
把「找文件 → 拼上下文 → 构建 prompt → 等结果 → 记录结论」的手工流程变成一键操作，
并把归因结果沉淀在评测平台（evals/data/ai_analysis/）供团队复用。

引擎：本机 `claude` CLI 的 headless 模式（`claude -p`）——与课程说的
Claude Agent SDK `system_prompt preset="claude_code"` 是同一套产品级能力
（SDK 即 CLI 的封装），零新增 pip 依赖。

安全边界：
  - 工具白名单只给 Read / Glob / Grep（只读）；Bash/Edit/Write 显式禁用。
    归因分析不需要写权限——锁死，防止 agent"顺手修代码"。
  - 产出定位是**归因假设，待人工确认**，不是结论（协作红线：别急着下结论）。
  - prompt 里内置「已知评测集缺陷备忘」——防止 agent 把已知缺陷（如房型跑偏
    是 batch_generate 非真实路径所致）当新发现重复上报（2026-06-30 教训）。

用法：
    python -m evals.analysis.ai_analyst --pair-id pair_000            # 跑真分析（花订阅额度）
    python -m evals.analysis.ai_analyst --pair-id pair_000 --dry-run  # 只打印 prompt 不调用
    python -m evals.analysis.ai_analyst --pair-id pair_000 --model claude-opus-4-8
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from evals.config import (
    AI_ANALYSIS_DIR, EVALS_DIR, EVAL_RESULTS_PATH, METADATA_PATH,
    PROJECT_ROOT, TRACE_LOG_PATH,
)

_TIMEOUT_SEC = 15 * 60       # 单次分析上限 15 分钟
_MAX_TURNS = 30              # agent 回合上限，防跑飞
_ALLOWED_TOOLS = "Read,Glob,Grep"
_DISALLOWED_TOOLS = "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Task"

# 归因阶段枚举（聚合后即失败模式分布 = 半自动化的 bottom-up 开放编码）
STAGES = {
    "input_quality": "输入图质量",
    "vision_understanding": "视觉理解",
    "prompt_construction": "Prompt构建",
    "generation_model": "生图模型",
    "scorer_misjudge": "评分器误判",
    "dataset_defect": "评测集缺陷",
    "not_a_failure": "复核非失败",
    "unknown": "未知",
}

# ⚠️ 已知评测集缺陷备忘 —— 必须随每次分析下发，防止 agent 把旧缺陷当新发现
_KNOWN_CAVEATS = """## 已知评测集缺陷备忘（必读，避免把已知问题误报为新发现）
1. **非真实路径生成**：本评测集 85 条全部由 evals/dataset/batch_generate.py 批量生成，
   与真实用户路径不同——真实前端会把用户选择的 room_type 传给后端参与生成，
   而 batch_generate 故意不传 → 生成时模型不知道目标房型。
   因此「房型跑偏」（实测约 71%）主要是评测集生成方式的缺陷，**不能直接当产品 bug 上报**。
2. **房型标注缺失**：47/85 条的 room_type 字段为空，房型相关结论只在有标注子集上有效。
3. **退役评分器**：clip_score / llm_judge 已被 85 条金标准证伪退役（clip 与美学负相关；
   llm_judge 盲评不看图=噪声）。结果文件里若出现它们的历史分数请忽略。
4. **唯一可信自动分**：structural_fidelity（0-100，64×64 低分辨率布局 SSIM，
   vs 人工结构维 Spearman +0.418）只覆盖结构维；美学/指令维目前没有可信自动分。
5. **单次采样**：所有效果图均为单次生成，生成模型的非确定性方差未度量。
"""

_FRAMEWORK = """## 分析框架（依次回答五问）
1. **失败首先发生在哪一环？** 沿生成链路定位第一个出错环节：
   输入毛坯图质量 → 视觉理解（AI 是否看错房型/布局）→ Prompt 构建（需求是否丢失/扭曲）
   → 生图模型能力 → 或者其实是**评分器误判**（图没问题，分打错了）/ **评测集自身缺陷**。
2. **证据是什么？** 必须指向你真实查看过的内容：图中可见的具体元素、trace 字段值、
   分数与人工标注的具体矛盾点。禁止无证据推断。
3. **同类失败可能波及哪些 case？** 给出可检索的特征（如"所有无房型标注的 corner_case"），
   便于横向排查。
4. **建议的修复方向是什么？** 指向具体环节（改 prompt 模板 / 换视觉分析模型 / 修评分器 /
   补数据集），不要泛泛而谈。
5. **你的置信度多高？** high / medium / low，并说明不确定性来自哪里。
"""

_OUTPUT_CONTRACT = """## 输出要求
自由分析结束后，**最后必须输出一个 ```json 围栏块**，字段如下：
```json
{
  "root_cause_stage": "input_quality|vision_understanding|prompt_construction|generation_model|scorer_misjudge|dataset_defect|not_a_failure|unknown",
  "confidence": "high|medium|low",
  "summary": "一句话归因结论（30字内）",
  "evidence": ["证据1（指向真实查看过的内容）", "证据2"],
  "affected_scope": "同类失败的可检索特征描述",
  "suggested_fix": "具体修复方向",
  "uncertainty": "不确定性来自哪里"
}
```
重要：你的产出是**归因假设，待人工确认**，不是结论。请在 summary 中保持假设语气。
"""


# ----------------------------- 上下文收集 -----------------------------

def _resolve(path: str) -> Path:
    """与评测平台一致的相对路径解析（data/ 前缀挂 evals/，其余挂项目根）。"""
    p = Path(path)
    if p.is_absolute():
        return p
    if str(path).startswith("data/"):
        return EVALS_DIR / p
    return PROJECT_ROOT / p


def _load_pair(pair_id: str) -> Optional[dict]:
    data = json.loads(Path(METADATA_PATH).read_text(encoding="utf-8"))
    for p in data.get("pairs", []):
        if p.get("pair_id") == pair_id:
            return p
    return None


def _load_scores(pair_id: str) -> dict:
    try:
        data = json.loads(Path(EVAL_RESULTS_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    for r in data.get("results", []):
        if r.get("pair_id") == pair_id:
            return r.get("scores", {}) or {}
    return {}


def _load_gold(pair_id: str) -> Optional[dict]:
    from evals.scorer.gold_store import GoldStore
    return GoldStore().get(pair_id)


def _load_trace(pair: dict) -> Optional[dict]:
    """production 来源的 pair 带 trace_id → 从 traces.jsonl 捞完整 trace。"""
    trace_id = (pair.get("metadata") or {}).get("trace_id")
    if not trace_id:
        return None
    tp = Path(TRACE_LOG_PATH)
    if not tp.exists():
        return None
    try:
        with open(tp, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("trace_id") == trace_id:
                    return rec
    except (OSError, json.JSONDecodeError):
        return None
    return None


def build_prompt(pair_id: str) -> str:
    """拼装预配置上下文 + 固化框架的完整分析 prompt。"""
    pair = _load_pair(pair_id)
    if pair is None:
        raise ValueError(f"pair_id 不存在: {pair_id}")
    scores = _load_scores(pair_id)
    gold = _load_gold(pair_id)
    trace = _load_trace(pair)

    in_path = _resolve(pair.get("input_path", ""))
    out_path = _resolve(pair.get("output_path", "")) if pair.get("output_path") else None

    lines = [
        "你是 AI 室内设计平台评测体系的**失败归因分析师**。",
        "针对下面这个评测 case 做深度归因：为什么它失败/表现不佳（或者其实没失败）。",
        "",
        _KNOWN_CAVEATS,
        "## Case 档案",
        f"- pair_id: {pair_id}",
        f"- 毛坯原图: {in_path}",
        f"- AI 效果图: {out_path or '（缺失）'}",
        "  ⚠️ 请务必用 Read 工具**亲眼查看这两张图**再下任何判断（这是你相对纯文本分析的核心优势）。",
        f"- 用户指令：风格={pair.get('style') or '未指定'}；房型={pair.get('room_type') or '未指定（见备忘2）'}",
        f"- 提示词: {(pair.get('prompt') or '')[:500] or '（空）'}",
        f"- 数据集: split={pair.get('dataset_split')}；标签={pair.get('tags')}；"
        f"内在难度={pair.get('intrinsic_difficulty') or '未标'}",
    ]

    if scores:
        lines.append(f"- 自动评分: {json.dumps(scores, ensure_ascii=False)}"
                     f"（structural_fidelity 为 0-100，见备忘4）")
    else:
        lines.append("- 自动评分: 无")

    if gold:
        g_scores = gold.get("scores", {})
        lines.append(f"- 人工金标准（1-5）: {json.dumps(g_scores, ensure_ascii=False)}")
        for field, label in (("binary_verdict", "人工二元裁决"),
                             ("critique", "人工判词"), ("notes", "人工备注")):
            if gold.get(field):
                lines.append(f"  - {label}: {gold[field]}")
    else:
        lines.append("- 人工金标准: 未标注")

    if trace:
        lines += [
            "",
            "## Trace（真实生成过程白盒记录）",
            f"- prompt_source: {trace.get('prompt_source')}"
            "（llm_vision=看图构建；blind_deepseek/static_on_error=没看图，房型判断可能出错）",
            f"- vision_analysis_ok: {trace.get('vision_analysis_ok')}",
            f"- vision_analysis: {json.dumps(trace.get('vision_analysis'), ensure_ascii=False)[:800]}",
            f"- enhanced_prompt（实际发给生图模型的完整 prompt）: "
            f"{(trace.get('enhanced_prompt') or '')[:800]}",
            f"- model_used: {trace.get('model_used')}",
            f"- latency: {trace.get('latency_ms')}ms  分段={trace.get('latency_breakdown')}",
            f"- success: {trace.get('success')}  error: {trace.get('error')}",
        ]
    else:
        lines += ["", "## Trace", "无（此 case 来自批量生成，不是真实用户请求——见备忘1）"]

    lines += [
        "",
        "## 可用资源（都是只读）",
        "- 用 Read 查看上面两张图片文件（可多次、可对比细节）",
        "- 生成链路源码：backend/app/routes/image.py（生成端点）、backend/app/services/（视觉分析/prompt构建/生图逻辑）",
        "- 评测方法论与已知结论：evals/METHODOLOGY.md、evals/PROGRESS.md（需要时再读，很长）",
        "",
        _FRAMEWORK,
        _OUTPUT_CONTRACT,
    ]
    return "\n".join(lines)


# ----------------------------- 执行与沉淀 -----------------------------

def _result_path(pair_id: str) -> Path:
    return Path(AI_ANALYSIS_DIR) / f"{pair_id}.json"


def _running_path(pair_id: str) -> Path:
    return Path(AI_ANALYSIS_DIR) / f"{pair_id}.running"


def _log_path(pair_id: str) -> Path:
    return Path(AI_ANALYSIS_DIR) / f"{pair_id}.log"


def _extract_verdict(text: str) -> Optional[dict]:
    """从 agent 最终回复中抽取最后一个合法 json 围栏块。"""
    blocks = re.findall(r"```json\s*(.*?)```", text, re.DOTALL)
    for b in reversed(blocks):
        try:
            d = json.loads(b)
            if isinstance(d, dict) and "root_cause_stage" in d:
                return d
        except json.JSONDecodeError:
            continue
    return None


def run_analysis(pair_id: str, model: Optional[str] = None,
                 max_turns: int = _MAX_TURNS) -> dict:
    """跑一次完整分析并沉淀结果 JSON。返回结果 dict。

    引擎 = `claude -p`（headless），只读工具白名单，回合与时长双上限。
    结果无论成败都落盘（status=ok/error），供看板展示与团队复用。
    """
    Path(AI_ANALYSIS_DIR).mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(pair_id)

    running = _running_path(pair_id)
    running.write_text(json.dumps({
        "pid": os.getpid(), "started_at": datetime.now().isoformat(),
    }), encoding="utf-8")

    cmd = [
        "claude", "-p",
        "--output-format", "json",
        "--allowedTools", _ALLOWED_TOOLS,
        "--disallowedTools", _DISALLOWED_TOOLS,
        "--max-turns", str(max_turns),
    ]
    if model:
        cmd += ["--model", model]

    t0 = time.time()
    result_text, status, err = "", "ok", ""
    envelope = {}
    try:
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            timeout=_TIMEOUT_SEC, cwd=str(PROJECT_ROOT),
        )
        raw = proc.stdout or ""
        _log_path(pair_id).write_text(
            f"$ {' '.join(cmd)}\n--- stdout ---\n{raw}\n--- stderr ---\n{proc.stderr}",
            encoding="utf-8")
        try:
            envelope = json.loads(raw)
            result_text = envelope.get("result") or ""
            if envelope.get("is_error"):
                status, err = "error", f"claude 返回 is_error: {result_text[:300]}"
        except json.JSONDecodeError:
            result_text = raw
            if proc.returncode != 0:
                status, err = "error", f"claude 退出码 {proc.returncode}: {(proc.stderr or raw)[:300]}"
    except subprocess.TimeoutExpired:
        status, err = "error", f"分析超时（>{_TIMEOUT_SEC//60} 分钟）"
    except FileNotFoundError:
        status, err = "error", "claude CLI 不在 PATH 中（需要本机安装 Claude Code）"
    finally:
        running.unlink(missing_ok=True)

    verdict = _extract_verdict(result_text) if status == "ok" else None
    if status == "ok" and verdict is None:
        status, err = "error", "分析完成但未产出合法 JSON 结论块（全文见 full_text）"

    record = {
        "pair_id": pair_id,
        "status": status,
        "error": err or None,
        "analyzed_at": datetime.now().isoformat(),
        "duration_sec": round(time.time() - t0, 1),
        "model": model or envelope.get("model") or "cli-default",
        "num_turns": envelope.get("num_turns"),
        "verdict": verdict,
        "full_text": result_text,
    }
    tmp = str(_result_path(pair_id)) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _result_path(pair_id))
    return record


def load_result(pair_id: str) -> Optional[dict]:
    p = _result_path(pair_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def is_running(pair_id: str) -> Optional[dict]:
    """分析进行中返回状态 dict，否则 None。附带僵尸清理（超时未清的 .running）。"""
    p = _running_path(pair_id)
    if not p.exists():
        return None
    try:
        info = json.loads(p.read_text(encoding="utf-8"))
        started = datetime.fromisoformat(info["started_at"])
        if (datetime.now() - started).total_seconds() > _TIMEOUT_SEC + 60:
            p.unlink(missing_ok=True)  # 僵尸状态：进程早没了，清掉
            return None
        return info
    except (OSError, ValueError, KeyError):
        p.unlink(missing_ok=True)
        return None


def all_verdicts() -> dict:
    """{pair_id: verdict}——聚合所有已完成分析的归因结论（失败模式分布的数据源）。"""
    out = {}
    d = Path(AI_ANALYSIS_DIR)
    if not d.exists():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if rec.get("status") == "ok" and rec.get("verdict"):
            out[rec["pair_id"]] = rec["verdict"]
    return out


# ----------------------------- CLI -----------------------------

def main():
    ap = argparse.ArgumentParser(description="单 case AI 深度归因分析")
    ap.add_argument("--pair-id", required=True)
    ap.add_argument("--model", default=None, help="覆盖 claude CLI 默认模型")
    ap.add_argument("--max-turns", type=int, default=_MAX_TURNS)
    ap.add_argument("--dry-run", action="store_true", help="只打印 prompt，不调用")
    args = ap.parse_args()

    if args.dry_run:
        print(build_prompt(args.pair_id))
        return

    print(f"开始分析 {args.pair_id}（上限 {args.max_turns} 回合 / {_TIMEOUT_SEC//60} 分钟）…")
    rec = run_analysis(args.pair_id, model=args.model, max_turns=args.max_turns)
    print(f"status={rec['status']}  耗时={rec['duration_sec']}s  回合={rec.get('num_turns')}")
    if rec["status"] == "ok":
        v = rec["verdict"]
        print(f"归因: {STAGES.get(v.get('root_cause_stage'), v.get('root_cause_stage'))}"
              f"（置信度 {v.get('confidence')}）")
        print(f"结论: {v.get('summary')}")
        print(f"已沉淀: {_result_path(args.pair_id)}")
    else:
        print(f"❌ {rec['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
