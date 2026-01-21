"""
AI 毛坯房精装修效果图生成器 - 主入口
"""

import os
from pathlib import Path

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

# 验证关键环境变量
dmxapi_key = os.getenv('DMXAPI_KEY')
if dmxapi_key:
    print(f"[INFO] DMXAPI Key: {dmxapi_key[:15]}...")
else:
    print("[WARN] DMXAPI_KEY not set!")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routes import image
from app.routes import segment

# 输出目录
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="AI 装修效果图生成器",
    description="基于 Nano Banana Pro API 的智能装修效果图生成服务",
    version="1.0.0"
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

# 静态文件服务 - 用于访问生成的图片
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")


@app.get("/")
async def root():
    return {"message": "AI 装修效果图生成器 API 服务已启动"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
