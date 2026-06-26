"""评测集深化（路径 A）：激活切片能力 + 产出「模型在哪类输入失分」地图。

做三件事，且**幂等**（可反复运行，结果不漂移）：
1. 从文件名回填 `room_type` 与结构难度 `tags`（小户型/异形户型/复式/横梁/杂物/地下室）。
   —— 识别不出房型的就留空，绝不硬造。
2. 从人工金标准 `overall` 反推 `difficulty`（hard/medium/easy）。
3. 把上述写回 real_metadata.json（源头，runner 重跑会自动携带）与 eval_results.json
   （看板当下即可切片，无需重算分），并打印失败地图。

设计原则（第一性原理）：
- room_type/tags = 输入的**固有属性**（看文件名即可定），写进 real_metadata。
- difficulty = 人工 overall 反推的**模型表现/结果**，不是输入属性，单独成字段，
  不混入输入 tags —— 这样才能做「输入属性 × 失败结果」的交叉分析。
- 结构难度标签与**唯一可信评分器 structural_fidelity** 对齐，使切片分析有可信尺子支撑。

用法：python -m evals.dataset.enrich          # 干跑，只看地图，不写文件
      python -m evals.dataset.enrich --write  # 写回两份数据文件
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from evals.config import METADATA_PATH as REAL_METADATA_PATH
from evals.config import EVAL_RESULTS_PATH, GOLD_LABELS_PATH

# 文件名子串 → 房型（规范英文）。命中即取，识别不出留空。
ROOM_RULES = [
    (("卧室", "bedroom"), "bedroom"),
    (("客厅", "living"), "living_room"),
    (("厨房", "kitchen"), "kitchen"),
    (("餐厅", "dining"), "dining_room"),
    (("阳台", "balcony"), "balcony"),
    (("书房", "study"), "study"),
    (("卫生", "浴", "bathroom"), "bathroom"),
]

# 文件名子串 → 结构难度标签。一个样本可命中多个。
TAG_RULES = [
    (("小户型", "small_apartment", "small_"), "small_space"),
    (("异形", "irregular"), "irregular_layout"),
    (("复式", "duplex"), "duplex"),
    (("横梁", "beam"), "exposed_beam"),
    (("杂物", "cluttered", "storage"), "cluttered"),
    (("basement", "地下室"), "basement"),
]


def _match(blob, rules):
    """blob 命中任一规则则返回其标签；rules 为 (子串元组, 标签) 列表。"""
    out = []
    for needles, label in rules:
        if any(n.lower() in blob for n in needles):
            out.append(label)
    return out


def derive_room_type(input_path):
    blob = input_path.lower()
    hits = _match(blob, ROOM_RULES)
    return hits[0] if hits else ""  # 取第一个命中；识别不出留空


def derive_tags(input_path):
    blob = input_path.lower()
    return _match(blob, TAG_RULES)  # 可能为空列表


def difficulty_from_overall(overall):
    """人工 overall(1-5) → 难度档。overall 越低 = 模型越搞砸 = 越难。"""
    if overall is None:
        return ""
    if overall <= 2:
        return "hard"
    if overall <= 3:
        return "medium"
    return "easy"


def load_gold_overall():
    """pair_id -> {overall, structural} 人工金标准（真值）。"""
    g = json.loads(Path(GOLD_LABELS_PATH).read_text(encoding="utf-8"))
    out = {}
    for e in g.get("labels", []):
        sc = e.get("scores", {})
        out[e["pair_id"]] = {
            "overall": sc.get("overall"),
            "structural": sc.get("structural"),
        }
    return out


def enrich(write=False):
    real = json.loads(Path(REAL_METADATA_PATH).read_text(encoding="utf-8"))
    results = json.loads(Path(EVAL_RESULTS_PATH).read_text(encoding="utf-8"))
    gold = load_gold_overall()

    # pair_id -> 派生属性
    derived = {}
    for p in real["pairs"]:
        pid = p["pair_id"]
        ip = p["input_path"]
        g = gold.get(pid, {})
        derived[pid] = {
            "room_type": derive_room_type(ip),
            "tags": derive_tags(ip),
            "difficulty": difficulty_from_overall(g.get("overall")),
            "gold_overall": g.get("overall"),
            "gold_structural": g.get("structural"),
        }

    # 写回 real_metadata（输入固有属性：room_type / tags）
    for p in real["pairs"]:
        d = derived[p["pair_id"]]
        p["room_type"] = d["room_type"]
        p["tags"] = d["tags"]

    # 写回 eval_results.metadata（看板切片：room_type / tags / difficulty）
    for r in results["results"]:
        d = derived.get(r["pair_id"], {})
        md = r.setdefault("metadata", {})
        md["room_type"] = d.get("room_type", "")
        md["tags"] = d.get("tags", [])
        md["difficulty"] = d.get("difficulty", "")

    if write:
        _atomic_write(REAL_METADATA_PATH, real)
        _atomic_write(EVAL_RESULTS_PATH, results)
        print(f"✅ 已写回 {REAL_METADATA_PATH}")
        print(f"✅ 已写回 {EVAL_RESULTS_PATH}")
    else:
        print("（干跑：未写文件，加 --write 才落盘）")

    print_failure_map(results["results"], derived)
    return derived


def _atomic_write(path, obj):
    path = str(path)
    tmp = path + ".tmp"
    Path(tmp).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(tmp).replace(path)


def _fmt_slice(name, rows):
    """rows: [(auto_struct, gold_overall, difficulty)]，打印一行切片统计。"""
    n = len(rows)
    autos = [a for a, _, _ in rows if a is not None]
    golds = [g for _, g, _ in rows if g is not None]
    hard = sum(1 for _, _, d in rows if d == "hard")
    avg_auto = sum(autos) / len(autos) if autos else float("nan")
    avg_gold = sum(golds) / len(golds) if golds else float("nan")
    print(f"  {name:18s} n={n:3d}  hard={hard:2d}({hard*100//n if n else 0:3d}%)  "
          f"结构保真(可信)均值={avg_auto:5.1f}  人工overall均值={avg_gold:4.2f}")


def print_failure_map(results, derived):
    """失败地图：各切片下 structural_fidelity(可信) 与人工 overall 的均值 + hard 占比。"""
    by_split = defaultdict(list)
    by_room = defaultdict(list)
    by_tag = defaultdict(list)
    by_diff = defaultdict(list)

    for r in results:
        pid = r["pair_id"]
        d = derived.get(pid, {})
        auto = r.get("scores", {}).get("structural_fidelity")
        gold_overall = d.get("gold_overall")
        diff = d.get("difficulty", "")
        row = (auto, gold_overall, diff)

        by_split[r.get("metadata", {}).get("split", "?")].append(row)
        by_room[d.get("room_type") or "(未识别)"].append(row)
        by_diff[diff or "(无)"].append(row)
        for t in d.get("tags", []) or ["(无结构标签)"]:
            by_tag[t].append(row)

    print("\n" + "=" * 64)
    print("       失败地图（structural_fidelity 是唯一可信尺子）")
    print("=" * 64)

    def dump(title, dd, sort_by_auto=True):
        print(f"\n── 按 {title} ──")
        items = list(dd.items())
        if sort_by_auto:  # 结构保真均值升序：最烂的切片排最前
            items.sort(key=lambda kv: _avg([a for a, _, _ in kv[1] if a is not None]))
        for k, rows in items:
            _fmt_slice(str(k), rows)

    dump("难度档 difficulty", by_diff)
    dump("结构难度标签 tag", by_tag)
    dump("房型 room_type", by_room)
    dump("来源分片 split", by_split)
    print()


def _avg(xs):
    return sum(xs) / len(xs) if xs else float("inf")


if __name__ == "__main__":
    enrich(write="--write" in sys.argv)
