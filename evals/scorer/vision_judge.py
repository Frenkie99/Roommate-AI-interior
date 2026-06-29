"""视觉 Judge（阶段 3）——真正"看见图"的多维评分器。

补齐本地算法做不到的两维：**美学质量 / 指令遵循**（语义问题，只能由视觉模型判）。
设计蓝图见 VISION_JUDGE_DESIGN.md。本文件提供可复用的打分函数 + 一个
「探单价 + 小批验证」的命令行入口（第一步，不写回任何数据、不进 registry）。

红线：未通过 VISION_JUDGE_DESIGN.md 第5节验收前，分不得用于任何自动决策。

两处免费加固（2026-06-29）：
  [加固一] 美学维去耦合 + 验证脚本「两极判别力」判定。
    - rubric 明确：aesthetic 只评效果图本身，不得因原图是毛坯而降分（消除毛坯图对美学判断的污染）。
    - 验证收尾打印「金标准两极分差 vs 视觉Judge两极分差」：若 Judge 拉不开好坏，与旧 llm_judge 同病，当场叫停，不往下花钱。
  [加固二] few-shot 锚定到「你」的尺度（--anchor K）。
    - 从 85 条人工金标准里跨低/中/高取 K 个样本，连同其权威分作为校准示例喂给模型，
      让 Judge 对齐你的审美而非互联网平均审美。
    - 强制「留出」：验证样本与锚点样本严格不相交，杜绝数据泄漏（对齐设计文档 2.3 防锚定原则）。

用法（需先配好 APIYI_KEY，见下方 _load_key）：
  python -m evals.scorer.vision_judge                  # 探价+验证：金标准两极各1条，默认带3个锚点
  python -m evals.scorer.vision_judge --n 2            # 控制验证条数
  python -m evals.scorer.vision_judge --anchor 0       # 关闭锚定，跑通用尺度（用于 A/B 对比）
  python -m evals.scorer.vision_judge --model gemini-2.5-flash
"""

import argparse
import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from PIL import Image

from evals.config import EVALS_DIR, PROJECT_ROOT, GOLD_LABELS_PATH, METADATA_PATH

_BASE = "https://api.apiyi.com"
_DEFAULT_MODEL = "gemini-2.5-flash"   # 理解模型；非图像生成模型
_MAX_DIM = 768                        # 缩图上限，控 token（结构/美学判断不需原分辨率）
_PROMPT_CLIP = 300                    # 截断超长 prompt

# 视觉 Judge 的输出维度（与人工金标准 axes 对齐，便于算对齐度）
AXES = ["structural", "aesthetic", "instruction", "overall"]

# [加固一] aesthetic 维明确去耦合：只评效果图自身，不得因原图是毛坯而降分。
_RUBRIC = """你是资深室内设计评审。下面【图1】是装修前的毛坯原图，【图2】是 AI 基于它生成的效果图。
目标风格：{style}；房间类型：{room_type}；用户需求：{prompt}。
请严格独立评分（1-5 分，可给低分），只输出 JSON：
{{
  "structural": <1-5>,   // 对比【图1】与【图2】：毛坯的墙体/门窗/承重/户型结构是否被如实保留，未被乱改
  "aesthetic":  <1-5>,   // 只评【图2】效果图本身的设计感/配色/材质/光影/美观；与【图1】毛坯无关，不得因原图是毛坯而降低此分
  "instruction":<1-5>,   // 【图2】是否符合目标风格/房型/需求
  "overall":    <1-5>,   // 综合主观评价
  "reason": "<两句话理由，先说硬伤>"
}}
只输出 JSON。烂图必须敢给 1-2 分、好图敢给 5 分，必须拉开差距。"""

# [加固二] 锚点校准引导语：把人工金标准的尺度先示范给模型。
_ANCHOR_INTRO = (
    "在评分前，请先校准你的尺度。以下是若干由资深评审打过权威分的【基准示例】，"
    "请记住每个示例的图像长相对应的分数，并据此校准你接下来的打分，使你的尺度与这些基准一致。"
)
_ANCHOR_TAIL = "以上是基准示例。现在请沿用上面校准好的同一把尺度，为下面这一对【新图】打分："


def _load_key():
    """取 APIYI_KEY：先环境变量，再 backend/.env 与根 .env（手动解析，不依赖 dotenv）。"""
    key = os.getenv("APIYI_KEY") or os.getenv("LLM_APIYI_KEY")
    if key:
        return key
    for envf in (PROJECT_ROOT / "backend" / ".env", PROJECT_ROOT / ".env"):
        if not envf.exists():
            continue
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() in ("APIYI_KEY", "LLM_APIYI_KEY"):
                v = v.strip().strip('"').strip("'")
                if v and v != "your_apiyi_key_here" and v != "your_llm_apiyi_key_here":
                    return v
    return None


def _resolve(path):
    p = Path(path)
    if p.is_absolute():
        return p
    if str(path).startswith("data/"):
        return EVALS_DIR / p
    return PROJECT_ROOT / p


def _img_to_b64(path, max_dim=_MAX_DIM):
    """缩图到 max_dim 内，转 JPEG base64。返回 (b64, 缩后尺寸)。"""
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), img.size


def _parse_scores(text):
    """从模型输出抽多维分。优先整体 JSON，失败则逐维正则兜底。"""
    # 去掉可能的 ```json 围栏
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
    out = {}
    for ax in AXES:
        v = data.get(ax)
        if v is None:  # 逐维正则兜底
            mm = re.search(rf'"{ax}"\s*:\s*(\d+(?:\.\d+)?)', cleaned)
            v = float(mm.group(1)) if mm else None
        out[ax] = float(v) if v is not None else None
    out["reason"] = data.get("reason", "")
    return out


def _anchor_parts(anchors):
    """[加固二] 把锚点样本（图+权威分）编成 few-shot parts，前置到目标图之前。"""
    if not anchors:
        return []
    parts = [{"text": _ANCHOR_INTRO}]
    for i, a in enumerate(anchors, 1):
        in_b64, _ = _img_to_b64(_resolve(a["input_path"]))
        out_b64, _ = _img_to_b64(_resolve(a["output_path"]))
        g = a["scores"]
        grade = "  ".join(f"{ax}={g.get(ax)}" for ax in AXES)
        parts += [
            {"text": f"【基准示例{i}·图1毛坯原图】"},
            {"inlineData": {"mimeType": "image/jpeg", "data": in_b64}},
            {"text": f"【基准示例{i}·图2效果图】"},
            {"inlineData": {"mimeType": "image/jpeg", "data": out_b64}},
            {"text": f"基准示例{i} 的权威评分：{grade}"},
        ]
    parts.append({"text": _ANCHOR_TAIL})
    return parts


def score_pair(input_path, output_path, style="", room_type="", prompt="",
               model=_DEFAULT_MODEL, key=None, timeout=120, anchors=None):
    """对一对图调用视觉 Judge，返回 {分维度..., reason, _usage, _latency, _raw}。

    anchors: 可选的校准锚点列表，每项 {input_path, output_path, scores}（[加固二]）。
             传入后会作为 few-shot 前置，让 Judge 对齐金标准的尺度。
    """
    key = key or _load_key()
    if not key:
        raise RuntimeError("APIYI_KEY 未配置")

    in_b64, in_sz = _img_to_b64(_resolve(input_path))
    out_b64, out_sz = _img_to_b64(_resolve(output_path))
    rubric = _RUBRIC.format(
        style=style or "未指定",
        room_type=room_type or "未指定",
        prompt=(prompt or "")[:_PROMPT_CLIP],
    )
    # 顺序：指令(rubric) → 锚点校准示例(可选) → 目标新图
    parts = [{"text": rubric}]
    parts += _anchor_parts(anchors)
    parts += [
        {"text": "【图1：毛坯原图】"},
        {"inlineData": {"mimeType": "image/jpeg", "data": in_b64}},
        {"text": "【图2：AI 效果图】"},
        {"inlineData": {"mimeType": "image/jpeg", "data": out_b64}},
    ]
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseModalities": ["TEXT"], "temperature": 0.2},
    }
    url = f"{_BASE}/v1beta/models/{model}:generateContent"
    t0 = time.time()
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload, timeout=timeout,
    )
    latency = time.time() - t0
    resp.raise_for_status()
    data = resp.json()
    text = ""
    for cand in data.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            if "text" in part:
                text += part["text"]
    scores = _parse_scores(text)
    scores["_usage"] = data.get("usageMetadata", {})
    scores["_latency"] = latency
    scores["_in_size"] = in_sz
    scores["_out_size"] = out_sz
    scores["_raw"] = text
    return scores


# ----------------------------- 探价 + 小批验证 -----------------------------

def _load_gold():
    g = json.loads(Path(GOLD_LABELS_PATH).read_text(encoding="utf-8"))
    return {e["pair_id"]: e.get("scores", {}) for e in g.get("labels", [])}


def _rated_sorted():
    """返回按人工 overall 升序排好的 [(pair_id, overall)]，以及 pair_id→pair 映射、gold。"""
    pairs = json.loads(Path(METADATA_PATH).read_text(encoding="utf-8"))["pairs"]
    gold = _load_gold()
    pm = {p["pair_id"]: p for p in pairs}
    rated = [(pid, gold[pid].get("overall")) for pid in pm
             if gold.get(pid, {}).get("overall") is not None]
    rated.sort(key=lambda x: x[1])
    return rated, pm, gold


def _pick_anchors(n_anchor, rated, pm, gold):
    """[加固二] 跨低/中/高均匀取 n_anchor 个金标准样本当校准锚点。返回 (anchors, anchor_ids)。"""
    if n_anchor <= 0 or not rated:
        return [], set()
    n_anchor = min(n_anchor, len(rated))
    if n_anchor == 1:
        idxs = [len(rated) // 2]
    else:
        idxs = [round(i * (len(rated) - 1) / (n_anchor - 1)) for i in range(n_anchor)]
    anchors, anchor_ids = [], set()
    for ix in idxs:
        pid = rated[ix][0]
        anchor_ids.add(pid)
        p = pm[pid]
        anchors.append({
            "pair_id": pid,
            "input_path": p["input_path"],
            "output_path": p["output_path"],
            "scores": gold[pid],
        })
    return anchors, anchor_ids


def _pick_pairs(n, rated, pm, exclude_ids):
    """挑验证样本：在排除锚点后，取人工 overall 最低/最高各若干（最能检验 Judge 是否区分好坏）。"""
    avail = [(pid, ov) for pid, ov in rated if pid not in exclude_ids]
    picks = []
    half = max(1, n // 2)
    picks += [pid for pid, _ in avail[:half]]              # 最差的
    picks += [pid for pid, _ in avail[-(n - half):]]       # 最好的
    # 去重并保序，截到 n 条
    seen, ordered = set(), []
    for pid in picks:
        if pid not in seen:
            seen.add(pid)
            ordered.append(pid)
    return [pm[pid] for pid in ordered[:n]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2, help="验证条数（默认2：最低+最高各1）")
    ap.add_argument("--anchor", type=int, default=3,
                    help="校准锚点条数（默认3，跨低/中/高；设0关闭，跑通用尺度做 A/B 对比）")
    ap.add_argument("--model", default=_DEFAULT_MODEL)
    args = ap.parse_args()

    key = _load_key()
    if not key:
        print("❌ 未找到 APIYI_KEY。请二选一后重跑：")
        print("   1) 在项目根或 backend/ 建 .env，写：APIYI_KEY=你的key")
        print("   2) 本会话临时注入：在对话框输入  ! export APIYI_KEY=你的key")
        print("      （注意：export 不一定跨命令保留，推荐用方式1的 .env）")
        sys.exit(2)

    rated, pm, gold = _rated_sorted()
    anchors, anchor_ids = _pick_anchors(args.anchor, rated, pm, gold)
    samples = _pick_pairs(args.n, rated, pm, anchor_ids)

    mode = f"带 {len(anchors)} 个锚点(已校准到你的尺度)" if anchors else "无锚点(通用尺度)"
    print(f"模型：{args.model}　{mode}　验证 {len(samples)} 条（按人工 overall 取两极）")
    if anchors:
        print("锚点样本(留出，不参与验证)：" +
              "  ".join(f"{a['pair_id']}(overall={a['scores'].get('overall')})" for a in anchors))
    print()

    tot_in = tot_out = 0
    ok = 0
    records = []  # (pid, gold_overall, judge_overall)
    for p in samples:
        pid = p["pair_id"]
        g = gold.get(pid, {})
        try:
            r = score_pair(p["input_path"], p["output_path"],
                           style=p.get("style", ""), room_type=p.get("room_type", ""),
                           prompt=p.get("prompt", ""), model=args.model, key=key,
                           anchors=anchors)
        except Exception as e:
            print(f"✗ {pid} 调用失败：{type(e).__name__}: {str(e)[:200]}")
            continue
        ok += 1
        u = r.get("_usage", {})
        pin = u.get("promptTokenCount", 0)
        pout = u.get("candidatesTokenCount", 0)
        tot_in += pin
        tot_out += pout
        records.append((pid, g.get("overall"), r.get("overall")))
        print(f"── {pid}  缩图 {r['_in_size']}/{r['_out_size']}  延迟 {r['_latency']:.1f}s")
        print(f"   视觉Judge : " + "  ".join(f"{ax}={r.get(ax)}" for ax in AXES))
        print(f"   人工金标准: " + "  ".join(f"{ax}={g.get(ax)}" for ax in AXES))
        print(f"   理由: {r.get('reason','')[:120]}")
        print(f"   token: in={pin} out={pout}")
        print()

    # [加固一] 两极判别力判定：Judge 能否像人一样把最差/最好拉开
    valid = [(pid, go, jo) for pid, go, jo in records if go is not None and jo is not None]
    if len(valid) >= 2:
        worst = min(valid, key=lambda x: x[1])
        best = max(valid, key=lambda x: x[1])
        d_gold = best[1] - worst[1]
        d_judge = best[2] - worst[2]
        print("─" * 60)
        print("【判别力检查】视觉Judge 能否像人一样把最差/最好拉开？")
        print(f"  最差样本 {worst[0]}: 人工 overall={worst[1]}  →  视觉Judge overall={worst[2]}")
        print(f"  最好样本 {best[0]}: 人工 overall={best[1]}  →  视觉Judge overall={best[2]}")
        print(f"  金标准两极分差 Δ_gold={d_gold:+.1f}　视觉Judge两极分差 Δ_judge={d_judge:+.1f}")
        if d_judge <= 0:
            print("  🔴 不合格：Judge 没把好坏拉开（Δ_judge≤0），与旧 llm_judge 同病——不要往下花钱跑全量。")
        elif d_judge < d_gold * 0.5:
            print("  🟡 偏弱：Judge 有方向但分差不足金标准一半，可疑，建议加大样本量再判，慎重投钱。")
        else:
            print("  🟢 通过初判：Judge 把两极拉开了，方向与人工一致，值得扩到全量算 Spearman。")
        print("─" * 60)
    elif ok:
        print("（验证条数<2 或缺金标准，跳过两极判别力判定；建议 --n 2 起步）")

    if ok:
        anchor_imgs = len(anchors) * 2  # 每个锚点 2 张图，是带锚后每次调用的固定额外开销
        print("=" * 60)
        print(f"探价汇总（{ok} 次成功调用，每次含 {anchor_imgs} 张锚点图 + 2 张目标图）：")
        print(f"  平均输入 token/次 ≈ {tot_in/ok:.0f}　平均输出 token/次 ≈ {tot_out/ok:.0f}")
        print(f"  → 全量一轮(85条)预计 in≈{tot_in/ok*85/1000:.0f}k / out≈{tot_out/ok*85/1000:.1f}k token")
        print(f"  → 投票纠偏(85×3)预计 in≈{tot_in/ok*255/1000:.0f}k / out≈{tot_out/ok*255/1000:.1f}k token")
        if anchors:
            print("  注：锚点图使每次输入 token 增大（多 {} 张图），是对齐你尺度的成本；".format(anchor_imgs))
            print("      若想看不带锚的便宜版单价，加 --anchor 0 再跑一次对比。")
        print("  实际人民币花费 = 上述 token × apiyi 对该模型的单价（请按你账号实际费率核算）。")
        print("=" * 60)


if __name__ == "__main__":
    main()
