"""评测结果存储"""

import json
import os
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

        # 原子写入：先写临时文件，再 rename
        tmp_path = self.path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.path)  # POSIX rename 是原子的
        except Exception:
            # 清理临时文件
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def load(self) -> Dict[str, Any]:
        with open(self.path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {
                    "version": "1.0",
                    "created_at": None,
                    "total_results": 0,
                    "metadata": {"corrupted": True, "source": self.path},
                    "results": [],
                }

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
