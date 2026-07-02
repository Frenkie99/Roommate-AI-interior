"""评测平台全局配置"""

import os
from pathlib import Path

# 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = PROJECT_ROOT / "evals"
DATA_DIR = EVALS_DIR / "data"
MOCK_IMAGE_DIR = DATA_DIR / "images"
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"

METADATA_PATH = DATA_DIR / "real_metadata.json"
EVAL_RESULTS_PATH = DATA_DIR / "eval_results.json"
BADCASE_NOTES_PATH = DATA_DIR / "badcase_notes.json"
GOLD_LABELS_PATH = DATA_DIR / "gold_labels.json"  # 人工金标准标注（评分器可信度的真值来源）
EVAL_REPORT_MD_PATH = DATA_DIR / "eval_report.md"      # Aggregator 产出的分维度聚合报告（人读）
EVAL_REPORT_JSON_PATH = DATA_DIR / "eval_report.json"  # 同一份报告的结构化版（程序/看板读）

# Trace（真实用户使用记录）——「用户使用过程」看板页数据源
#   真实数据由后端埋点追加写（默认 backend/data/traces.jsonl，可用 env TRACE_LOG_PATH 改）；
#   部署前 traces.jsonl 不存在 → 看板回退读 sample_traces.jsonl（示例假数据，仅供预览界面）。
TRACE_LOG_PATH = os.environ.get("TRACE_LOG_PATH",
                                str(PROJECT_ROOT / "backend" / "data" / "traces.jsonl"))
SAMPLE_TRACES_PATH = DATA_DIR / "sample_traces.jsonl"

# 指标范围: (min, max, higher_is_better)
METRIC_RANGES = {
    "iou": (0.0, 1.0, True),
    "fid": (0.0, 200.0, False),
    "clip_score": (0.0, 1.0, True),
    "structural_fidelity": (0.0, 100.0, True),
    "llm_judge": (1.0, 5.0, True),
}

# 指标中文显示名
METRIC_LABELS = {
    "iou": "IoU 分割精度",
    "fid": "FID 图像真实感",
    "clip_score": "CLIP 语义匹配度",
    "structural_fidelity": "结构保真度",
    "llm_judge": "LLM 综合评分",
}

# 数据集分片比例
DATASET_SPLITS = {
    "standard": 0.6,
    "competitor": 0.3,
    "corner_case": 0.1,
}

# 默认风格和房间类型
DEFAULT_STYLES = [
    "modern_luxury", "minimalist", "scandinavian", "japanese",
    "french_vintage", "industrial", "bohemian", "art_deco",
    "chinese_traditional", "coastal",
]

DEFAULT_ROOM_TYPES = [
    "living_room", "bedroom", "kitchen", "bathroom",
    "study", "dining_room", "balcony", "children_room",
    "entryway", "basement",
]

# Mock/Real 开关
USE_MOCK = False
