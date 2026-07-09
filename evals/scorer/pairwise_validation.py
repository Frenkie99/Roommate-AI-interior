"""美学成对 Judge 的校准验证 — 刀4（花钱，走 GRADER_APIYI_KEY）

协议（对齐课程"Judge 当分类器验证" + RESEARCH_IMAGE_EVAL 结论"美学上成对>点评"）：
  1. 从 judge_split 指定划分取 case（默认 dev；test 只在最终验收用且必须 --record-ledger 记台账）。
  2. 构造"人工美学差距明确"的对（低分组 aesthetic≤2 × 高分组 aesthetic≥4，Δ≥2）——
     验证目标是"清晰差异上 judge 是否与人一致"；模糊差异连人-人一致性都只有 ~0.45，不作为验收依据。
  3. 每对调 compare_pairwise（纯美学、无毛坯参考、正反双序消位置偏见）。
  4. 指标：一致率 = judge 选对更美者 / 总对数（tie 计为不一致，单列报告）+ Wilson 95% 区间。
     验收门槛：一致率 ≥ 75%（人-人美学一致上限 ~0.45，不照搬课程 90%——见 PROGRESS 2026-07-09）。

结果落盘 data/pairwise_validation.json（追加式，按 run 记录），供可信度面板与复盘。

用法：
    python -m evals.scorer.pairwise_validation --split dev --n 20            # dev 迭代
    python -m evals.scorer.pairwise_validation --split dev --n 20 --dry-run  # 只看抽了哪些对，不花钱
    python -m evals.scorer.pairwise_validation --split test --n 15 --record-ledger --judge-version v2.1
                                                                             # test 最终验收（一版一次）
"""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

from evals.config import DATA_DIR, GOLD_LABELS_PATH, METADATA_PATH

RESULT_PATH = DATA_DIR / "pairwise_validation.json"
_SEED = 20260709
_LOW_MAX = 2.0    # 低分组：人工 aesthetic ≤ 2
_HIGH_MIN = 4.0   # 高分组：人工 aesthetic ≥ 4


def _load_universe(split: str):
    """取指定划分下、未被校准剔除、美学分齐全且图可读的 case 列表。"""
    from evals.dataset.judge_split import pair_ids
    from evals.scorer.gold_store import GoldStore, is_excluded

    gold = GoldStore().load()
    pairs = {p["pair_id"]: p for p in
             json.loads(Path(METADATA_PATH).read_text(encoding="utf-8"))["pairs"]}
    out = []
    for pid in pair_ids(split):
        e = gold.get(pid)
        p = pairs.get(pid)
        if not e or not p or is_excluded(e):
            continue
        aes = e.get("scores", {}).get("aesthetic")
        if aes is None or not p.get("output_path"):
            continue
        out.append({"pair_id": pid, "aesthetic": aes, "pair": p})
    return out


def build_comparisons(split: str, n: int, seed: int = _SEED):
    """低×高分组配对（Δ美学≥2），确定性抽样；每个 case 最多出现 2 次以摊薄个体影响。"""
    universe = _load_universe(split)
    lows = sorted((u for u in universe if u["aesthetic"] <= _LOW_MAX),
                  key=lambda u: u["pair_id"])
    highs = sorted((u for u in universe if u["aesthetic"] >= _HIGH_MIN),
                   key=lambda u: u["pair_id"])
    if not lows or not highs:
        raise RuntimeError(f"{split} 集低分组({len(lows)})/高分组({len(highs)})不足，无法配对")

    rng = random.Random(seed)
    # 允许每个 case 最多用 2 轮：低高各自洗牌后 zip，两轮不同排列
    combos, used = [], set()
    for _round in range(2):
        ls, hs = lows[:], highs[:]
        rng.shuffle(ls)
        rng.shuffle(hs)
        for lo, hi in zip(ls, hs):
            key = (lo["pair_id"], hi["pair_id"])
            if key in used:
                continue
            used.add(key)
            combos.append((lo, hi))
    rng.shuffle(combos)
    return combos[:n], len(lows), len(highs)


def run(split: str, n: int, seed: int, model: str, dry_run: bool = False):
    from evals.scorer.vision_judge import compare_pairwise, _DEFAULT_MODEL

    model = model or _DEFAULT_MODEL
    combos, n_low, n_high = build_comparisons(split, n, seed)
    print(f"划分={split}  低分组(aes≤{_LOW_MAX:g}) {n_low} 条 × 高分组(aes≥{_HIGH_MIN:g}) {n_high} 条"
          f" → 抽 {len(combos)} 对（seed={seed}）")

    if dry_run:
        for lo, hi in combos:
            print(f"  {lo['pair_id']}(aes={lo['aesthetic']:g}) vs {hi['pair_id']}(aes={hi['aesthetic']:g})")
        print("（dry-run，未调用 API）")
        return None

    rows, correct, wrong, ties, errors = [], 0, 0, 0, 0
    tot_in = tot_out = 0
    for i, (lo, hi) in enumerate(combos, 1):
        # 随机化位置：一半 A=低分方，一半 A=高分方（双序机制之外再消系统位置偏差）
        swap = (i % 2 == 0)
        a, b = (hi, lo) if swap else (lo, hi)
        expect = "a" if swap else "b"   # 期望 judge 选人工美学更高的一方
        try:
            r = compare_pairwise(None, a["pair"]["output_path"], b["pair"]["output_path"],
                                 style="", room_type="", model=model)
        except Exception as e:
            errors += 1
            print(f"  ✗ [{i}/{len(combos)}] {a['pair_id']} vs {b['pair_id']} 调用失败: "
                  f"{type(e).__name__}: {str(e)[:120]}")
            continue
        got = r["winner"]
        verdict = "correct" if got == expect else ("tie" if got == "tie" else "wrong")
        correct += (verdict == "correct")
        wrong += (verdict == "wrong")
        ties += (verdict == "tie")
        ui, uo = r["_usage"].get("prompt_tokens", 0), r["_usage"].get("completion_tokens", 0)
        tot_in += ui
        tot_out += uo
        rows.append({
            "a": a["pair_id"], "b": b["pair_id"],
            "a_aes": a["aesthetic"], "b_aes": b["aesthetic"],
            "expect": expect, "got": got, "verdict": verdict,
            "consistent": r["consistent"], "reasons": r["reasons"],
        })
        print(f"  [{i}/{len(combos)}] {a['pair_id']}(aes{a['aesthetic']:g}) vs "
              f"{b['pair_id']}(aes{b['aesthetic']:g}) → judge={got} 期望={expect} "
              f"{'✓' if verdict == 'correct' else '✗' if verdict == 'wrong' else '– tie'}")

    n_done = correct + wrong + ties
    if not n_done:
        print("没有成功的比较，无法计算一致率。")
        return None

    from evals.scorer.credibility import wilson_interval
    agree = correct / n_done
    ci = wilson_interval(correct, n_done)
    consistent_rate = sum(1 for r in rows if r["consistent"]) / len(rows)

    summary = {
        "run_at": datetime.now().isoformat(),
        "split": split, "seed": seed, "model": model,
        "n_pairs": n_done, "n_errors": errors,
        "correct": correct, "wrong": wrong, "ties": ties,
        "agreement": round(agree, 4),
        "agreement_ci": [round(ci[0], 4), round(ci[1], 4)],
        "order_consistency": round(consistent_rate, 4),
        "tokens": {"in": tot_in, "out": tot_out},
        "rows": rows,
    }

    print("\n" + "=" * 60)
    print(f"一致率: {agree*100:.1f}%  [Wilson 95%: {ci[0]*100:.0f}% ~ {ci[1]*100:.0f}%]"
          f"  （对 {correct} / 错 {wrong} / 平 {ties}，tie 计不一致）")
    print(f"双序一致率: {consistent_rate*100:.1f}%（判断稳定性）")
    print(f"token 用量: in {tot_in} / out {tot_out}"
          f"（约 {tot_in/max(1,n_done):.0f} in + {tot_out/max(1,n_done):.0f} out /对）")
    verdict_txt = "🟢 过门槛(≥75%)" if agree >= 0.75 else "🔴 未过门槛(<75%)"
    print(f"验收判定: {verdict_txt}")
    print("=" * 60)

    _append_result(summary)
    return summary


def _append_result(summary: dict) -> None:
    data = {"runs": []}
    if RESULT_PATH.exists():
        try:
            data = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    data.setdefault("runs", []).append(summary)
    tmp = str(RESULT_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    import os
    os.replace(tmp, RESULT_PATH)
    print(f"结果已落盘: {RESULT_PATH}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=_SEED)
    ap.add_argument("--model", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--record-ledger", action="store_true",
                    help="test 验收必带：消费记入 judge_split 台账")
    ap.add_argument("--judge-version", default="", help="配合 --record-ledger")
    args = ap.parse_args()

    if args.split == "test" and not args.dry_run:
        if not args.record_ledger or not args.judge_version:
            print("🔒 test 集只用于最终验收：必须带 --record-ledger 和 --judge-version（一版一次纪律）")
            sys.exit(2)

    summary = run(args.split, args.n, args.seed, args.model, dry_run=args.dry_run)

    if summary and args.split == "test" and args.record_ledger:
        from evals.dataset.judge_split import record_test_consumption
        record_test_consumption(
            "vision_judge.pairwise_aesthetic", args.judge_version,
            note=f"一致率 {summary['agreement']*100:.1f}% "
                 f"[{summary['agreement_ci'][0]*100:.0f}~{summary['agreement_ci'][1]*100:.0f}%] "
                 f"(对{summary['correct']}/错{summary['wrong']}/平{summary['ties']})")
        print("📒 已记入 test 消费台账")


if __name__ == "__main__":
    main()
