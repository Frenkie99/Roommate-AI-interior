"""评测数据模型定义"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


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
class Trace:
    """一次真实用户「上传毛坯 → 首次生图」的完整记录（v1，不含局部精修）。

    这是评测集最重要的数据来源：真实输入 + 用户亲选的指令 + 真实输出 + 反馈。
    由后端每次生成时写一条（追加到 JSONL）；评测平台经 to_image_pair() 转成评测样本。
    """
    trace_id: str
    created_at: str
    session_id: str = ""                       # 匿名会话id（无身份信息），串联同一人多次操作

    # —— 输入 ——
    input_image_path: str = ""                 # 毛坯原图（服务器已存）
    input_image_hash: str = ""                 # 去重用

    # —— 用户真实选择 = 评测的「指令」（评测集一直缺的，真实不靠猜）——
    style: str = ""
    room_type: str = ""
    custom_prompt: str = ""
    aspect_ratio: str = ""

    # —— 产品内部过程（诊断用）——
    enhanced_prompt: str = ""                  # 实际发给图像模型的完整 prompt
    model_used: str = ""
    vision_analysis_ok: Optional[bool] = None  # 视觉识别成功 / 静默降级到盲 DeepSeek（记录隐患频率）
    latency_ms: Optional[int] = None

    # —— 输出 ——
    output_image_paths: List[str] = field(default_factory=list)
    success: bool = True
    error: str = ""

    # —— 用户反馈（第4个问题再做，先占位）= bad case 金矿 ——
    feedback: Dict[str, Any] = field(default_factory=dict)   # {action: 留用/重生成/下载/弃用, rating: ...}
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Trace:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_image_pair(self, pair_id: str) -> "ImagePair":
        """转成评测样本：用户选择即指令；标记来源为 production，并把 trace 信息存入 metadata。"""
        return ImagePair(
            pair_id=pair_id,
            input_path=self.input_image_path,
            output_path=self.output_image_paths[0] if self.output_image_paths else "",
            prompt=self.custom_prompt,
            style=self.style,
            room_type=self.room_type,
            dataset_split="production",
            metadata={
                "source": "trace",
                "trace_id": self.trace_id,
                "session_id": self.session_id,
                "enhanced_prompt": self.enhanced_prompt,
                "model_used": self.model_used,
                "vision_analysis_ok": self.vision_analysis_ok,
                "feedback": self.feedback,
            },
        )


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
