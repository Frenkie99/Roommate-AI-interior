"""
把服务器攒下的真实用户 trace（traces.jsonl）导入本地评测数据集。

流程（trace 管道第 5 步）：
    server: backend/data/traces.jsonl   ——(你手动拉回本地任意路径)——>
    本脚本： 逐条 Trace.from_dict → to_image_pair() → 合并进 real_metadata.json
             （dataset_split="production"），评测面板即可看到真实用户样本。

设计要点：
- **幂等**：靠 trace_id 去重，重复跑不会产生重复样本（已导入的自动跳过）。
- **只导入成功生图**（success=True）且图片文件在本地真实存在的 trace；
  缺图的跳过并告警（避免生成打不开的坏样本）。bad case 反馈留给后续「用户点评」埋点。
- **pair_id 方案**：production 样本用 `prod_000/001/...`，编号在已有 prod 之后续接。
- 不覆盖任何已有非 production 样本；只做追加 + 更新计数。

用法：
    python -m evals.dataset.import_traces <traces.jsonl路径> [--images-root 项目根]
    # 默认 traces 路径 = backend/data/traces.jsonl；images-root = 项目根（trace 里存的是
    #   input/xxx、output/xxx 相对路径，需能在 images-root 下找到对应图片文件）
"""

import os
import sys
import json
import argparse
from typing import List, Tuple

# 允许以脚本或模块两种方式运行
_THIS = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from evals.dataset.schemas import Trace, DatasetMetadata, ImagePair  # noqa: E402
from evals.config import METADATA_PATH, PROJECT_ROOT  # noqa: E402

_DEFAULT_TRACES = os.path.join(str(PROJECT_ROOT), "backend", "data", "traces.jsonl")
_PROD_SPLIT = "production"


def _read_traces(path: str) -> List[Trace]:
    """读 JSONL，逐行解析成 Trace；跳过空行/坏行（告警不中断）。"""
    traces: List[Trace] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                traces.append(Trace.from_dict(json.loads(line)))
            except Exception as e:
                print(f"[WARN] 第{i}行解析失败,跳过: {e}")
    return traces


def _existing_trace_ids(pairs: List[ImagePair]) -> set:
    """已导入过的 trace_id 集合（用于幂等去重）。"""
    ids = set()
    for p in pairs:
        if p.dataset_split == _PROD_SPLIT:
            tid = (p.metadata or {}).get("trace_id")
            if tid:
                ids.add(tid)
    return ids


def _next_prod_index(pairs: List[ImagePair]) -> int:
    """已有 prod_NNN 的最大编号 + 1。"""
    mx = -1
    for p in pairs:
        if p.pair_id.startswith("prod_"):
            try:
                mx = max(mx, int(p.pair_id.split("_", 1)[1]))
            except (ValueError, IndexError):
                pass
    return mx + 1


def _images_exist(pair: ImagePair, images_root: str) -> bool:
    inp = os.path.join(images_root, pair.input_path)
    out = os.path.join(images_root, pair.output_path)
    return os.path.isfile(inp) and os.path.isfile(out)


def import_traces(
    traces_path: str = _DEFAULT_TRACES,
    metadata_path: str = None,
    images_root: str = None,
    require_images: bool = True,
) -> Tuple[int, int, int]:
    """返回 (新增, 跳过_已存在, 跳过_缺图或失败)。"""
    metadata_path = metadata_path or str(METADATA_PATH)
    images_root = images_root or str(PROJECT_ROOT)

    if not os.path.isfile(traces_path):
        print(f"[ERROR] 找不到 traces 文件: {traces_path}")
        return (0, 0, 0)

    traces = _read_traces(traces_path)
    meta = DatasetMetadata.load(metadata_path)
    seen = _existing_trace_ids(meta.pairs)
    idx = _next_prod_index(meta.pairs)

    added = skip_existing = skip_bad = 0
    for t in traces:
        if not t.trace_id or t.trace_id in seen:
            skip_existing += 1
            continue
        if not t.success or not t.output_image_paths:
            skip_bad += 1
            continue
        pair = t.to_image_pair(f"prod_{idx:03d}")
        if require_images and not _images_exist(pair, images_root):
            print(f"[WARN] trace {t.trace_id[:8]} 缺图片(input/output),跳过")
            skip_bad += 1
            continue
        meta.pairs.append(pair)
        seen.add(t.trace_id)
        idx += 1
        added += 1

    if added:
        meta.total_pairs = len(meta.pairs)
        meta.save(metadata_path)

    print(f"[导入完成] 新增 {added} · 已存在跳过 {skip_existing} · 缺图/失败跳过 {skip_bad}"
          f" · 数据集现共 {len(meta.pairs)} 条")
    return (added, skip_existing, skip_bad)


def main():
    ap = argparse.ArgumentParser(description="导入真实用户 trace 到评测数据集")
    ap.add_argument("traces", nargs="?", default=_DEFAULT_TRACES,
                    help=f"traces.jsonl 路径(默认 {_DEFAULT_TRACES})")
    ap.add_argument("--metadata", default=None, help="目标 real_metadata.json(默认 config.METADATA_PATH)")
    ap.add_argument("--images-root", default=None, help="图片相对路径的根目录(默认项目根)")
    ap.add_argument("--no-require-images", action="store_true",
                    help="不校验图片文件是否存在(仅测试转换逻辑时用)")
    args = ap.parse_args()
    import_traces(
        traces_path=args.traces,
        metadata_path=args.metadata,
        images_root=args.images_root,
        require_images=not args.no_require_images,
    )


if __name__ == "__main__":
    main()
