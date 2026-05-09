"""
批量生成效果图脚本
遍历评测集中的毛坯图，均匀分配风格，调用产品 API 生成效果图。
room_type 不传，由产品内部 LLM 自动分析。

用法:
    python -m evals.dataset.batch_generate
"""

import json
import random
import sys
import time
from pathlib import Path
from functools import partial

import httpx

print = partial(print, flush=True)

# ===== 配置 =====
API_BASE = "https://roommate-ai.cn"
GENERATE_URL = f"{API_BASE}/api/v1/generate"
# TLS 校验默认开启；如证书有问题应该修证书，而不是禁验证。
# 仅在显式设置 EVALS_INSECURE_TLS=1 的开发场景下临时关闭，
# 关闭时会在 stderr 打印警告以提醒不要在生产环境使用。
import os as _os
import sys as _sys
VERIFY_SSL = True
if _os.getenv("EVALS_INSECURE_TLS") == "1":
    VERIFY_SSL = False
    print("[WARN] EVALS_INSECURE_TLS=1 detected; TLS verification DISABLED. "
          "DO NOT use this in production.", file=_sys.stderr)

STYLES = [
    "modern_luxury", "chinese_modern", "american_transitional",
    "european_neoclassical", "industrial_loft", "natural_wood",
    "japanese_traditional", "bohemian", "bauhaus", "modern_minimalist",
]

METADATA_PATH = Path(__file__).resolve().parent.parent / "data" / "real_metadata.json"

MAX_RETRIES = 3
REQUEST_DELAY = 3  # 请求间隔秒数
RETRY_DELAY = 30   # 重试等待秒数
COOLDOWN_AFTER = 3  # 连续失败几次后进入冷却


def assign_styles(total: int) -> list:
    styles = STYLES * (total // len(STYLES) + 1)
    random.seed(42)
    random.shuffle(styles)
    return styles[:total]


def generate_one(image_path: str, style: str) -> dict:
    """调用产品 API 生成一张效果图，带重试"""
    for attempt in range(MAX_RETRIES):
        try:
            with open(image_path, "rb") as f:
                files = {"image": (Path(image_path).name, f, "image/jpeg")}
                data = {
                    "style": style,
                    "aspect_ratio": "auto",
                    "image_size": "1K",
                }
                resp = httpx.post(GENERATE_URL, files=files, data=data,
                                  verify=VERIFY_SSL, timeout=120)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 0:
                raise Exception(f"API error: {result}")
            return result["data"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (attempt + 1)
                print(f"    服务器错误 {e.response.status_code}，{wait}s 后重试 ({attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                raise
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise


def main():
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    pairs = metadata["pairs"]
    total = len(pairs)
    print(f"评测集共 {total} 张图片")

    remaining = [(i, p) for i, p in enumerate(pairs) if not p.get("output_path")]
    print(f"已有 {total - len(remaining)} 张生成过，剩余 {len(remaining)} 张待生成")

    style_list = assign_styles(total)
    succeeded = 0
    failed = 0
    consecutive_fails = 0

    for idx, (i, pair) in enumerate(remaining):
        img_path = Path(pair["input_path"])
        if not img_path.is_absolute():
            img_path = Path(__file__).resolve().parent.parent / img_path

        style = style_list[i]
        pair_id = pair["pair_id"]

        # 连续失败冷却
        if consecutive_fails >= COOLDOWN_AFTER:
            print(f"\n连续 {consecutive_fails} 次失败，冷却 60s...")
            time.sleep(60)
            consecutive_fails = 0

        print(f"\n[{idx+1}/{len(remaining)}] {pair_id}: {Path(pair['input_path']).name}")
        print(f"  风格: {style}")

        try:
            result = generate_one(str(img_path), style)
            output_url = result["output_urls"][0]
            output_path = output_url.lstrip("/")
            print(f"  生成成功: {output_url}")

            pair["output_path"] = output_path
            pair["style"] = style
            pair["prompt"] = result.get("prompt", "")[:200]
            succeeded += 1
            consecutive_fails = 0

        except Exception as e:
            print(f"  生成失败: {e}")
            pair["output_path"] = ""
            pair["style"] = style
            failed += 1
            consecutive_fails += 1

        if (idx + 1) % 5 == 0:
            with open(METADATA_PATH, "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            print(f"\n--- 进度已保存 ({idx+1}/{len(remaining)}) ---")

        time.sleep(REQUEST_DELAY)

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"完成！成功: {succeeded}, 失败: {failed}")
    print(f"metadata 已更新: {METADATA_PATH}")


if __name__ == "__main__":
    main()
