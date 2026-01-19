"""
AI 毛坯房精装修效果图生成器 - 主入口
"""

import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import image
from app.routes import segment

app = FastAPI(
    title="AI 装修效果图生成器",
    description="基于 Nano Banana Pro API 的智能装修效果图生成服务",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(image.router, prefix="/api/v1", tags=["image"])
app.include_router(segment.router, tags=["segment"])


@app.get("/")
async def root():
    return {"message": "AI 装修效果图生成器 API 服务已启动"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
