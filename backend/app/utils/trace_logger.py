"""
真实用户 trace 埋点（评测集头号数据来源）。

设计原则：
- 字段与 evals/dataset/schemas.py 的 `Trace` 对齐，但后端**不 import evals**，保持独立解耦。
- 只追加、不读回；单条写失败**绝不能拖垮生图** → 全程 try/except 吞异常。
- 路径可配置：环境变量 `TRACE_LOG_PATH`，默认 `backend/data/traces.jsonl`
  （未跟踪文件，部署脚本的 git checkout/pull 不会冲掉）。

v1 范围：只记「真实用户上传毛坯 → 首次生图**成功**」的完整记录（不含局部精修）。
失败/弃用的 bad case 留给第 4 步「用户反馈采集」去捕获，更准。
"""

import os
import json
import uuid
import hashlib
from datetime import datetime

# backend/app/utils/trace_logger.py → 上溯三级到 backend/
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_DEFAULT_TRACE_PATH = os.path.join(_BACKEND_DIR, "data", "traces.jsonl")

# 与 Trace 数据结构对齐的字段白名单（多余键丢弃，缺失键不报错）
_TRACE_FIELDS = (
    "trace_id", "created_at", "session_id",
    "input_image_path", "input_image_hash",
    "style", "room_type", "custom_prompt", "aspect_ratio",
    "enhanced_prompt", "prompt_source", "vision_analysis",
    "model_used", "vision_analysis_ok", "latency_ms", "latency_breakdown",
    "output_image_paths", "success", "error",
    "feedback", "metadata",
)


def new_trace_id() -> str:
    return uuid.uuid4().hex


def image_hash(data: bytes) -> str:
    """毛坯原图内容哈希，用于评测集去重。失败返回空串，绝不抛。"""
    try:
        return hashlib.md5(data).hexdigest()
    except Exception:
        return ""


def write_trace(trace: dict) -> None:
    """把一条 trace 追加写入 JSONL。任何异常都吞掉，绝不影响调用方（生图）。"""
    try:
        path = os.getenv("TRACE_LOG_PATH", _DEFAULT_TRACE_PATH)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        record = {k: trace.get(k) for k in _TRACE_FIELDS if k in trace}
        record.setdefault("trace_id", new_trace_id())
        record.setdefault("created_at", datetime.now().isoformat())
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        # 埋点绝不能拖垮生图：只打日志，不抛
        print(f"[TRACE] 写入失败(已忽略): {e}")
