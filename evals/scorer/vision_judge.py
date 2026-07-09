"""视觉 Judge（阶段 3）——真正"看见图"的评分器。v2 重写（2026-06-30）。

补齐本地算法做不到的两维：**指令遵循 / 美学质量**（语义问题，只能由视觉模型判）。
**结构保真不在此处**——由非 VLM 的 structural_fidelity 负责（结构/几何畸变是 VLM 最弱维，见 RESEARCH_IMAGE_EVAL.md F6）。

设计依据：`VISION_JUDGE_DESIGN.md` 第7节 v2 修正 + `RESEARCH_IMAGE_EVAL.md`。
核心修正：**抛弃「四维 1-5 标量打分」**（MLLM 直接打标量分与人类对不齐），改为——
  - 指令遵循 → **VQA 点评**：把"是否遵循"拆成一串是非题，逐条 yes/no → 加总成 [0,1] 分（VQAScore/TIFA 思路）。
  - 美学质量 → **成对 A/B**：两个效果图比哪个更美，正反各跑一次消位置偏见（视觉质量上成对 > 点评）。

v2.1（2026-07-09，对齐课程 judge prompt 模板·张和老师 grader 模块）：
  1. reason 前置于 verdict —— 自回归模型先写结论再补理由等于没推理（课程 {"reasoning","answer"} 顺序）。
  2. 每题写清 pass/fail 判据 —— "任务清晰、失败/成功标准清晰"。
  3. 退出机制 —— verdict 允许 "na"（依据不足），na 不计入分母（课程"给LLM留退出机制"）。
  4. few-shot 嵌入 —— 从 judge_split 的 few-shot 池取人工判定+critique 文本示例校准严格度；
     池外样本永不入 prompt（防泄漏）。划分文件缺失时自动退化为无 few-shot。

通道（2026-06-30 实测确定）：apiyi 这把 key 仅开通图像模型通道，纯理解模型 gemini-2.5-flash「无可用通道」。
但 **gemini-2.5-flash-image 走 OpenAI 兼容端点 `/v1/chat/completions` 能读图+输出文字**，实测可用，故采之。
（更高质量可换 gemini-3-pro-image-preview，更贵。）

红线：未通过 VISION_JUDGE_DESIGN.md 第5节验收前，分不得用于任何自动决策。
本文件不写回数据、不进 registry；需先配 APIYI_KEY（见 _load_key）。

用法：
  python -m evals.scorer.vision_judge                    # 默认 vqa：金标准两极各1条，验证指令 VQA 的判别力
  python -m evals.scorer.vision_judge --mode vqa --n 2
  python -m evals.scorer.vision_judge --mode pairwise    # 取美学两极的两张效果图，验证成对能否选对更美的
  python -m evals.scorer.vision_judge --model gemini-3-pro-image-preview
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
_CHAT_URL = f"{_BASE}/v1/chat/completions"   # OpenAI 兼容端点（这把 key 唯一能跑通图像模型理解的路）
_DEFAULT_MODEL = "gpt-4o"                     # 图像理解评委（VIEScore 同款）；用 GRADER_APIYI_KEY 专用通道
_MAX_DIM = 768                               # 缩图上限，控 token（语义判断不需原分辨率）
_PROMPT_CLIP = 300                           # 截断超长 prompt


# ============================ 基础设施 ============================

_KEY_NAMES = ("GRADER_APIYI_KEY", "APIYI_KEY", "LLM_APIYI_KEY")  # grader 专用 key 优先


def _load_key():
    """取评测 key：优先 GRADER_APIYI_KEY（图像理解评委专用），回退产品 key。
    先环境变量，再 backend/.env 与根 .env（手动解析，不依赖 dotenv）。"""
    for name in _KEY_NAMES:
        if os.getenv(name):
            return os.getenv(name)
    found = {}  # 收集 .env 里所有匹配项，最后按 _KEY_NAMES 优先级返回（而非文件顺序）
    for envf in (PROJECT_ROOT / "backend" / ".env", PROJECT_ROOT / ".env"):
        if not envf.exists():
            continue
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            if k in _KEY_NAMES and k not in found:
                v = v.strip().strip('"').strip("'")
                if v and not v.startswith("your_"):
                    found[k] = v
    for name in _KEY_NAMES:   # 按优先级取
        if name in found:
            return found[name]
    return None


def _resolve(path):
    p = Path(path)
    if p.is_absolute():
        return p
    if str(path).startswith("data/"):
        return EVALS_DIR / p
    return PROJECT_ROOT / p


def _img_data_uri(path, max_dim=_MAX_DIM):
    """缩图到 max_dim 内，转 JPEG base64 的 data URI（OpenAI image_url 格式）。返回 (uri, 尺寸)。"""
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_dim, max_dim))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}", img.size


def _text(t):
    return {"type": "text", "text": t}


def _image(uri):
    return {"type": "image_url", "image_url": {"url": uri}}


def _extract_json(text):
    """从模型输出抽 JSON（对象或数组），带围栏剥离 + 兜底。"""
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        return json.loads(m.group(0)) if m else None


def _call_api(content, model, key, max_tokens=800, timeout=120):
    """单次调用 OpenAI 兼容 /v1/chat/completions（apiyi）。返回 (text, usage, latency)。"""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    t0 = time.time()
    resp = requests.post(
        _CHAT_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload, timeout=timeout,
    )
    latency = time.time() - t0
    resp.raise_for_status()
    data = resp.json()
    msg = (data.get("choices") or [{}])[0].get("message", {})
    text = msg.get("content") or ""
    return text, data.get("usage", {}), latency


def _tok(usage):
    """归一 token 用量 → (in, out)。OpenAI 格式用 prompt_tokens/completion_tokens。"""
    return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


# ============================ v2-A：指令遵循 VQA ============================
# 把"是否遵循指令"拆成产品相关的是非题，逐条 yes/no → 加总成 [0,1] 分。
# 结构题作为"次要交叉校验"（primary 结构分用 structural_fidelity），可关。

# 题目三元组：(id, 文本, 需要 room_type)。房型匹配是实测的头号失败维（71% 跑偏 → 模型爱默认产客厅），
# 故列首位并作"失败门"：房型跑偏 → 指令分直接封顶到 _ROOM_FAIL_CAP（frenkie 裁定：房型跑偏=严重失败）。
_ROOM_FAIL_CAP = 0.34
_VQA_INSTRUCTION = [
    ("inst_room",
     "效果图呈现的房间功能是否与目标房型「{room_type}」一致？"
     "判据：以家具功能识别房间——床=卧室、灶台/橱柜=厨房、沙发+电视墙=客厅、餐桌为主=餐厅、"
     "马桶/浴缸/洗手台=卫生间、书桌书架=书房、晾晒/户外休闲=阳台。"
     "功能一致答 yes；跑成其他房型答 no（房型跑偏=严重失败）。此题禁用 na。", True),
    ("inst_style",
     "效果图整体是否符合目标风格「{style}」？"
     "判据：从配色/材质/家具造型/装饰元素判断，主体特征明显属于该风格答 yes；"
     "风格特征缺失、或混杂到认不出目标风格答 no。此题禁用 na。", False),
    ("inst_need",
     "是否满足用户需求「{prompt}」中的关键点？"
     "判据：先从需求中提取可核验要点（颜色/材质/家具/布局等），逐一在图中查证；"
     "关键要点大多可见答 yes；关键要点缺失或与需求相反答 no；"
     "需求过于空泛、提不出可核验要点时答 na。", False),
]
_VQA_STRUCTURE = [  # 次要交叉校验；primary 结构分=structural_fidelity
    ("struct_walls", "对比【图1】毛坯：墙体/隔断的位置是否被如实保留、未被乱改？"
                     "位置一致答 yes；新增/拆除/移动了墙体答 no。", False),
    ("struct_openings", "门窗的位置与数量是否与【图1】毛坯基本一致？"
                        "基本一致答 yes；位置明显移动或数量增减答 no。", False),
]

_VQA_PROMPT = """你是资深室内设计评审。【图1】是装修前的毛坯原图，【图2】是 AI 基于它生成的效果图。
目标风格：{style}；房间类型：{room_type}；用户需求：{prompt}。
{fewshot}请对【图2】逐条回答下列是非题。每题先写一句话分析（reason），再依据题内判据下结论（verdict）。
verdict 只能取 "yes" / "no" / "na"——na 表示依据不足无法判断，仅在题目判据明确允许时使用。
**效果差就果断答 no，不要客气。**
题目：
{questions}
只输出 JSON 数组，每元素形如 {{"id":"题号","reason":"你的一句话分析","verdict":"yes"或"no"或"na"}}。
注意：reason 字段必须写在 verdict 之前（先分析后结论）。不要输出多余文字。"""


def _fewshot_block(max_per_class: int = 2) -> str:
    """从 judge_split 的 few-shot 池取人工判定+critique，文本化嵌入 prompt 校准严格度。

    池外样本永不入 prompt（防泄漏，few-shot 池不参与任何对齐度/TPR-TNR 计算）。
    few-shot 是增强项：划分缺失、池空、任何异常都静默退化为空串，不阻断打分。
    """
    try:
        from evals.dataset.judge_split import pair_ids
        from evals.scorer.gold_store import GoldStore, effective_binary

        from evals.scorer.gold_store import is_excluded

        pool = pair_ids("fewshot")
        if not pool:
            return ""
        gold = GoldStore().load()
        pairs = {p["pair_id"]: p for p in
                 json.loads(Path(METADATA_PATH).read_text(encoding="utf-8"))["pairs"]}
        by_class = {"pass": [], "fail": []}
        for pid in pool:
            e = gold.get(pid) or {}
            if is_excluded(e):   # 评测集缺陷 case 不当示例（其判词描述的是题目缺陷而非输出质量）
                continue
            v, _src = effective_binary(e)
            if v not in by_class:
                continue
            p = pairs.get(pid, {})
            # critique 是专为喂 judge 写的一句话判词，优先；notes 常混入数据集管理碎碎念，
            # 仅当"短且非疑问句"（像判词而非备忘）时才兜底使用。
            why = (e.get("critique") or "").strip()
            if not why:
                note = (e.get("notes") or "").strip()
                if note and len(note) <= 30 and "？" not in note and "?" not in note:
                    why = note
            desc = f"目标风格={p.get('style') or '未指定'}/房型={p.get('room_type') or '未指定'}"
            line = (f"  - 人工判定={'通过' if v == 'pass' else '失败'}（{desc}）"
                    + (f"：{why}" if why else ""))
            by_class[v].append(line)
        lines = by_class["fail"][:max_per_class] + by_class["pass"][:max_per_class]
        if not lines:
            return ""
        return ("判断严格度校准示例（人类专家对同类任务的裁决，请对齐这个严格度）：\n"
                + "\n".join(lines) + "\n")
    except Exception:
        return ""


def _norm_verdict(v) -> str:
    """归一 verdict → "yes"/"no"/"na"/""。注意 "na" 与 "no" 同以 n 开头，必须精确匹配。"""
    v = str(v or "").strip().lower()
    if v in ("yes", "y", "是"):
        return "yes"
    if v in ("no", "n", "否"):
        return "no"
    if v in ("na", "n/a", "unknown", "uncertain", "无法判断"):
        return "na"
    return ""


def score_instruction_vqa(input_path, output_path, style="", room_type="", prompt="",
                          include_structure=False, model=_DEFAULT_MODEL, key=None,
                          timeout=120, fewshot=True):
    """指令遵循 VQA 打分。返回 {score:[0,1], n_yes, n_total, n_na, items:[...], _usage,_latency,_raw}。

    score = yes 数 / 有效题数（verdict∈{yes,no}）；na（退出机制）与解析失败均不计入分母。
    include_structure=True 时附带结构交叉校验题（不计入主分）。
    fewshot=True 时嵌入 judge_split few-shot 池的人工裁决示例（池缺失自动退化）。
    """
    key = key or _load_key()
    if not key:
        raise RuntimeError("APIYI_KEY 未配置")

    has_room = bool(room_type)
    # 房型题仅在有房型标注时纳入（未指定房型无可跑偏）
    active = [(qid, q) for qid, q, req in _VQA_INSTRUCTION if has_room or not req]
    struct = [(qid, q) for qid, q, _r in _VQA_STRUCTURE] if include_structure else []
    qs = active + struct
    fmt = dict(style=style or "未指定", room_type=room_type or "未指定", prompt=(prompt or "")[:_PROMPT_CLIP])
    q_text = "\n".join(f"  [{qid}] {q.format(**fmt)}" for qid, q in qs)
    prompt_text = _VQA_PROMPT.format(questions=q_text,
                                     fewshot=(_fewshot_block() if fewshot else ""), **fmt)

    in_uri, _ = _img_data_uri(_resolve(input_path))
    out_uri, _ = _img_data_uri(_resolve(output_path))
    content = [_text(prompt_text), _text("【图1：毛坯原图】"), _image(in_uri),
               _text("【图2：AI 效果图】"), _image(out_uri)]

    text, usage, latency = _call_api(content, model, key, max_tokens=800, timeout=timeout)
    data = _extract_json(text) or []
    by_id = {d.get("id"): d for d in data if isinstance(d, dict)}
    items, n_yes, n_total, n_na = [], 0, 0, 0
    inst_ids = {qid for qid, _ in active}
    room_no = False
    for qid, _q in qs:
        d = by_id.get(qid, {})
        v = _norm_verdict(d.get("verdict"))
        items.append({"id": qid, "verdict": v or "?", "reason": d.get("reason", "")})
        if qid == "inst_room" and v == "no":
            room_no = True
        if qid in inst_ids:  # 只有指令题计入主分
            if v in ("yes", "no"):   # 有效判定才进分母（na/解析失败→不计，避免假0分）
                n_total += 1
                n_yes += (v == "yes")
            elif v == "na":
                n_na += 1
    score = (n_yes / n_total) if n_total else None   # 全部 na/解析失败→None，不污染判别力
    if score is not None and room_no:                # 房型跑偏=失败门：封顶到 _ROOM_FAIL_CAP
        score = min(score, _ROOM_FAIL_CAP)
    return {
        "score": score, "n_yes": n_yes, "n_total": n_total, "n_na": n_na,
        "room_mismatch": room_no,
        "items": items, "_usage": usage, "_latency": latency, "_raw": text,
    }


# ============================ v2-B：美学成对 A/B ============================
# 两个效果图比哪个更美；正反各跑一次消位置偏见。

_PAIRWISE_PROMPT = """你是资深室内设计评审。{intro}
请**只就美学质量**（设计感 / 配色 / 材质 / 光影 / 整体美观）判断哪个方案更好{no_ref}。
只输出 JSON：{{"winner":"A"或"B"或"tie","reason":"一句话理由"}}，不要多余文字。"""


def _pairwise_once(in_uri, a_uri, b_uri, style, room_type, model, key, timeout):
    if in_uri:
        intro = (f"【图1】是装修前的毛坯原图，仅供了解原始空间。"
                 f"【方案A】和【方案B】是两个 AI 效果图。"
                 f"目标风格：{style or '未指定'}；房间类型：{room_type or '未指定'}。")
        no_ref = "，与谁更像毛坯无关"
    else:
        intro = "【方案A】和【方案B】是两张 AI 室内设计效果图（可能来自不同房间，忽略户型差异）。"
        no_ref = ""
    content = [_text(_PAIRWISE_PROMPT.format(intro=intro, no_ref=no_ref))]
    if in_uri:
        content += [_text("【图1：毛坯原图】"), _image(in_uri)]
    content += [_text("【方案A】"), _image(a_uri),
                _text("【方案B】"), _image(b_uri)]
    text, usage, latency = _call_api(content, model, key, max_tokens=200, timeout=timeout)
    data = _extract_json(text) or {}
    w = str(data.get("winner", "")).strip().upper()
    return (w if w in ("A", "B", "TIE") else "TIE"), data.get("reason", ""), usage, latency


def compare_pairwise(input_path, output_a, output_b, style="", room_type="",
                     model=_DEFAULT_MODEL, key=None, timeout=120):
    """美学成对比较。正反各跑一次（A/B 与 B/A）消位置偏见。

    input_path=None 时做纯美学对比（跨 case 对比用：不展示毛坯参考图，省 token 且不误导）。
    返回 {winner:'A'/'B'/'tie', order1, order2, consistent, reasons, _usage,_latency}。
    winner='A' 仅当两序都判 A 更美（或一序 A 一序 tie 偏 A）；两序矛盾→tie（位置偏见，存疑）。
    """
    key = key or _load_key()
    if not key:
        raise RuntimeError("APIYI_KEY 未配置")
    in_uri = _img_data_uri(_resolve(input_path))[0] if input_path else None
    a_uri, _ = _img_data_uri(_resolve(output_a))
    b_uri, _ = _img_data_uri(_resolve(output_b))

    # 序1：A=output_a, B=output_b
    w1, r1, u1, l1 = _pairwise_once(in_uri, a_uri, b_uri, style, room_type, model, key, timeout)
    # 序2：交换位置，A=output_b, B=output_a → 把结果映射回原 A/B 语义
    w2raw, r2, u2, l2 = _pairwise_once(in_uri, b_uri, a_uri, style, room_type, model, key, timeout)
    w2 = {"A": "B", "B": "A", "TIE": "TIE"}[w2raw]

    if w1 == w2 and w1 in ("A", "B"):
        winner = w1.lower()
    elif {w1, w2} == {"A", "TIE"}:   # 一序判A一序判平 → 偏A
        winner = "a"
    elif {w1, w2} == {"B", "TIE"}:   # 一序判B一序判平 → 偏B
        winner = "b"
    else:
        winner = "tie"  # 两序皆平，或两序矛盾(位置偏见)→存疑
    p1i, p1o = _tok(u1); p2i, p2o = _tok(u2)
    usage = {"prompt_tokens": p1i + p2i, "completion_tokens": p1o + p2o}
    return {
        "winner": winner, "order1": w1.lower(), "order2": w2.lower(),
        "consistent": (w1 == w2), "reasons": [r1, r2],
        "_usage": usage, "_latency": l1 + l2,
    }


# ============================ 金标准 / 取样 ============================

def _load_gold():
    g = json.loads(Path(GOLD_LABELS_PATH).read_text(encoding="utf-8"))
    return {e["pair_id"]: e.get("scores", {}) for e in g.get("labels", [])}


def _pairs_by_gold(axis):
    """返回按指定金标准维度(overall/aesthetic/instruction…)升序排好的 [(pair, score)]，及 gold。"""
    pairs = json.loads(Path(METADATA_PATH).read_text(encoding="utf-8"))["pairs"]
    gold = _load_gold()
    pm = {p["pair_id"]: p for p in pairs}
    rated = [(pm[pid], gold[pid].get(axis)) for pid in pm
             if gold.get(pid, {}).get(axis) is not None]
    rated.sort(key=lambda x: x[1])
    return rated, gold


# ============================ CLI：小批验证（不写回） ============================

def _run_vqa(args, key):
    rated, gold = _pairs_by_gold("instruction")
    half = max(1, args.n // 2)
    samples = [p for p, _ in rated[:half]] + [p for p, _ in rated[-(args.n - half):]]
    print(f"模型：{args.model}　模式 VQA(指令遵循)　验证 {len(samples)} 条（按人工 instruction 取两极）\n")
    tot_in = tot_out = 0
    recs = []
    for p in samples:
        pid = p["pair_id"]
        g = gold.get(pid, {})
        try:
            r = score_instruction_vqa(p["input_path"], p["output_path"], style=p.get("style", ""),
                                      room_type=p.get("room_type", ""), prompt=p.get("prompt", ""),
                                      include_structure=args.structure, model=args.model, key=key)
        except Exception as e:
            print(f"✗ {pid} 调用失败：{type(e).__name__}: {str(e)[:200]}")
            continue
        ti, to = _tok(r["_usage"]); tot_in += ti; tot_out += to
        recs.append((pid, g.get("instruction"), r["score"]))
        na_note = f", na {r['n_na']}" if r.get("n_na") else ""
        print(f"── {pid}  延迟 {r['_latency']:.1f}s  VQA指令分={r['score']}  (yes {r['n_yes']}/{r['n_total']}{na_note})")
        for it in r["items"]:
            print(f"     [{it['id']}] {it['verdict']:3s} {it['reason'][:50]}")
        print(f"   人工 instruction 金标准={g.get('instruction')}\n")
    _discrimination(recs, "VQA指令分", "instruction")
    _cost(tot_in, tot_out, len(recs))


def _run_pairwise(args, key):
    rated, gold = _pairs_by_gold("aesthetic")
    if len(rated) < 2:
        print("金标准美学维样本不足，无法成对验证。"); return
    low, high = rated[0][0], rated[-1][0]
    gl, gh = rated[0][1], rated[-1][1]
    print(f"模型：{args.model}　模式 成对(美学)　取美学两极：")
    print(f"  方案A={low['pair_id']}(人工美学={gl})  方案B={high['pair_id']}(人工美学={gh})")
    print(f"  期望：Judge 应判 B 更美（人工分更高）。正反各跑一次消位置偏见。\n")
    try:
        r = compare_pairwise(low["input_path"], low["output_path"], high["output_path"],
                             style=high.get("style", ""), room_type=high.get("room_type", ""),
                             model=args.model, key=key)
    except Exception as e:
        print(f"✗ 调用失败：{type(e).__name__}: {str(e)[:200]}"); return
    print(f"  序1判={r['order1']}  序2判={r['order2']}  一致={r['consistent']}  → 最终 winner={r['winner']}")
    print(f"  理由: {r['reasons']}")
    ok = (r["winner"] == "b")
    print("\n" + "─" * 56)
    if ok:
        print("  🟢 通过：Judge 选对了更美的方案，且两序一致性见上。")
    elif r["winner"] == "tie":
        print("  🟡 存疑：两序矛盾(位置偏见)或判平，需加样本再看。")
    else:
        print("  🔴 不合格：Judge 把更丑的判成更美——美学成对不可信，不要往下花钱。")
    print("─" * 56)
    ti, to = _tok(r["_usage"])
    _cost(ti, to, 1, note="(含正反两次调用)")


def _discrimination(recs, judge_name, gold_axis):
    valid = [(pid, g, j) for pid, g, j in recs if g is not None and j is not None]
    if len(valid) < 2:
        print("（有效样本<2，跳过两极判别力判定）"); return
    worst = min(valid, key=lambda x: x[1]); best = max(valid, key=lambda x: x[1])
    dg = best[1] - worst[1]; dj = best[2] - worst[2]
    print("─" * 56)
    print(f"【判别力】最差 {worst[0]}(人工{gold_axis}={worst[1]}→{judge_name}={worst[2]}) vs 最好 {best[0]}({best[1]}→{best[2]})")
    print(f"  金标准两极差={dg:+.2f}　{judge_name}两极差={dj:+.3f}")
    if dj <= 0:
        print("  🔴 不合格：Judge 没把好坏拉开（同 llm_judge 病），不要往下花钱。")
    else:
        print("  🟢 方向一致：Judge 把两极拉开了，值得扩样算 Spearman。")
    print("─" * 56)


def _cost(tin, tout, n, note=""):
    if not n:
        return
    print("=" * 56)
    print(f"探价（{n} 次成功调用 {note}）：均输入≈{tin/n:.0f} / 输出≈{tout/n:.0f} token/次")
    print(f"  → 全量85条预计 in≈{tin/n*85/1000:.0f}k / out≈{tout/n*85/1000:.1f}k token；实际人民币=token×apiyi 费率")
    print("=" * 56)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["vqa", "pairwise"], default="vqa")
    ap.add_argument("--n", type=int, default=2, help="vqa 模式验证条数（默认2：最低+最高各1）")
    ap.add_argument("--structure", action="store_true", help="vqa 附带结构交叉校验题（不计入主分）")
    ap.add_argument("--model", default=_DEFAULT_MODEL)
    args = ap.parse_args()

    key = _load_key()
    if not key:
        print("❌ 未找到 APIYI_KEY。请二选一后重跑：")
        print("   1) 在项目根或 backend/ 建 .env，写：APIYI_KEY=你的key")
        print("   2) 本会话临时注入：在对话框输入  ! export APIYI_KEY=你的key")
        sys.exit(2)

    (_run_vqa if args.mode == "vqa" else _run_pairwise)(args, key)


if __name__ == "__main__":
    main()
