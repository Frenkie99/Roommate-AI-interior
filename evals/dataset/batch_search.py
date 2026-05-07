"""
批量图片搜索下载脚本
通过 Bing Image Search 搜索并下载毛坯房候选图片。

用法:
    python -m evals.dataset.batch_search

下载的图片会保存到 evals/data/candidates/ 目录。
"""

import os
import re
import time
import hashlib
import urllib.parse
from pathlib import Path
from typing import List, Tuple

import httpx
from PIL import Image
from io import BytesIO

# ===== 配置 =====
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "candidates"

# 搜索关键词（多维度覆盖）
SEARCH_QUERIES = [
    # 标准场景 - 各房间类型
    ("毛坯房客厅", "standard"),
    ("毛坯房卧室", "standard"),
    ("毛坯房厨房", "standard"),
    ("毛坯房卫生间", "standard"),
    ("毛坯房书房", "standard"),
    ("毛坯房餐厅", "standard"),
    ("毛坯房阳台", "standard"),
    ("毛坯房玄关", "standard"),
    # 竞品对标场景
    ("毛坯房横梁", "competitor"),
    ("小户型毛坯房", "competitor"),
    ("极简风格毛坯房", "competitor"),
    ("毛坯房复式", "competitor"),
    ("毛坯房异形户型", "competitor"),
    # 极端场景
    ("暗光毛坯房", "corner_case"),
    ("杂物毛坯房", "corner_case"),
    ("毛坯房阁楼", "corner_case"),
    # 英文搜索（Pinterest/海外素材）
    ("unfinished room interior", "standard"),
    ("raw concrete room", "standard"),
    ("bare room renovation", "standard"),
    ("unfinished basement", "corner_case"),
    ("small apartment bare walls", "competitor"),
]

# 下载配置
MAX_PER_QUERY = 10
MIN_RESOLUTION = (300, 200)  # 最小分辨率
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
REQUEST_DELAY = 1.5  # 请求间隔（秒）


def search_bing_images(query: str, count: int = 20) -> List[str]:
    """通过 Bing Image Search 获取图片 URL 列表"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}&first=1&count={count}&qft=+filterui:photo-photo"

    image_urls = []
    try:
        client = httpx.Client(headers=headers, follow_redirects=True, timeout=15)
        response = client.get(url)
        response.raise_for_status()

        # 从 HTML 中提取图片 URL
        # Bing 图片搜索结果中的 murl 是原图 URL（HTML 实体编码格式）
        murl_pattern = r'murl&quot;:&quot;(https?://[^&]+?)&quot;'
        matches = re.findall(murl_pattern, response.text)
        image_urls.extend(matches)

        # 备用：未编码格式
        if len(image_urls) < 5:
            murl_pattern2 = r'"murl":"(https?://[^"]+?\.(?:jpg|jpeg|png|webp)[^"]*)"'
            matches2 = re.findall(murl_pattern2, response.text)
            image_urls.extend(matches2)

        client.close()
    except Exception as e:
        print(f"    搜索失败: {e}")

    return list(set(image_urls))[:count]


def download_image(client: httpx.Client, url: str, output_path: Path) -> bool:
    """下载单张图片，验证分辨率和大小"""
    try:
        response = client.get(url, timeout=15, follow_redirects=True)
        if response.status_code != 200:
            return False

        content_type = response.headers.get("content-type", "")
        if "image" not in content_type and not url.endswith((".jpg", ".jpeg", ".png", ".webp")):
            return False

        # 检查文件大小
        if len(response.content) > MAX_FILE_SIZE or len(response.content) < 5000:
            return False

        # 验证是有效图片
        img = Image.open(BytesIO(response.content))
        width, height = img.size

        # 检查最小分辨率
        if width < MIN_RESOLUTION[0] or height < MIN_RESOLUTION[1]:
            return False

        # 统一转为 JPEG 保存
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(str(output_path), "JPEG", quality=90)
        return True

    except Exception:
        return False


def analyze_basic_properties(image_path: Path) -> dict:
    """基础图像属性分析（不依赖 AI）"""
    try:
        img = Image.open(str(image_path))
        w, h = img.size
        file_size = image_path.stat().st_size

        return {
            "width": w,
            "height": h,
            "aspect_ratio": round(w / h, 2),
            "file_size_kb": round(file_size / 1024, 1),
            "format": img.format or "unknown",
            "is_landscape": w > h,
            "is_portrait": h > w,
            "resolution_ok": w >= 512 and h >= 384,
            # 宽高比判断是否像室内照片（通常 4:3 或 16:9）
            "likely_indoor_ratio": 1.0 <= w / h <= 2.0,
        }
    except Exception:
        return {"error": True}


def run_batch_search():
    """执行批量搜索下载"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 加载已下载文件列表（支持续传）
    existing = set(f.name for f in OUTPUT_DIR.iterdir() if f.is_file())
    print(f"已有 {len(existing)} 张候选图片")

    download_client = httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        follow_redirects=True,
        timeout=15,
    )

    total_downloaded = 0
    results = []

    for query, category in SEARCH_QUERIES:
        print(f"\n搜索: '{query}' [{category}]")
        urls = search_bing_images(query, count=MAX_PER_QUERY + 5)
        print(f"  找到 {len(urls)} 个图片 URL")

        downloaded = 0
        for i, url in enumerate(urls):
            if downloaded >= MAX_PER_QUERY:
                break

            # 生成文件名
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"{category}_{query.replace(' ', '_')}_{url_hash}.jpg"

            if filename in existing:
                continue

            output_path = OUTPUT_DIR / filename
            if download_image(download_client, url, output_path):
                props = analyze_basic_properties(output_path)
                props["filename"] = filename
                props["query"] = query
                props["category"] = category
                props["source_url"] = url
                results.append(props)
                downloaded += 1
                total_downloaded += 1
                print(f"    + {filename} ({props['width']}x{props['height']})")
            else:
                print(f"    x 跳过 (无效/太小)")

            time.sleep(0.3)  # 避免过快请求

        time.sleep(REQUEST_DELAY)

    download_client.close()

    # 保存结果摘要
    import csv
    csv_path = OUTPUT_DIR.parent / "candidates_summary.csv"
    if results:
        fieldnames = ["filename", "query", "category", "width", "height",
                       "aspect_ratio", "file_size_kb", "resolution_ok",
                       "likely_indoor_ratio", "source_url"]
        with open(str(csv_path), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)

    print(f"\n完成！共下载 {total_downloaded} 张新图片")
    print(f"保存目录: {OUTPUT_DIR}")
    print(f"摘要 CSV: {csv_path}")


if __name__ == "__main__":
    run_batch_search()
