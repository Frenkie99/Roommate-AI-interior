#!/usr/bin/env python3
"""
从范例图片反推纯净风格提示词 —— Gemini 多模态多图交集运算
================================================================
对每个风格文件夹内的所有范例图片执行多图交集运算（Intersection），
提取"零房间依赖"的通用风格描述。

用法：
    # 处理所有有图片的风格
    python scripts/extract_style_prompts.py

    # 只处理指定风格（文件夹名）
    python scripts/extract_style_prompts.py --style 01_modern_luxury

    # 预览模式：看有哪些风格和图片，不调用 API
    python scripts/extract_style_prompts.py --dry-run

    # 强制重新提取某个风格（覆盖已有结果）
    python scripts/extract_style_prompts.py --style 01_modern_luxury --force

输出文件：backend/prompts/prompt_data_preparation/style_prompts.json

依赖：httpx（必需），Pillow（可选，用于自动缩放大图）
"""

import os
import sys
import json
import base64
import time
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

BASE_URL = "https://api.apiyi.com"
# 模型优先级（API易上 gemini-3-flash-preview 已下线，图像模型支持 TEXT 输出）
MODEL_PRIORITY = [
    "gemini-3-pro-image-preview",    # 首选：质量更高，分析更细腻
    "gemini-2.5-flash-image",        # 备选：更快更便宜
]

# 路径 — 均相对于项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STYLES_DIR = PROJECT_ROOT / "backend" / "prompts" / "prompt_data_preparation" / "01_styles"
OUTPUT_PATH = PROJECT_ROOT / "backend" / "prompts" / "prompt_data_preparation" / "style_prompts.json"

# API 调用
MAX_RETRIES = 3
RETRY_DELAY = 3.0          # 基础等待秒数（会指数退避）
REQUEST_TIMEOUT = 300.0     # 16 张图的请求可能需要较长时间

# 图片限制（超出会尝试缩放，需 PIL）
MAX_IMAGE_DIMENSION = 800    # 16 张图场景需控制单张尺寸，避免 payload 过大
MAX_PAYLOAD_BYTES = 18 * 1024 * 1024   # 18MB，留余量给 JSON 结构

# 支持的图片格式
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# 北京时间
BJT = timezone(timedelta(hours=8))

# 目录名后缀 → prompt_builder.py 中 canonical style ID 的映射
# 因为 prompt_builder.py 的 key 与文件夹命名不完全一致
STYLE_ID_OVERRIDE = {
    "new_chinese": "chinese_modern",
    "warm_wood": "natural_wood",
}

# ---------------------------------------------------------------------------
# System Prompt — "零房间依赖" 交集运算
# ---------------------------------------------------------------------------

def build_system_prompt(image_count: int) -> str:
    """根据实际图片数量动态生成 System Prompt"""
    return f"""你是一位高级室内设计视觉分析专家。我为你提供了属于同一种室内装修风格的 {image_count} 张不同空间的高清效果图。

请执行【多图交集运算（Intersection）】，并严格遵循以下"零房间依赖"的降噪清洗规则：
1. 提取共性：只提取在大多数图片中共同出现的【视觉肌理、色彩体系、光影逻辑、家具语言】。忽略单张图特有的杂物或特定布局。
2. 零房间依赖（极度重要）：风格描述中【严禁】出现特定房间的具象家具名词（如 bed, sofa, dining table, bathtub）。必须泛化为类别词（例如：将 boucle sofa 泛化为 low-profile seating；将 double bed 泛化为 primary sleeping surface）。
3. 属性精确绑定：材质不可绑定房间，只能绑定表面类型（如：用于墙面和地面，而非用于卧室）。

请输出纯 JSON 格式，结构严格如下：
{{
  "MATERIAL_AND_FINISHES": "描述主材与辅材体系，如微水泥、木饰面等，并说明适用的表面类型。",
  "COLOR_PALETTE": "描述色彩分配策略，必须量化比例，如主色 60%、辅助色 25%、点缀色 5%。",
  "LIGHTING_SCHEME": "描述光照逻辑，包括环境光、主灯/无主灯设定、气氛灯带分布及色温 K 值。",
  "FURNITURE_STYLE": "描述家具的通用造型语言，如线条风格、腿部材质、表面工艺。严禁出现具体功能家具名称。"
}}

只输出 JSON，不要包含 markdown 代码块标记。"""


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def get_api_key() -> str:
    """获取 API Key，优先 APIYI_KEY，备选 LLM_APIYI_KEY"""
    for var in ("APIYI_KEY", "LLM_APIYI_KEY"):
        key = os.getenv(var)
        if key:
            return key
    print("❌ 未找到 API Key！请设置 APIYI_KEY 或 LLM_APIYI_KEY 环境变量", file=sys.stderr)
    print("   export APIYI_KEY=your_key_here", file=sys.stderr)
    sys.exit(1)


def detect_mime_type(data: bytes) -> str:
    """通过 magic bytes 检测图片 MIME 类型"""
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if data[:2] == b'\xff\xd8':
        return "image/jpeg"
    if data[:4] == b'RIFF' and len(data) > 11 and data[8:12] == b'WEBP':
        return "image/webp"
    if data[:2] == b'BM':
        return "image/bmp"
    return "image/jpeg"


def resize_if_needed(data: bytes) -> bytes:
    """若图片长边超过 MAX_IMAGE_DIMENSION，等比缩放（需 PIL）"""
    try:
        from PIL import Image
        from io import BytesIO

        img = Image.open(BytesIO(data))
        w, h = img.size
        if max(w, h) <= MAX_IMAGE_DIMENSION:
            return data

        # resize 前保存原始格式：resize 后 img.format 会丢失（变 None）
        fmt = (img.format or "JPEG").upper()
        if fmt not in ("JPEG", "PNG", "WEBP"):
            fmt = "JPEG"

        ratio = MAX_IMAGE_DIMENSION / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)

        # JPEG 不支持透明通道/调色板，RGBA/P 等模式需先转 RGB（透明底垫白）
        if fmt == "JPEG" and img.mode != "RGB":
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                rgba = img.convert("RGBA")
                background.paste(rgba, mask=rgba.split()[-1])
                img = background
            else:
                img = img.convert("RGB")

        buf = BytesIO()
        img.save(buf, format=fmt, quality=85)
        resized = buf.getvalue()

        print(f"   📐 缩放: {w}×{h} → {new_size[0]}×{new_size[1]} "
              f"({len(data) // 1024}KB → {len(resized) // 1024}KB)")
        return resized
    except ImportError:
        return data


def load_images(style_dir: Path) -> list[dict]:
    """加载风格文件夹内所有图片，返回 Gemini inlineData parts 列表"""
    image_files = sorted(
        f for f in style_dir.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    )

    if not image_files:
        return []

    print(f"   📷 找到 {len(image_files)} 张图片：")
    for f in image_files:
        size_kb = f.stat().st_size // 1024
        print(f"      {f.name}  ({size_kb}KB)")

    parts = []
    for f in image_files:
        data = f.read_bytes()
        data = resize_if_needed(data)
        mime = detect_mime_type(data)
        b64 = base64.b64encode(data).decode("utf-8")
        parts.append({
            "inlineData": {
                "mimeType": mime,
                "data": b64
            }
        })

    total_b64 = sum(len(p["inlineData"]["data"]) for p in parts)
    total_mb = total_b64 / (1024 * 1024)
    print(f"   📦 Base64 总大小: {total_mb:.1f}MB")

    if total_b64 > MAX_PAYLOAD_BYTES:
        print(f"   ⚠️  超过 {MAX_PAYLOAD_BYTES // 1024 // 1024}MB 安全限制！"
              f" 建议减少图片数量或安装 Pillow 启用自动缩放")
        # 不阻止，让 API 决定是否拒绝

    return parts


def call_gemini(images_parts: list[dict], style_id: str, api_key: str) -> Optional[dict]:
    """
    调用 Gemini 多模态 API，按 MODEL_PRIORITY 降级尝试。

    Returns:
        解析后的风格 JSON dict，失败返回 None
    """
    try:
        import httpx
    except ImportError:
        print("   ❌ 缺少 httpx 依赖，请安装: pip install httpx")
        return None

    image_count = len(images_parts)
    system_prompt = build_system_prompt(image_count)

    # 组装 parts：[img1, img2, ..., imgN, text_prompt]
    parts = list(images_parts)
    parts.append({"text": system_prompt})

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    for model in MODEL_PRIORITY:
        print(f"   🤖 尝试模型: {model}")

        payload = {
            "contents": [{
                "parts": parts
            }],
            "generationConfig": {
                "responseModalities": ["TEXT"],
                "temperature": 0.4,
                "maxOutputTokens": 4096
            }
        }

        api_url = f"{BASE_URL}/v1beta/models/{model}:generateContent"
        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if attempt > 1:
                    wait = RETRY_DELAY * (2 ** (attempt - 2))
                    print(f"   ⏳ 等待 {wait:.0f}s 后重试...")
                    time.sleep(wait)

                print(f"   🚀 请求 (尝试 {attempt}/{MAX_RETRIES})...", end="", flush=True)
                start = time.time()

                with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                    resp = client.post(api_url, headers=headers, json=payload)

                elapsed = time.time() - start
                print(f"  HTTP {resp.status_code}  ({elapsed:.1f}s)")

                if resp.status_code == 200:
                    result = _parse_response(resp.json(), style_id)
                    if result:
                        result["_model_used"] = model  # 记录实际使用的模型
                        return result
                    # 解析失败（截断/非 JSON）：先重试，重试耗尽后自然降级到备选模型
                    print(f"   🔄 响应解析失败，将重试...")
                    last_error = "parse_failed"
                    continue

                if resp.status_code == 429:
                    print(f"   ⏳ Rate limited")
                    last_error = f"HTTP 429"
                    continue

                if resp.status_code >= 500 or (
                    resp.status_code == 400 and ("no available channels" in resp.text or "JSON mode" in resp.text)
                ):
                    # 503 + "no available channels" → 模型不可用
                    # 400 + "JSON mode" → 模型不支持 JSON Mode
                    if "no available channels" in resp.text:
                        print(f"   🔀 模型 {model} 不可用，切换...")
                        break
                    if "JSON mode" in resp.text:
                        print(f"   🔀 模型 {model} 不支持 JSON Mode，切换...")
                        break
                    print(f"   🔄 服务端错误，重试...")
                    last_error = f"HTTP {resp.status_code}"
                    continue

                # 4xx 单模型不可重试，但可能是模型级问题（下线/改名/不支持），
                # 降级尝试备选模型而非直接放弃整个风格
                error_body = resp.text[:500]
                print(f"   ❌ 客户端错误: {error_body}")
                print(f"   🔀 跳过模型 {model}，尝试备选...")
                last_error = f"HTTP {resp.status_code}"
                break

            except httpx.TimeoutException:
                print(f"\n   ⏰ 请求超时 ({REQUEST_TIMEOUT}s)")
                last_error = "timeout"
            except httpx.ConnectError as e:
                print(f"\n   🔌 连接失败: {e}")
                last_error = str(e)
            except Exception as e:
                print(f"\n   ❌ 异常: {type(e).__name__}: {e}")
                last_error = str(e)

        print(f"   ⚠️  模型 {model} 全部 {MAX_RETRIES} 次尝试失败（最后: {last_error}）")

    print(f"   ❌ 所有模型均失败")
    return None


def _parse_response(result: dict, style_id: str) -> Optional[dict]:
    """从 Gemini generateContent 响应中提取并验证 JSON"""
    try:
        candidates = result.get("candidates", [])
        if not candidates:
            print("   ❌ 响应中无 candidates")
            # 检查是否有 promptFeedback（安全过滤）
            feedback = result.get("promptFeedback", {})
            if feedback:
                reason = feedback.get("blockReason", "UNKNOWN")
                print(f"   🛑 被安全过滤拦截: {reason}")
            return None

        candidate = candidates[0]

        # 检查结束原因
        finish = candidate.get("finishReason", "UNKNOWN")
        safety = candidate.get("safetyRatings", [])
        if finish == "SAFETY":
            print(f"   🛑 被安全策略终止: {safety}")
            return None
        if finish == "MAX_TOKENS":
            print(f"   ⚠️  输出被截断 (MAX_TOKENS)，可能需要增大 maxOutputTokens")

        content = candidate.get("content", {})
        parts = content.get("parts", [])

        text = ""
        for part in parts:
            if "text" in part:
                text += part["text"]

        if not text:
            print("   ❌ 响应中无文本内容")
            return None

        # 清理可能的 markdown 包裹
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # 解析 JSON
        parsed = json.loads(text)

        # 验证必需字段
        required = ["MATERIAL_AND_FINISHES", "COLOR_PALETTE",
                     "LIGHTING_SCHEME", "FURNITURE_STYLE"]
        missing = [k for k in required if k not in parsed]
        if missing:
            print(f"   ⚠️  响应缺少字段: {missing}，将保留空值")
            for k in missing:
                parsed[k] = ""

        return parsed

    except json.JSONDecodeError as e:
        print(f"   ❌ JSON 解析失败: {e}")
        # 打印原始文本前 500 字符帮助调试
        preview = text[:500] if 'text' in dir() else "(无文本)"
        print(f"   原始响应: {preview}")
        return None


# ---------------------------------------------------------------------------
# 持久化
# ---------------------------------------------------------------------------

def load_existing() -> dict:
    """加载已有结果，支持增量更新"""
    if OUTPUT_PATH.exists():
        try:
            data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # 过滤掉纯元数据（没有四个必需字段的是旧格式占位）
                return {
                    k: v for k, v in data.items()
                    if isinstance(v, dict) and "MATERIAL_AND_FINISHES" in v
                }
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_results(results: dict):
    """保存到 JSON 文件，确保目录存在"""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def extract_style_id(dirname: str) -> str:
    """
    从目录名提取 canonical style ID。
    例：'01_modern_luxury' → 'modern_luxury'
         '02_new_chinese' → 'chinese_modern'（通过 STYLE_ID_OVERRIDE 映射）
    """
    # 去掉数字前缀 "01_", "02_" 等
    parts = dirname.split("_", 1)
    raw = parts[1] if len(parts) > 1 else dirname
    # 检查是否需要映射到 prompt_builder.py 的 canonical ID
    return STYLE_ID_OVERRIDE.get(raw, raw)


def main():
    parser = argparse.ArgumentParser(
        description="从范例图片反推纯净风格提示词（Gemini 多模态多图交集运算）"
    )
    parser.add_argument(
        "--style", type=str,
        help="只处理指定风格的文件夹名（如 01_modern_luxury）"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="预览模式：列出风格和图片数，不调用 API"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="强制覆盖已有结果"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("🏗️  风格提示词提取器")
    print(f"   模型: {MODEL_PRIORITY}")
    print(f"   API:  {BASE_URL}")
    print(f"   图片目录: {STYLES_DIR}")
    print(f"   输出文件: {OUTPUT_PATH}")
    print("=" * 70)

    if not STYLES_DIR.exists():
        print(f"❌ 图片目录不存在: {STYLES_DIR}")
        sys.exit(1)

    # 收集风格文件夹
    all_dirs = sorted(
        d for d in STYLES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    if args.style:
        target_dirs = [d for d in all_dirs if d.name == args.style]
        if not target_dirs:
            print(f"❌ 未找到文件夹: {args.style}")
            available = [d.name for d in all_dirs]
            print(f"   可用: {available}")
            sys.exit(1)
    else:
        target_dirs = all_dirs

    print(f"\n📂 共 {len(target_dirs)} 个风格文件夹待处理\n")

    # 加载已有结果
    api_key = None if args.dry_run else get_api_key()
    results = load_existing()
    if results:
        print(f"📋 已有 {len(results)} 个风格的结果（将被跳过，--force 覆盖）: "
              f"{list(results.keys())}\n")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for style_dir in target_dirs:
        style_id = extract_style_id(style_dir.name)
        display_name = style_dir.name

        print(f"{'─' * 60}")
        print(f"🎨 {display_name}")
        print(f"   canonical ID: {style_id}")

        # 跳过已处理的
        if style_id in results and not args.force:
            print(f"   ⏭️  已有结果，跳过（--force 可覆盖）")
            skip_count += 1
            continue

        # 加载图片
        images = load_images(style_dir)
        if not images:
            print(f"   ⚠️  文件夹无图片，跳过")
            skip_count += 1
            continue

        if args.dry_run:
            print(f"   🔍 [dry-run] 将发送 {len(images)} 张图片，跳过 API 调用")
            continue

        # 调用 Gemini
        print(f"   🎯 开始多图交集运算（{len(images)} 张图片 → 1 次 API 调用）")
        parsed = call_gemini(images, style_id, api_key)

        if parsed:
            # 组装带元数据的结果
            results[style_id] = {
                "_meta": {
                    "model": parsed.pop("_model_used", MODEL_PRIORITY[0]),
                    "image_count": len(images),
                    "folder": display_name,
                    "extracted_at": datetime.now(BJT).isoformat()
                },
                **parsed
            }
            # 立即持久化
            save_results(results)
            print(f"   ✅ 提取成功，已保存")
            success_count += 1
        else:
            print(f"   ❌ 提取失败")
            fail_count += 1

    # 最终汇总
    print(f"\n{'=' * 70}")
    print(f"📊 汇总")

    empty_dirs = 0
    for d in all_dirs:
        imgs = [f for f in d.iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS]
        status = "✅" if extract_style_id(d.name) in results else ("📭" if not imgs else "⏳")
        print(f"   {status}  {d.name}  ({len(imgs)} 张图) → {extract_style_id(d.name)}")

    print(f"\n   ✅ {success_count} 成功  ⏭️ {skip_count} 跳过  ❌ {fail_count} 失败")
    if results:
        print(f"   📁 输出: {OUTPUT_PATH}  ({len(results)} 个风格)")
    print("=" * 70)

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
