"""Mock 数据生成器：生成假图片 + metadata.json"""

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from evals.config import (
    MOCK_IMAGE_DIR, METADATA_PATH, DATA_DIR,
    DEFAULT_STYLES, DEFAULT_ROOM_TYPES, DATASET_SPLITS,
)
from evals.dataset.schemas import DatasetMetadata, ImagePair

# 颜色调色板（input 用偏灰暗色，output 用鲜艳色）
INPUT_COLORS = [
    (180, 180, 170), (160, 155, 145), (170, 165, 160),
    (190, 185, 175), (175, 170, 165), (165, 160, 155),
    (185, 180, 170), (155, 150, 145), (195, 190, 180),
    (172, 167, 162),
]

OUTPUT_COLORS = [
    (220, 180, 140), (180, 210, 170), (200, 170, 190),
    (170, 190, 220), (210, 200, 160), (190, 220, 200),
    (230, 190, 160), (180, 200, 210), (200, 180, 200),
    (190, 210, 180),
]

# 标签池
TAG_POOL = {
    "standard": [["well_lit", "clean"], ["standard", "bright"], ["well_lit", "spacious"]],
    "competitor": [["complex_structure", "beam"], ["specific_style", "minimalist"], ["hard_decor", "load_bearing"]],
    "corner_case": [["dark_light", "cluttered"], ["tiny_irregular", "narrow"], ["dark_light", "extreme_angle"]],
}

# Prompt 模板
PROMPT_TEMPLATES = [
    "A {style} {room_type} with warm lighting and natural materials",
    "{style} design for a {room_type}, featuring elegant furniture",
    "Modern {style} renovation of a {room_type} with high ceiling",
    "Luxurious {style} {room_type} with panoramic window",
    "Cozy {style} {room_type} renovation with sustainable materials",
]


class MockDataGenerator:
    def __init__(self, num_pairs: int = 10, seed: int = 42):
        self.num_pairs = num_pairs
        self.seed = seed

    def generate(self) -> DatasetMetadata:
        random.seed(self.seed)
        MOCK_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

        pairs = []
        for i in range(self.num_pairs):
            split = self._assign_split(i)
            style = DEFAULT_STYLES[i % len(DEFAULT_STYLES)]
            room_type = DEFAULT_ROOM_TYPES[i % len(DEFAULT_ROOM_TYPES)]
            tags = random.choice(TAG_POOL[split])
            prompt = random.choice(PROMPT_TEMPLATES).format(
                style=style.replace("_", " "), room_type=room_type.replace("_", " ")
            )

            input_path = self._create_mock_image(i, is_input=True)
            output_path = self._create_mock_image(i, is_input=False)

            pair = ImagePair(
                pair_id=f"pair_{i:03d}",
                input_path=str(input_path),
                output_path=str(output_path),
                prompt=prompt,
                style=style,
                room_type=room_type,
                tags=tags,
                dataset_split=split,
                metadata={"seed": self.seed, "generator": "mock"},
            )
            pairs.append(pair)

        metadata = DatasetMetadata(
            version="1.0",
            total_pairs=len(pairs),
            pairs=pairs,
        )
        metadata.save(str(METADATA_PATH))
        print(f"Generated {len(pairs)} pairs, saved to {METADATA_PATH}")
        return metadata

    def _create_mock_image(self, index: int, is_input: bool) -> str:
        pair_id = f"pair_{index:03d}"
        suffix = "input" if is_input else "output"
        filename = f"{pair_id}_{suffix}.png"
        path = MOCK_IMAGE_DIR / filename

        colors = INPUT_COLORS if is_input else OUTPUT_COLORS
        bg_color = colors[index % len(colors)]
        img = Image.new("RGB", (512, 384), bg_color)
        draw = ImageDraw.Draw(img)

        # 画简单的"房间"形状
        if is_input:
            # 灰色墙壁 + 地板线
            draw.rectangle([50, 50, 462, 334], outline=(100, 100, 100), width=2)
            draw.line([50, 250, 462, 250], fill=(120, 120, 120), width=2)
        else:
            # 彩色渲染效果
            draw.rectangle([50, 50, 462, 334], outline=bg_color, width=3)
            draw.rectangle([60, 60, 452, 240], fill=(bg_color[0]+20, bg_color[1]+20, bg_color[2]+20))

        # 文字标注
        label = f"{pair_id}\n{'INPUT' if is_input else 'OUTPUT'}\n{suffix}"
        draw.text((180, 160), label, fill=(50, 50, 50))

        img.save(str(path))
        return str(path)

    def _assign_split(self, index: int) -> str:
        # 按 DATASET_SPLITS 比例分配
        standard_count = round(self.num_pairs * DATASET_SPLITS["standard"])
        competitor_count = round(self.num_pairs * DATASET_SPLITS["competitor"])

        if index < standard_count:
            return "standard"
        elif index < standard_count + competitor_count:
            return "competitor"
        else:
            return "corner_case"


if __name__ == "__main__":
    gen = MockDataGenerator(num_pairs=10, seed=42)
    metadata = gen.generate()
    print(f"Total pairs: {metadata.total_pairs}")
    for p in metadata.pairs[:3]:
        print(f"  {p.pair_id}: {p.style} / {p.room_type} / {p.dataset_split} / {p.tags}")
