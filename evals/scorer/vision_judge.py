"""视觉 Judge（阶段 3）——真正"看见图"的多维评分器。

补齐本地算法做不到的两维：**美学质量 / 指令遵循**（语义问题，只能由视觉模型判）。
设计蓝图见 VISION_JUDGE_DESIGN.md。本文件提供可复用的打分函数 + 一个
「探单价 + 小批验证」的命令行入口（第一步，不写回任何数据、不进 registry）。

红线：未通过 VISION_JUDGE_DESIGN.md 第5节验收前，分不得用于任何自动决策。

用法（需先配好 APIYI_KEY，见下方 _load_key）：
  python -m evals.scorer.vision_judge              # 探价+验证：自动挑金标准最高/最低各1条
  python -m evals.scorer.vision_judge --n 2        # 控制验证条数
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

_RUBRIC = """你是资深室内设计评审。下面【图1】是装修前的毛坯原图，【图2】是 AI 基于它生成的效果图。
目标风格：{style}；房间类型：{room_type}；用户需求：{prompt}。
请严格独立评分（1-5 分，可给低分），只输出 JSON：
{{
  "structural": <1-5>,   // 毛坯的墙体/门窗/承重/户型结构是否被如实保留，未被乱改
  "aesthetic":  <1-5>,   // 设计感/配色/材质/光影/整体美观
  "instruction":<1-5>,   // 是否符合目标风格/房型/需求
  "overall":    <1-5>,   // 综合主观评价
  "reason": "<两句话理由，先说硬伤>"
}}
只输出 JSON。烂图必须敢给 1-2 分。"""


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


def score_pair(input_path, output_path, style="", room_type="", prompt="",
               model=_DEFAULT_MODEL, key=None, timeout=120):
    """对一对图调用视觉 Judge，返回 {分维度..., reason, _usage, _latency, _raw}。"""
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
    payload = {
        "contents": [{"parts": [
            {"text": rubric},
            {"text": "【图1：毛坯原图】"},
            {"inlineData": {"mimeType": "image/jpeg", "data": in_b64}},
            {"text": "【图2：AI 效果图】"},
            {"inlineData": {"mimeType": "image/jpeg", "data": out_b64}},
        ]}],
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


def _pick_pairs(n):
    """挑验证样本：默认取人工 overall 最低/最高各若干，最能检验 Judge 是否会区分好坏。"""
    pairs = json.loads(Path(METADATA_PATH).read_text(encoding="utf-8"))["pairs"]
    gold = _load_gold()
    pm = {p["pair_id"]: p for p in pairs}
    rated = [(pid, gold[pid].get("overall")) for pid in pm if gold.get(pid, {}).get("overall") is not None]
    rated.sort(key=lambda x: x[1])
    picks = []
    half = max(1, n // 2)
    picks += [pid for pid, _ in rated[:half]]              # 最差的
    picks += [pid for pid, _ in rated[-(n - half):]]       # 最好的
    return [pm[pid] for pid in picks[:n]], gold


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2, help="验证条数（默认2：最低+最高各1）")
    ap.add_argument("--model", default=_DEFAULT_MODEL)
    args = ap.parse_args()

    key = _load_key()
    if not key:
        print("❌ 未找到 APIYI_KEY。请二选一后重跑：")
        print("   1) 在项目根或 backend/ 建 .env，写：APIYI_KEY=你的key")
        print("   2) 本会话临时注入：在对话框输入  ! export APIYI_KEY=你的key")
        print("      （注意：export 不一定跨命令保留，推荐用方式1的 .env）")
        sys.exit(2)

    samples, gold = _pick_pairs(args.n)
    print(f"模型：{args.model}　验证 {len(samples)} 条（按人工 overall 取两极）\n")

    tot_in = tot_out = 0
    ok = 0
    for p in samples:
        pid = p["pair_id"]
        g = gold.get(pid, {})
        try:
            r = score_pair(p["input_path"], p["output_path"],
                           style=p.get("style", ""), room_type=p.get("room_type", ""),
                           prompt=p.get("prompt", ""), model=args.model, key=key)
        except Exception as e:
            print(f"✗ {pid} 调用失败：{type(e).__name__}: {str(e)[:200]}")
            continue
        ok += 1
        u = r.get("_usage", {})
        pin = u.get("promptTokenCount", 0)
        pout = u.get("candidatesTokenCount", 0)
        tot_in += pin
        tot_out += pout
        print(f"── {pid}  缩图 {r['_in_size']}/{r['_out_size']}  延迟 {r['_latency']:.1f}s")
        print(f"   视觉Judge : " + "  ".join(f"{ax}={r.get(ax)}" for ax in AXES))
        print(f"   人工金标准: " + "  ".join(f"{ax}={g.get(ax)}" for ax in AXES))
        print(f"   理由: {r.get('reason','')[:120]}")
        print(f"   token: in={pin} out={pout}")
        print()

    if ok:
        print("=" * 60)
        print(f"探价汇总（{ok} 次成功调用）：")
        print(f"  平均输入 token/次 ≈ {tot_in/ok:.0f}　平均输出 token/次 ≈ {tot_out/ok:.0f}")
        print(f"  → 全量一轮(85条)预计 in≈{tot_in/ok*85/1000:.0f}k / out≈{tot_out/ok*85/1000:.1f}k token")
        print(f"  → 投票纠偏(85×3)预计 in≈{tot_in/ok*255/1000:.0f}k / out≈{tot_out/ok*255/1000:.1f}k token")
        print("  实际人民币花费 = 上述 token × apiyi 对该模型的单价（请按你账号实际费率核算）。")
        print("=" * 60)


if __name__ == "__main__":
    main()
