"""评测执行器：编排 loader × scorers → eval_results.json"""

from typing import List, Optional

from evals.config import USE_MOCK
from evals.dataset.loader import DatasetLoader
from evals.dataset.schemas import EvalResult, DatasetMetadata, ImagePair
from evals.scorer.registry import ScorerRegistry
from evals.executor.result_store import ResultStore


class Runner:
    def __init__(self, loader: Optional[DatasetLoader] = None,
                 store: Optional[ResultStore] = None):
        self.loader = loader or DatasetLoader()
        self.store = store or ResultStore()

    def run(self, pairs: Optional[List[ImagePair]] = None,
            metric_names: Optional[List[str]] = None) -> List[EvalResult]:
        ScorerRegistry.initialize(use_mock=USE_MOCK)
        scorers = ScorerRegistry.get_all()

        if metric_names:
            scorers = {k: v for k, v in scorers.items() if k in metric_names}

        if pairs is None:
            pairs = self.loader.load()

        results = []
        total = len(pairs)
        for i, pair in enumerate(pairs, 1):
            scores = {}
            for name, scorer in scorers.items():
                s = scorer.score(
                    pair.input_path, pair.output_path, pair.prompt,
                    style=pair.style, room_type=pair.room_type,
                )
                scores[name] = s

            result = EvalResult(
                pair_id=pair.pair_id,
                scores=scores,
                metadata={"style": pair.style, "room_type": pair.room_type,
                          "tags": pair.tags, "split": pair.dataset_split},
            )
            results.append(result)
            print(f"  [{i}/{total}] {pair.pair_id}: {scores}")

        # 保存结果
        meta = self.loader.load()
        self.store.save(results, metadata={"total_pairs": len(meta)})
        print(f"\nDone. {len(results)} results saved to {self.store.path}")

        # 打印汇总
        self._print_summary(results)
        return results

    def _print_summary(self, results: List[EvalResult]) -> None:
        if not results:
            return
        metrics = list(results[0].scores.keys())
        print("\n--- Summary ---")
        for m in metrics:
            values = [r.scores[m] for r in results]
            avg = sum(values) / len(values)
            print(f"  Avg {m}: {avg:.4f} (min={min(values):.4f}, max={max(values):.4f})")


if __name__ == "__main__":
    runner = Runner()
    runner.run()
