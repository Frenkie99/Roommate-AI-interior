"""
AI 图片预筛选脚本
用视觉模型批量分析候选图片，判断是否适合作为评测数据集输入。

用法:
    python -m evals.dataset.screener --dir <图片目录> --output <输出CSV路径>

示例:
    python -m evals.dataset.screener --dir ./input_candidates --output evals/data/screening_results.csv
"""

import argparse
import csv
import base64
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import httpx


# ===== 配置 =====
API_BASE_URL = "https://api.apiyi.com"
MODEL_NAME = "gemini-2.5-flash-preview"

SCREENING_PROMPT = """你是一个室内设计AI评测数据集的图片筛选专家。请分析这张图片，严格按以下JSON格式输出评估结果（不要输出任何其他内容）：

{
  "is_indoor": true/false,
  "is_raw_or_simple": true/false,
  "room_type": "客厅/卧室/厨房/卫生间/书房/餐厅/阳台/玄关/地下室/其他",
  "lighting": "明亮/正常/偏暗/极暗",
  "raw_state": "纯毛坯/简装白墙/半装修/精装修",
  "has_complete_view": true/false,
  "suitable_for_eval": true/false,
  "quality_note": "一句话说明图片质量或问题",
  "recommended_split": "standard/competitor/corner_case",
  "corner_case_type": "无/暗光/杂物多/异形户型/极小空间/镜面反射"
}

判断标准:
- is_indoor: 是否为室内空间（排除室外、纯风景、人物特写）
- is_raw_or_simple: 是否为毛坯房或简装状态（排除精装修、已完工的房间）
- has_complete_view: 至少能看到2面墙+地面，视角完整
- suitable_for_eval: 综合判断是否适合作为评测输入（需要是真实的室内毛坯/简装空间，视角完整，清晰度高）
- recommended_split:
  - standard: 采光正常、格局方正的常规空间
  - competitor: 有横梁、复杂结构、特定风格特征、小户型
  - corner_case: 暗光、杂物多、极小异形、极端条件
"""


def get_api_key() -> str:
    key = os.getenv("LLM_APIYI_KEY")
    if not key:
        # 尝试从多个 .env 路径读取
        root = Path(__file__).resolve().parent.parent.parent
        env_paths = [root / "backend" / ".env", root / ".env"]
        for env_path in env_paths:
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("LLM_APIYI_KEY="):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            if key:
                break
    if not key:
        print("错误: 未找到 LLM_APIYI_KEY，请在 .env 中设置或设为环境变量")
        sys.exit(1)
    return key


def image_to_base64(image_path: str) -> tuple[str, str]:
    """读取图片并转为 base64，返回 (base64_data, mime_type)"""
    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp", ".bmp": "image/bmp"}
    mime_type = mime_map.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return data, mime_type


def analyze_image(client: httpx.Client, api_key: str, image_path: str) -> Optional[Dict]:
    """调用视觉模型分析单张图片"""
    try:
        img_b64, mime_type = image_to_base64(image_path)
    except Exception as e:
        return {"error": str(e), "file": str(image_path)}

    payload = {
        "contents": [{
            "parts": [
                {"inlineData": {"mimeType": mime_type, "data": img_b64}},
                {"text": SCREENING_PROMPT}
            ]
        }],
        "generationConfig": {
            "responseModalities": ["TEXT"],
            "responseMimeType": "application/json",
            "temperature": 0.1,
            "maxOutputTokens": 1024
        }
    }

    url = f"{API_BASE_URL}/v1beta/models/{MODEL_NAME}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    try:
        response = client.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        if "candidates" in result and result["candidates"]:
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            # 清理可能的 markdown 代码块
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            return json.loads(text)
        return {"error": "No response from model", "file": str(image_path)}
    except Exception as e:
        return {"error": str(e), "file": str(image_path)}


def scan_directory(directory: str) -> List[str]:
    """扫描目录下所有图片文件"""
    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    images = []
    for f in Path(directory).iterdir():
        if f.is_file() and f.suffix.lower() in valid_exts:
            images.append(str(f))
    return sorted(images)


def run_screening(image_dir: str, output_path: str) -> None:
    """批量筛选图片"""
    api_key = get_api_key()
    images = scan_directory(image_dir)

    if not images:
        print(f"在 {image_dir} 中未找到图片文件")
        return

    print(f"找到 {len(images)} 张候选图片，开始 AI 预筛选...")

    results = []
    client = httpx.Client(timeout=30)

    for i, img_path in enumerate(images, 1):
        filename = Path(img_path).name
        print(f"  [{i}/{len(images)}] 分析: {filename}...", end=" ")

        analysis = analyze_image(client, api_key, img_path)

        if "error" in analysis:
            print(f"失败 ({analysis['error']})")
            row = {"filename": filename, "file_path": img_path, "error": analysis["error"]}
        else:
            # 综合判断
            suitable = analysis.get("suitable_for_eval", False)
            status = "PASS" if suitable else "SKIP"
            print(f"{status} | {analysis.get('room_type', '?')} | {analysis.get('raw_state', '?')}")

            row = {"filename": filename, "file_path": img_path}
            row.update(analysis)
            row["status"] = status

        results.append(row)

    client.close()

    # 写入 CSV
    if results:
        fieldnames = ["filename", "file_path", "status", "is_indoor", "is_raw_or_simple",
                       "room_type", "lighting", "raw_state", "has_complete_view",
                       "suitable_for_eval", "recommended_split", "corner_case_type",
                       "quality_note", "error"]

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)

    # 汇总
    passed = sum(1 for r in results if r.get("status") == "PASS")
    print(f"\n筛选完成: {passed}/{len(results)} 张适合作为评测输入")
    print(f"结果已保存到: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI 图片预筛选")
    parser.add_argument("--dir", required=True, help="候选图片目录")
    parser.add_argument("--output", default="evals/data/screening_results.csv", help="输出 CSV 路径")
    args = parser.parse_args()
    run_screening(args.dir, args.output)
