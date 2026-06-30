"""把「看图判定的内在难度」写回评测集元数据（幂等）。

背景（2026-06-30）：原难度是从文件名关键词推的，不可信——审计发现 45 张 standard 被一律默认成「易」，
看图后实为 易12/中13/难16/极难4。本脚本把「看图标签」(evals/data/intrinsic_difficulty_labels.json)
应用到两处：
  - real_metadata.json（源头）：每对加 `intrinsic_difficulty`（easy/medium/hard/extreme），
    并按看图补/纠 room_type（补空缺、解冲突，原值保留进 metadata.room_type_original 不丢）。
  - eval_results.json（看板数据）：每条 metadata 加 `intrinsic_difficulty`，同步 room_type；
    **绝不动已有的 `difficulty` 字段**——那是「结果难度」(从人工分反推)，与内在难度是两个独立的轴。

幂等：以 labels 文件为准，重跑得同一结果；room_type_original 只在首次冲突时写入，不重复覆盖。
用法：python -m evals.dataset.apply_intrinsic_difficulty  [--dry-run]
"""

import argparse
import json
from pathlib import Path

from evals.config import EVALS_DIR

LABELS_PATH = EVALS_DIR / "data" / "intrinsic_difficulty_labels.json"
REAL_META_PATH = EVALS_DIR / "data" / "real_metadata.json"
EVAL_RESULTS_PATH = EVALS_DIR / "data" / "eval_results.json"

VALID_DIFF = {"easy", "medium", "hard", "extreme"}


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _dump(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _filename_of(pair):
    """取一对图的源文件名：优先 metadata.source_filename，回退 input_path 末段。"""
    md = pair.get("metadata") or {}
    return md.get("source_filename") or Path(pair.get("input_path", "")).name


def apply(dry_run=False):
    labels = _load(LABELS_PATH)["labels"]
    stats = {"diff_set": 0, "rt_add": 0, "rt_conflict": 0, "rt_confirm": 0, "unmatched": 0}

    # ---- real_metadata.json ----
    rm = _load(REAL_META_PATH)
    fn2pid = {}
    for pair in rm["pairs"]:
        fn = _filename_of(pair)
        fn2pid[fn] = pair["pair_id"]
        lab = labels.get(fn)
        if not lab:
            stats["unmatched"] += 1
            continue
        diff = lab["intrinsic_difficulty"]
        assert diff in VALID_DIFF, f"非法难度 {diff} @ {fn}"
        if pair.get("intrinsic_difficulty") != diff:
            stats["diff_set"] += 1
        pair["intrinsic_difficulty"] = diff

        seen = lab.get("room_type_seen") or ""
        cur = pair.get("room_type") or ""
        if seen:
            if not cur:
                pair["room_type"] = seen
                stats["rt_add"] += 1
            elif cur != seen:
                # 冲突：采看图值，原值保留（仅首次）
                md = pair.setdefault("metadata", {})
                md.setdefault("room_type_original", cur)
                if pair.get("room_type") != seen:
                    pair["room_type"] = seen
                    stats["rt_conflict"] += 1
            else:
                stats["rt_confirm"] += 1

    # ---- eval_results.json ----
    er = _load(EVAL_RESULTS_PATH)
    pid2lab = {fn2pid[fn]: lab for fn, lab in labels.items() if fn in fn2pid}
    pid2rt = {p["pair_id"]: (p.get("room_type") or "") for p in rm["pairs"]}
    for res in er["results"]:
        lab = pid2lab.get(res["pair_id"])
        if not lab:
            continue
        meta = res.setdefault("metadata", {})
        meta["intrinsic_difficulty"] = lab["intrinsic_difficulty"]
        # room_type 与 real_metadata 对齐（保持单一真相）；不动 meta['difficulty']（结果难度）
        meta["room_type"] = pid2rt.get(res["pair_id"], meta.get("room_type", ""))

    print("== 应用统计 ==")
    print(f"  内在难度写入: {stats['diff_set']} 条（剩余为已是目标值，幂等）")
    print(f"  room_type 补空: {stats['rt_add']} · 解冲突: {stats['rt_conflict']} · 确认一致: {stats['rt_confirm']} · 未匹配标签: {stats['unmatched']}")

    if dry_run:
        print("  [dry-run] 未写盘。")
        return
    _dump(REAL_META_PATH, rm)
    _dump(EVAL_RESULTS_PATH, er)
    print(f"  已写回: {REAL_META_PATH.name} + {EVAL_RESULTS_PATH.name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    apply(**vars(ap.parse_args()))
