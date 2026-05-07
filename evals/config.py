"""评测平台全局配置"""

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
