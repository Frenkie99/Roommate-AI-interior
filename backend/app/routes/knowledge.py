"""
知识库查询路由
提供装修知识问答的API接口
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.services.knowledge_service import knowledge_service
from app.services.llm_client import llm_client

logger = logging.getLogger(__name__)

router = APIRouter()


class KnowledgeQueryRequest(BaseModel):
    """知识库查询请求"""
    question: str
    style: Optional[str] = None
    room_type: Optional[str] = None
    n_results: int = 5


class KnowledgeQueryResponse(BaseModel):
    """知识库查询响应"""
    code: int
    message: str
    data: Optional[dict] = None


@router.post("/api/v1/knowledge/query", response_model=KnowledgeQueryResponse)
async def query_knowledge(request: KnowledgeQueryRequest):
    """
    查询装修知识库并生成智能回答

    Args:
        request: 包含用户问题、可选的风格/房间类型过滤、返回结果数量

    Returns:
        AI生成的专业回答 + 知识来源标注
    """
    try:
        # 1. 从向量库检索相关知识
        rag_result = await knowledge_service.query(
            question=request.question,
            style=request.style,
            room_type=request.room_type,
            n_results=request.n_results
        )

        # 2. 检查知识库是否已初始化
        if not rag_result["relevant_docs"]:
            return KnowledgeQueryResponse(
                code=0,
                message="success",
                data={
                    "answer": rag_result["answer"],
                    "sources": [],
                    "need_init": True
                }
            )

        # 3. 构建RAG提示词
        context = rag_result["context_used"]
        rag_prompt = f"""你是专业室内设计顾问。请基于以下装修知识回答用户问题：

【相关知识库内容】
{context}

【用户问题】
{request.question}

请提供专业、实用的建议。如果知识库内容不足以完全回答问题，可以基于你的专业知识进行补充，但请明确说明哪些是来自知识库的。"""

        # 4. 调用LLM生成回答
        ai_answer = await llm_client.chat_text(rag_prompt)

        # 5. 返回结果
        return KnowledgeQueryResponse(
            code=0,
            message="success",
            data={
                "answer": ai_answer,
                "sources": rag_result["sources"],
                "context_used": context
            }
        )

    except Exception:
        logger.exception("知识库查询失败")
        raise HTTPException(status_code=500, detail="服务器内部错误，请稍后重试")


@router.get("/api/v1/knowledge/health")
async def health_check():
    """知识库服务健康检查"""
    stats = knowledge_service.get_collection_stats()
    return {
        "status": "ok",
        "service": "knowledge_base",
        "stats": stats
    }


@router.get("/api/v1/knowledge/stats")
async def get_stats():
    """获取知识库统计信息"""
    stats = knowledge_service.get_collection_stats()
    return {
        "code": 0,
        "message": "success",
        "data": stats
    }


class ResetRequest(BaseModel):
    """重置知识库请求"""
    confirm: bool  # 需要确认以防止误操作


@router.post("/api/v1/knowledge/reset")
async def reset_knowledge_base(request: ResetRequest):
    """
    重置知识库（清空所有数据）

    注意：此操作不可逆，请谨慎使用
    """
    if not request.confirm:
        return {
            "code": -1,
            "message": "需要确认操作（设置confirm=true）"
        }

    success = knowledge_service.reset_collection()
    if success:
        return {
            "code": 0,
            "message": "知识库已重置",
            "data": {"note": "请重新运行初始化脚本添加知识"}
        }
    else:
        raise HTTPException(status_code=500, detail="重置失败")
