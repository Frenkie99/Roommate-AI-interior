"""下载效果图到本地 output/ 目录"""

import json
import re
import time
from pathlib import Path

import httpx

from evals.config import METADATA_PATH, PROJECT_ROOT

API_BASE = "https://roommate-ai.cn"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 路径白名单：metadata 中的 output_path 必须形如 output/xxx.png，
# 防止恶意 metadata（或被 MITM 篡改的响应）通过 ../../ 写到任意位置
_SAFE_PATH_RE = re.compile(r"^output/[A-Za-z0-9_./-]+$")
# 单文件大小上限，防止响应填爆磁盘
_MAX_BYTES = 50 * 1024 * 1024  # 50MB


def _safe_local_path(output_path: str) -> Path:
    """校验 output_path 后返回沙箱内绝对路径；不安全时抛 ValueError"""
    if not _SAFE_PATH_RE.match(output_path):
        raise ValueError(f"unsafe output_path: {output_path!r}")
    resolved = (PROJECT_ROOT / output_path).resolve()
    project_root = PROJECT_ROOT.resolve()
    if not resolved.is_relative_to(project_root):
        raise ValueError(f"path escape: {output_path!r}")
    return resolved


def main():
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    pairs = metadata["pairs"]
    downloaded = 0
    skipped = 0
    failed = 0

    # 长生命 client，复用 TLS 连接（默认 verify=True，绝不要禁用）
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        for i, pair in enumerate(pairs):
            output_path = pair.get("output_path", "")
            if not output_path:
                continue

            try:
                local_path = _safe_local_path(output_path)
            except ValueError as exc:
                failed += 1
                print(f"[{i+1}/{len(pairs)}] REJECTED unsafe path: {exc}")
                continue

            if local_path.exists():
                skipped += 1
                continue

            url = f"{API_BASE}/{output_path}"
            try:
                resp = client.get(url)
                resp.raise_for_status()
                content_length = int(resp.headers.get("content-length", 0) or 0)
                if content_length > _MAX_BYTES or len(resp.content) > _MAX_BYTES:
                    raise ValueError(f"response too large: {content_length} bytes")
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
