"""85 条金标准的 Judge 数据集划分 — few-shot 池 / dev / test

课程框架（张和老师·grader 模块）：Judge 本身也要设三种数据集——
  - fewshot（≈课程的 training）：只当 judge prompt 里的示例，永不参与对齐度/TPR-TNR 计算（防泄漏）
  - dev    ：迭代与调试 judge prompt 用，随便看随便调
  - test   ：每个 judge 版本只碰一次，报最终 TPR/TNR；消费记录写 test_ledger 强制纪律

适用范围：本划分只约束**还在迭代的 judge**（vision_judge）。structural_fidelity 已定型
（消融止于 2026-06-21，此后无调参），其相关性继续用全 85 条报，不受此约束。

划分方法：确定性分层抽样（固定 seed）——按（二元判定类别 × 是否有房型标注）分层，
保证 dev/test 都覆盖 好/坏/模糊 与 有房型/无房型（VQA 房型题只在有房型时生效，test 必须含有房型样本）。

用法：
    python -m evals.dataset.judge_split              # 生成划分（已存在则拒绝，防 test 纯度破坏）
    python -m evals.dataset.judge_split --show       # 查看现有划分
    python -m evals.dataset.judge_split --force      # 强制重新生成（会作废 test 纯度，慎用）
"""

import argparse
import json
import os
import random
from datetime import datetime
from typing import Dict, List, Optional

from evals.config import JUDGE_SPLIT_PATH, METADATA_PATH

_SEED = 20260709
_N_FEWSHOT_PASS = 3
_N_FEWSHOT_FAIL = 3
_TEST_FRACTION = 1 / 3  # 剩余样本按 dev:test ≈ 2:1


# ----------------------------- 读接口 -----------------------------

def load(path: Optional[str] = None) -> dict:
    """读取划分文件；不存在返回空 dict。"""
    p = str(path or JUDGE_SPLIT_PATH)
    if not os.path.exists(p):
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def assignment(path: Optional[str] = None) -> Dict[str, str]:
    """{pair_id: "fewshot"/"dev"/"test"}；划分文件不存在返回空 dict。"""
    return load(path).get("assignment", {})


def pair_ids(split: str, path: Optional[str] = None) -> List[str]:
    """某一划分下的 pair_id 列表（排序稳定）。"""
    return sorted(pid for pid, s in assignment(path).items() if s == split)


def record_test_consumption(judge_name: str, version: str, note: str = "",
                            path: Optional[str] = None) -> None:
    """test 集消费台账：每次用 test 集验收一个 judge 版本，必须记一笔。

    纪律：同一 judge 版本只允许消费 test 一次；台账是审计依据。
    """
    p = str(path or JUDGE_SPLIT_PATH)
    data = load(p)
    if not data:
        raise FileNotFoundError(f"划分文件不存在: {p}，请先生成划分")
    ledger = data.setdefault("test_ledger", [])
    ledger.append({
        "judge": judge_name,
        "version": version,
        "note": note,
        "consumed_at": datetime.now().isoformat(),
    })
    _atomic_save(data, p)


# ----------------------------- 生成划分 -----------------------------

def _load_gold_and_meta():
    from evals.scorer.gold_store import GoldStore, effective_binary

    gold = GoldStore().load()
    pairs = json.loads(open(METADATA_PATH, encoding="utf-8").read())["pairs"]
    room_of = {p["pair_id"]: (p.get("room_type") or "") for p in pairs}
    rows = []
    for pid, entry in sorted(gold.items()):
        verdict, _src = effective_binary(entry)
        rows.append({
            "pair_id": pid,
            "binary": verdict or "fuzzy",
            "overall": entry.get("scores", {}).get("overall"),
            "has_room": bool(room_of.get(pid)),
            "has_notes": bool((entry.get("notes") or "").strip()
                              or (entry.get("critique") or "").strip()),
        })
    return rows


def _pick_fewshot(rows: List[dict]) -> List[dict]:
    """确定性挑 few-shot 池：3 pass + 3 fail，跨分档、优先有备注/房型（能当 critique 示例）。

    pass 侧取 overall∈{5,4} 交替、fail 侧取 overall∈{1,2} 交替 → 覆盖"典型好/边缘好/典型烂/边缘烂"。
    """
    def _bucketed(binary: str, buckets: List[float], n: int) -> List[dict]:
        pools = {
            b: sorted(
                (r for r in rows if r["binary"] == binary and r["overall"] == b),
                key=lambda r: (-r["has_notes"], -r["has_room"], r["pair_id"]),
            )
            for b in buckets
        }
        picked, i = [], 0
        while len(picked) < n and any(pools.values()):
            b = buckets[i % len(buckets)]
            if pools[b]:
                picked.append(pools[b].pop(0))
            i += 1
            if i > 100:  # 兜底防死循环
                break
        return picked

    return _bucketed("pass", [5.0, 4.0], _N_FEWSHOT_PASS) + \
        _bucketed("fail", [1.0, 2.0], _N_FEWSHOT_FAIL)


def generate(seed: int = _SEED, force: bool = False,
             path: Optional[str] = None) -> dict:
    """生成并落盘划分。已存在且非 force 时拒绝——重划会作废 test 集纯度。"""
    p = str(path or JUDGE_SPLIT_PATH)
    if os.path.exists(p) and not force:
        raise FileExistsError(
            f"划分已存在: {p}。重新划分会作废 test 集纯度（dev 上调过的 prompt 会泄漏进新 test）。"
            f"确要重划请加 --force。")

    rows = _load_gold_and_meta()
    fewshot = _pick_fewshot(rows)
    fewshot_ids = {r["pair_id"] for r in fewshot}
    remaining = [r for r in rows if r["pair_id"] not in fewshot_ids]

    # 分层：二元类别 × 是否有房型
    strata: Dict[tuple, List[dict]] = {}
    for r in remaining:
        strata.setdefault((r["binary"], r["has_room"]), []).append(r)

    rng = random.Random(seed)
    assign: Dict[str, str] = {r["pair_id"]: "fewshot" for r in fewshot}
    for key in sorted(strata, key=str):
        group = sorted(strata[key], key=lambda r: r["pair_id"])
        rng.shuffle(group)
        n_test = round(len(group) * _TEST_FRACTION)
        if len(group) >= 2 and n_test == 0:
            n_test = 1  # 每个层至少给 test 1 条（层内≥2 时）
        for i, r in enumerate(group):
            assign[r["pair_id"]] = "test" if i < n_test else "dev"

    counts = {"fewshot": 0, "dev": 0, "test": 0}
    for s in assign.values():
        counts[s] += 1

    data = {
        "version": "1.0",
        "seed": seed,
        "created_at": datetime.now().isoformat(),
        "rule": ("fewshot=3pass+3fail(跨分档,优先有备注/房型); "
                 "余下按(二元类别×有无房型)分层, seed 洗牌, dev:test≈2:1; "
                 "test 每个 judge 版本只碰一次(见 test_ledger)"),
        "counts": counts,
        "fewshot_detail": [
            {"pair_id": r["pair_id"], "binary": r["binary"], "overall": r["overall"],
             "has_room": r["has_room"], "has_notes": r["has_notes"]}
            for r in fewshot
        ],
        "assignment": assign,
        "test_ledger": [],
    }
    _atomic_save(data, p)
    return data


def _atomic_save(data: dict, path: str) -> None:
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


# ----------------------------- CLI -----------------------------

def _show(data: dict) -> None:
    if not data:
        print("划分文件不存在。运行 python -m evals.dataset.judge_split 生成。")
        return
    c = data["counts"]
    print(f"seed={data['seed']}  created_at={data['created_at']}")
    print(f"counts: fewshot={c['fewshot']}  dev={c['dev']}  test={c['test']}")
    print("\nfew-shot 池：")
    for r in data.get("fewshot_detail", []):
        print(f"  {r['pair_id']}  binary={r['binary']}  overall={r['overall']}"
              f"  房型={'有' if r['has_room'] else '无'}  备注={'有' if r['has_notes'] else '无'}")
    ledger = data.get("test_ledger", [])
    print(f"\ntest 消费台账（{len(ledger)} 笔）：")
    for e in ledger:
        print(f"  {e['consumed_at']}  {e['judge']} v{e['version']}  {e.get('note','')}")
    # 分布交叉表
    from collections import Counter
    cross = Counter()
    for pid, s in data["assignment"].items():
        cross[s] += 1
    print(f"\nassignment 总数: {sum(cross.values())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="查看现有划分")
    ap.add_argument("--force", action="store_true", help="强制重新生成（作废 test 纯度，慎用）")
    ap.add_argument("--seed", type=int, default=_SEED)
    args = ap.parse_args()

    if args.show:
        _show(load())
    else:
        data = generate(seed=args.seed, force=args.force)
        print("✅ 划分已生成：")
        _show(data)
