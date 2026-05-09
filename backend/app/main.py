"""
AI 毛坯房精装修效果图生成器 - 主入口
"""

import os
import warnings
from pathlib import Path

from PIL import Image

# 防御 PIL 解压炸弹：限制单图最大像素数，超出阈值的解码会抛异常而非警告
# 16M 像素 ≈ 4096x4096，足够覆盖所有常规室内照片
Image.MAX_IMAGE_PIXELS = 16 * 1024 * 1024
warnings.simplefilter("error", Image.DecompressionBombWarning)


def load_env_file(env_path: Path) -> bool:
    """手动加载.env文件，确保兼容性"""
    if not env_path.exists():
        return False
    try:
        # 使用utf-8-sig自动处理BOM
        with open(env_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ[key] = value
        return True
    except Exception as e:
        print(f"[ERROR] Failed to load .env: {e}")
        return False

# 加载环境变量 - 使用可靠的手动加载方式
env_path = Path(__file__).parent.parent / ".env"
if load_env_file(env_path):
    print(f"[INFO] Environment loaded from: {env_path}")
else:
    print(f"[WARN] .env not found at: {env_path}")

# 验证关键环境变量（仅记录是否配置，永远不打印任何 key 内容/前缀以防日志泄漏）
print(f"[INFO] APIYI_KEY: {'configured' if os.getenv('APIYI_KEY') else 'NOT SET'}")
print(f"[INFO] LLM_APIYI_KEY: {'configured' if os.getenv('LLM_APIYI_KEY') else 'NOT SET'}")

# LLM 功能开关
use_llm = os.getenv('USE_LLM_PROMPT', 'true')
print(f"[INFO] LLM 智能提示词: {'启用' if use_llm.lower() == 'true' else '禁用'}")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import image
from app.routes import segment
from app.routes import knowledge

# 输出目录
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 在生产环境关闭 /docs、/redoc、/openapi.json，避免对外暴露完整 API map
# 通过 ENABLE_API_DOCS=true 在开发环境开启；不设或非 true 则关闭
_docs_enabled = os.getenv("ENABLE_API_DOCS", "false").lower() == "true"

app = FastAPI(
    title="AI 装修效果图生成器",
    description="基于 API易平台 的智能装修效果图生成服务",
    version="1.0.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# CORS 配置 - 允许所有来源（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(image.router, prefix="/api/v1", tags=["image"])
app.include_router(segment.router, tags=["segment"])
app.include_router(knowledge.router, tags=["knowledge"])

# 静态文件服务 - 用于访问生成的图片
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")


@app.get("/")
async def root():
    return {"message": "AI 装修效果图生成器 API 服务已启动"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
