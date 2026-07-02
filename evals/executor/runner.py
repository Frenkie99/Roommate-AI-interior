"""评测执行器 Runner（Eval Harness 五大要素的执行核心）

对齐课程「Eval Harness」框架，一条命令把评测跑起来：
  ① Loader 筛选      —— --split/--room-type/--difficulty/--intrinsic-difficulty/--tags 选 case 子集
  ② Runner 批量      —— 失败隔离（单个评分器/单张图报错不拖垮整轮）、可续跑（--resume）
  ③ 环境隔离/可复现  —— 每轮把「筛选条件/指标/mock/耗时/计数」存成 run 快照写进结果文件
  ⑤ Aggregator      —— 跑完自动产出分维度聚合报告（eval_report.md / .json）
（④ Trace 日志、生成式重跑 押后，见 PROGRESS.md）

用法示例：
  python -m evals.executor.runner                       # 全量跑（合并写盘，不丢已有维度）
  python -m evals.executor.runner --split standard      # 只跑 standard 分片
  python -m evals.executor.runner --intrinsic-difficulty extreme  # 只跑极难 case
  python -m evals.executor.runner --resume              # 续跑：跳过已算完的
  python -m evals.executor.runner --dry-run             # 只列命中哪些 case，不打分
  python -m evals.executor.runner --report-only         # 不打分，仅从现有结果重出聚合报告
"""

import argparse
import time
from datetime import datetime
from typing import List, Optional

from evals.config import USE_MOCK
from evals.dataset.loader import DatasetLoader
from evals.dataset.schemas import EvalResult, ImagePair
from evals.scorer.registry import ScorerRegistry
from evals.executor.result_store import ResultStore
from evals.executor import aggregator


class Runner:
    def __init__(self, loader: Optional[DatasetLoader] = None,
                 store: Optional[ResultStore] = None):
        self.loader = loader or DatasetLoader()
        self.store = store or ResultStore()

    # —— ① 筛选：选出要跑的 case 子集 ——
    def select_pairs(self, split=None, room_type=None, tags=None,
                     difficulty=None, intrinsic_difficulty=None) -> List[ImagePair]:
        pairs = self.loader.filter(tags=tags, room_type=room_type, split=split)
        # difficulty/intrinsic_difficulty 是富化维度（不在 ImagePair 字段里，从已有结果读），
        # 这里按已存结果的 metadata 过滤，保证「按难度选 case」也能用。
        if difficulty or intrinsic_difficulty:
            existing = {r["pair_id"]: r.get("metadata", {})
                        for r in self.store.load().get("results", [])}
            dim = "difficulty" if difficulty else "intrinsic_difficulty"
            # 反静默：没评过分/无该维度标注的 case（如新导入的 production 数据）无法按难度
            # 过滤，会被排除——必须显式告警，绝不无声吞掉。
            unlabeled = [p.pair_id for p in pairs if not existing.get(p.pair_id, {}).get(dim)]
            if unlabeled:
                shown = ", ".join(unlabeled[:5]) + ("…" if len(unlabeled) > 5 else "")
                print(f"  ⚠️ {len(unlabeled)} 条 case 缺 {dim} 标注，无法按难度筛选、已被排除：{shown}\n"
                      f"     （新导入的数据需先跑一轮全量评分/富化才能进难度切片）")
            if difficulty:
                pairs = [p for p in pairs if existing.get(p.pair_id, {}).get("difficulty") == difficulty]
            if intrinsic_difficulty:
                pairs = [p for p in pairs
                         if existing.get(p.pair_id, {}).get("intrinsic_difficulty") == intrinsic_difficulty]
        return pairs

    def _base_metadata(self, pair: ImagePair) -> dict:
        """只写 runner 能可靠从输入属性得出的维度。
        difficulty/intrinsic_difficulty 由独立富化脚本注入 eval_results，
        合并写盘时予以保留（见 run() 的 merge 逻辑），重跑不丢。
        """
        return {"style": pair.style, "room_type": pair.room_type,
                "tags": pair.tags, "split": pair.dataset_split}

    # —— ②③⑤ 主流程 ——
    def run(self, *, split=None, room_type=None, tags=None, difficulty=None,
            intrinsic_difficulty=None, metric_names=None, use_mock=USE_MOCK,
            resume=False, merge=True, dry_run=False) -> List[EvalResult]:
        started = time.time()

        ScorerRegistry.initialize(use_mock=use_mock)
        scorers = ScorerRegistry.get_all()
        if metric_names:
            scorers = {k: v for k, v in scorers.items() if k in metric_names}
        active_metrics = list(scorers.keys())
        if not active_metrics:
            raise SystemExit(f"没有可用评分器（请求={metric_names}，"
                             f"已注册={list(ScorerRegistry.get_all())}）")

        pairs = self.select_pairs(split=split, room_type=room_type, tags=tags,
                                  difficulty=difficulty, intrinsic_difficulty=intrinsic_difficulty)

        existing_doc = self.store.load()
        existing = {r["pair_id"]: r for r in existing_doc.get("results", [])}

        if resume:
            def done(pid):
                r = existing.get(pid)
                return bool(r) and all(r.get("scores", {}).get(m) is not None for m in active_metrics)
            before = len(pairs)
            pairs = [p for p in pairs if not done(p.pair_id)]
            print(f"续跑：跳过 {before - len(pairs)} 条已完成，待跑 {len(pairs)} 条")

        tag_note = f"/tags={tags}" if tags else ""
        print(f"筛选后 {len(pairs)} 对 × 指标 {active_metrics}"
              f"{'（mock）' if use_mock else ''}{tag_note}")

        if dry_run:
            for p in pairs:
                print(f"  - {p.pair_id} [{p.dataset_split}/{p.room_type or '?'}]")
            print(f"\n[dry-run] 不打分、不写盘。命中 {len(pairs)} 对。")
            return []

        # —— ② 批量打分（失败隔离）——
        errors = 0
        fresh: List[EvalResult] = []
        total = len(pairs)
        for i, pair in enumerate(pairs, 1):
            scores = {}
            for name, scorer in scorers.items():
                try:
                    scores[name] = scorer.score(
                        pair.input_path, pair.output_path, pair.prompt,
                        style=pair.style, room_type=pair.room_type,
                    )
                except Exception as e:  # 单点报错记 None 继续，绝不拖垮整轮
                    scores[name] = None
                    errors += 1
                    print(f"  ⚠️ {pair.pair_id} 评分器 {name} 报错，记 None 继续：{e}")
            fresh.append(EvalResult(pair_id=pair.pair_id, scores=scores,
                                    metadata=self._base_metadata(pair)))
            print(f"  [{i}/{total}] {pair.pair_id}: {scores}")

        # —— 合并写盘（非破坏性）：保留既有富化维度，只更新分数 + 基础属性 ——
        if merge:
            merged = {pid: dict(r) for pid, r in existing.items()}
            for r in fresh:
                rd = r.to_dict()
                if r.pair_id in merged:
                    merged[r.pair_id].setdefault("scores", {}).update(rd["scores"])
                    old_meta = merged[r.pair_id].get("metadata", {})
                    merged[r.pair_id]["metadata"] = {**old_meta, **rd["metadata"]}
                else:
                    merged[r.pair_id] = rd
            out_results = [EvalResult.from_dict(v) for v in merged.values()]
        else:
            out_results = fresh

        # —— ③ run 快照：保留原顶层 metadata（retired_metrics 等）再叠加本轮信息 ——
        top_meta = dict(existing_doc.get("metadata", {}))
        top_meta["total_pairs"] = len(out_results)
        top_meta["last_run"] = {
            "at": datetime.now().isoformat(),
            "filters": {"split": split, "room_type": room_type, "tags": tags,
                        "difficulty": difficulty, "intrinsic_difficulty": intrinsic_difficulty},
            "metrics": active_metrics,
            "use_mock": use_mock,
            "resume": resume,
            "merge": merge,
            "n_scored": len(fresh),
            "n_errors": errors,
            "duration_sec": round(time.time() - started, 2),
        }
        self.store.save(out_results, metadata=top_meta)
        print(f"\n完成：本次新算 {len(fresh)} 条，写盘共 {len(out_results)} 条 → {self.store.path}"
              + (f"；{errors} 个评分错误（已记 None）" if errors else ""))

        # —— ⑤ 聚合报告 ——
        report_path = self._emit_report(out_results, active_metrics, top_meta["last_run"])
        print(f"聚合报告 → {report_path}")
        return out_results

    def report_only(self, metric_names: Optional[List[str]] = None) -> str:
        """不打分，仅从现有结果重出聚合报告（免费、随时可跑）。"""
        doc = self.store.load()
        results = [EvalResult.from_dict(r) for r in doc.get("results", [])]
        report_path = self._emit_report(results, metric_names, doc.get("metadata", {}).get("last_run"))
        print(f"聚合报告 → {report_path}")
        return report_path

    def _emit_report(self, results, metrics, run_config) -> str:
        report = aggregator.aggregate(results, metrics=metrics)
        md = aggregator.to_markdown(report, run_config=run_config)
        path = aggregator.save_report(md, report)
        print("\n" + md)
        return path


def _parse_args():
    p = argparse.ArgumentParser(description="Eval Harness Runner —— 一键跑评测 + 分维度报告")
    p.add_argument("--split", help="按分片筛：standard/competitor/corner_case/production")
    p.add_argument("--room-type", dest="room_type", help="按房型筛")
    p.add_argument("--difficulty", choices=["easy", "medium", "hard"], help="按结果难度筛")
    p.add_argument("--intrinsic-difficulty", dest="intrinsic_difficulty",
                   choices=["easy", "medium", "hard", "extreme"], help="按内在难度筛")
    p.add_argument("--tags", help="按结构标签筛，逗号分隔（命中任一即选）")
    p.add_argument("--metrics", help="只跑指定指标，逗号分隔；默认全部已注册")
    p.add_argument("--mock", action="store_true", help="用 mock 评分器（不碰真实图片/模型）")
    p.add_argument("--resume", action="store_true", help="续跑：跳过所有请求指标都已算完的 case")
    p.add_argument("--no-merge", dest="no_merge", action="store_true",
                   help="不合并，直接用本次结果覆盖全文件（会丢未跑 case 与富化维度，慎用）")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", help="只列命中哪些 case，不打分")
    p.add_argument("--report-only", dest="report_only", action="store_true",
                   help="不打分，仅从现有结果重出聚合报告")
    return p.parse_args()


if __name__ == "__main__":
    a = _parse_args()
    tags = [t.strip() for t in a.tags.split(",")] if a.tags else None
    metrics = [m.strip() for m in a.metrics.split(",")] if a.metrics else None
    runner = Runner()
    if a.report_only:
        runner.report_only(metric_names=metrics)
    else:
        runner.run(split=a.split, room_type=a.room_type, tags=tags,
                   difficulty=a.difficulty, intrinsic_difficulty=a.intrinsic_difficulty,
                   metric_names=metrics, use_mock=a.mock or USE_MOCK,
                   resume=a.resume, merge=not a.no_merge, dry_run=a.dry_run)
