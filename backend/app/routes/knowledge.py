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

# RAG 系统提示词
RAG_SYSTEM_PROMPT = """你是一位拥有 15 年经验的资深室内设计师和装修顾问。
你的回答必须基于提供的知识库内容，遵循以下规则：

1. **准确性优先**：只基于【参考知识】中的内容回答。如果知识库内容不足以完整回答问题，明确告知用户"知识库中暂无相关信息"，并给出你的通用建议（标注为"通用建议"）。
2. **引用来源**：在回答中引用知识来源，格式为 [来源: X.Y.Z 小节名称]。例如："防水工程需要做 48 小时闭水试验 [来源: 7.1.1 隐蔽工程验收]"。
3. **量化回答**：涉及价格、尺寸、时间等数值时，必须给出具体数字和单位，不要模糊表述。
4. **结构化输出**：使用 Markdown 格式，包含要点列表、表格（如适用）和分步骤说明。
5. **风险提示**：涉及安全、环保、合同等关键事项时，用"⚠️ 注意"标注风险点。"""


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
    """查询装修知识库并生成智能回答"""
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

        # 3. 构建结构化 RAG 提示词
        context = rag_result["context_used"]
        style_hint = f"用户选择的风格偏好：{request.style}。" if request.style else ""
        room_hint = f"用户关注的房间类型：{request.room_type}。" if request.room_type else ""

        rag_prompt = f"""【参考知识】
{context}

【用户问题】
{request.question}

{style_hint}{room_hint}请基于以上知识库内容，提供专业、实用的回答。"""

        # 4. 调用LLM生成回答
        try:
            ai_answer = await llm_client.chat_text(rag_prompt, system_prompt=RAG_SYSTEM_PROMPT)
        except Exception as llm_error:
            logger.error(f"LLM 调用失败: {llm_error}")
            return KnowledgeQueryResponse(
                code=-1,
                message="AI 回答生成失败，请稍后重试",
                data={
                    "answer": None,
                    "sources": rag_result["sources"],
                    "context_used": context,
                    "error": "llm_failure"
                }
            )

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

    except Exception as e:
        logger.exception(f"知识库查询失败: {e}")
        raise HTTPException(status_code=500, detail=f"知识库查询失败: {str(e)}")


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
