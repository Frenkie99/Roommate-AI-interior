"""评测数据模型定义"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class ImagePair:
    pair_id: str
    input_path: str
    output_path: str
    prompt: str = ""
    style: str = ""
    room_type: str = ""
    tags: List[str] = field(default_factory=list)
    dataset_split: str = "standard"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> ImagePair:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class EvalResult:
    pair_id: str
    scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> EvalResult:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class DatasetMetadata:
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    total_pairs: int = 0
    pairs: List[ImagePair] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "total_pairs": self.total_pairs,
            "pairs": [p.to_dict() for p in self.pairs],
        }

    @classmethod
    def from_dict(cls, d: dict) -> DatasetMetadata:
        pairs = [ImagePair.from_dict(p) for p in d.get("pairs", [])]
        return cls(
            version=d.get("version", "1.0"),
            created_at=d.get("created_at", ""),
            total_pairs=len(pairs),
            pairs=pairs,
        )

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> DatasetMetadata:
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
