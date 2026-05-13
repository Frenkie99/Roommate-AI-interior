"""下载效果图到本地 output/ 目录"""

import json
import logging
import os
import re
import time
from pathlib import Path

import httpx

from evals.config import METADATA_PATH, PROJECT_ROOT

logger = logging.getLogger(__name__)

API_BASE = "https://roommate-ai.cn"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 路径白名单：只允许 output/ 下的相对路径，且不含 .. 或绝对路径
SAFE_PATH_PATTERN = re.compile(r"^output/[A-Za-z0-9_./-]+$")

# 单文件大小上限 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024


def _safe_local_path(output_path: str) -> Path | None:
    """
    校验 output_path 是否安全：
    1. 必须匹配白名单正则
    2. resolve() 后必须仍在 PROJECT_ROOT 内
    """
    if not output_path or not SAFE_PATH_PATTERN.match(output_path):
        logger.warning(f"REJECTED unsafe path (regex): {output_path!r}")
        return None

    local_path = (PROJECT_ROOT / output_path).resolve()
    if not local_path.is_relative_to(PROJECT_ROOT.resolve()):
        logger.warning(f"REJECTED unsafe path (escape): {output_path!r} -> {local_path}")
        return None

    return local_path


def main():
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    pairs = metadata["pairs"]
    downloaded = 0
    skipped = 0
    failed = 0

    # 使用长生命 client 复用 TLS 连接
    with httpx.Client(timeout=30) as client:
        for i, pair in enumerate(pairs):
            output_path = pair.get("output_path", "")
            if not output_path:
                continue

            local_path = _safe_local_path(output_path)
            if local_path is None:
                failed += 1
                continue

            if local_path.exists():
                skipped += 1
                continue

            url = f"{API_BASE}/{output_path}"
            try:
                resp = client.get(url)
                resp.raise_for_status()

                # 检查文件大小
                content_length = len(resp.content)
                if content_length > MAX_FILE_SIZE:
                    logger.warning(f"File too large ({content_length} bytes): {output_path}")
                    failed += 1
                    continue

                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(resp.content)
                downloaded += 1
                print(f"[{i+1}/{len(pairs)}] Downloaded: {output_path}")
            except Exception as e:
                failed += 1
                print(f"[{i+1}/{len(pairs)}] FAILED: {output_path} - {e}")

            time.sleep(0.5)

    print(f"\nDone. Downloaded: {downloaded}, Skipped: {skipped}, Failed: {failed}")


if __name__ == "__main__":
    main()
