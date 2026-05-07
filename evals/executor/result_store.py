"""评测结果存储"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from evals.config import EVAL_RESULTS_PATH
from evals.dataset.schemas import EvalResult


class ResultStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or str(EVAL_RESULTS_PATH)

    def save(self, results: List[EvalResult],
             metadata: Optional[Dict[str, Any]] = None) -> None:
        data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "total_results": len(results),
            "metadata": metadata or {},
            "results": [r.to_dict() for r in results],
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_results_list(self) -> List[EvalResult]:
        data = self.load()
        return [EvalResult.from_dict(r) for r in data.get("results", [])]

    def get_flat_dicts(self) -> List[Dict[str, Any]]:
        """展平为字典列表，方便 pandas 使用"""
        data = self.load()
        flat = []
        for r in data.get("results", []):
            row = {
                "pair_id": r["pair_id"],
                "notes": r.get("notes", ""),
            }
            row.update(r.get("scores", {}))
            row.update(r.get("metadata", {}))
            flat.append(row)
        return flat
