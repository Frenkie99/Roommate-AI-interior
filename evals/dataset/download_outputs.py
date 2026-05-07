"""下载效果图到本地 output/ 目录"""

import json
import time
from pathlib import Path

import httpx

from evals.config import METADATA_PATH, PROJECT_ROOT

API_BASE = "https://roommate-ai.cn"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def main():
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    pairs = metadata["pairs"]
    downloaded = 0
    skipped = 0
    failed = 0

    for i, pair in enumerate(pairs):
        output_path = pair.get("output_path", "")
        if not output_path:
            continue

        local_path = PROJECT_ROOT / output_path
        if local_path.exists():
            skipped += 1
            continue

        url = f"{API_BASE}/{output_path}"
        try:
            resp = httpx.get(url, verify=False, timeout=30)
            resp.raise_for_status()
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
