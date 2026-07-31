"""
室内设计 Agent 路由
统一承接聊天输入，并把生成、知识问答、局部精修交给现有工具链。
"""

import json
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.routes.image import generate_renovation_image
from app.routes.knowledge import KnowledgeQueryRequest, query_knowledge
from app.routes.segment import inpaint_region
from app.services.design_agent import DesignAgent


router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


def _parse_json(value: str, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _json_response_data(response: JSONResponse) -> dict:
    return json.loads(response.body.decode("utf-8"))


@router.post("/chat")
async def agent_chat(
    message: str = Form(...),
    context: str = Form("{}"),
    history: str = Form("[]"),
    upload_image: Optional[UploadFile] = File(None),
    current_image: Optional[UploadFile] = File(None),
    mask_base64: Optional[str] = Form(None),
):
    """
    Agent 对话入口。

    前端仍负责精修模式框选和分割；本接口只根据上下文选择工具。
    """
    context_data = _parse_json(context, {})
    history_data = _parse_json(history, [])

    async def knowledge_tool(message: str, context: dict, history: list) -> dict:
        response = await query_knowledge(KnowledgeQueryRequest(
            question=message,
            style=context.get("style"),
            room_type=context.get("room_type"),
            n_results=5,
        ))
        data = response.data or {}
        if data.get("answer") is None:
            data["answer"] = "知识库暂无相关资料，AI 回答服务也遇到了问题。请稍后再试或换个问法。"
        return data

    async def generate_tool(prompt: str, context: dict) -> dict:
        if not upload_image:
            return {"error": "missing_upload_image"}

        response = await generate_renovation_image(
            image=upload_image,
            style=context.get("style") or "aman_style",
            room_type=context.get("room_type"),
            custom_prompt=prompt,
            aspect_ratio="auto",
            image_size="1K",
        )
        body = _json_response_data(response)
        if body.get("code") != 0:
            return {"error": body.get("message") or "generate_failed"}
        return body.get("data") or {}

    async def refine_tool(prompt: str, context: dict) -> dict:
        if not current_image or not mask_base64:
            return {"error": "missing_refine_inputs"}

        response = await inpaint_region(
            image=current_image,
            mask_base64=mask_base64,
            prompt=prompt,
            negative_prompt=None,
            strength=0.85,
        )
        body = _json_response_data(response)
        if body.get("code") != 0:
            return {"error": body.get("message") or "refine_failed"}
        return body.get("data") or {}

    agent = DesignAgent(
        knowledge_tool=knowledge_tool,
        generate_tool=generate_tool,
        refine_tool=refine_tool,
    )
    result = await agent.handle_chat(message=message, context=context_data, history=history_data)

    return JSONResponse({
        "code": 0,
        "message": "success",
        "data": result,
    })
