"""
室内设计对话 Agent

只负责理解用户意图和选择工具，不接管前端精修模式的框选交互。
"""

from typing import Awaitable, Callable, Optional


AgentTool = Callable[..., Awaitable[dict]]


DESIGN_ACTION_WORDS = (
    "换", "调整", "改成", "改为", "变成", "生成", "设计", "增加", "减少",
    "去掉", "移除", "删除", "加", "做", "来一", "配", "摆", "放",
)

QUESTION_WORDS = (
    "什么", "如何", "怎么", "为什么", "建议", "推荐", "哪些", "区别",
    "优缺点", "怎么样", "好不好", "注意", "预算", "适合", "选择", "吗", "呢",
)

LOCAL_OBJECT_WORDS = (
    "沙发", "椅子", "桌", "茶几", "床", "柜", "灯", "窗帘", "地毯",
    "绿植", "植物", "挂画", "墙", "背景墙", "吊灯", "区域", "物体", "家具",
)

LOCAL_POINTER_WORDS = ("把", "将", "这个", "这里", "选中", "局部", "框选", "区域")


class DesignAgent:
    """室内设计助手：根据上下文选择知识问答、整图生成、局部精修或 UI 提示。"""

    def __init__(
        self,
        knowledge_tool: Optional[AgentTool] = None,
        generate_tool: Optional[AgentTool] = None,
        refine_tool: Optional[AgentTool] = None,
    ):
        self.knowledge_tool = knowledge_tool
        self.generate_tool = generate_tool
        self.refine_tool = refine_tool

    async def handle_chat(self, message: str, context: dict, history: Optional[list] = None) -> dict:
        message = (message or "").strip()
        history = history or []

        if not message:
            return self._response("clarify", "请先描述您的设计需求或装修问题。")

        if self._is_question(message):
            return await self._answer_knowledge(message, context, history)

        has_uploaded_image = bool(context.get("has_uploaded_image"))
        has_generated_image = bool(context.get("generated_image"))
        has_selected_mask = bool(context.get("has_selected_mask"))

        if has_selected_mask and has_generated_image:
            return await self._refine_region(message, context, history)

        if self._is_local_edit(message) and has_generated_image:
            return self._response(
                "request_box_selection",
                "请先进入精修模式并框选要修改的区域，我会根据选区进行局部精修。",
                ui_hint="refine",
            )

        if self._is_design_action(message):
            if not has_uploaded_image:
                return self._response("request_upload", "请先上传一张房间照片，我才能为您生成设计方案。")
            return await self._generate_design(message, context, history)

        return await self._answer_knowledge(message, context, history)

    async def _answer_knowledge(self, message: str, context: dict, history: list) -> dict:
        if not self.knowledge_tool:
            return self._response("knowledge_answer", "我暂时无法查询知识库，请稍后再试。")

        result = await self.knowledge_tool(
            message=message,
            context=context,
            history=history,
        )
        answer = result.get("answer") or "我暂时没有找到可靠答案，请换个问法再试。"
        return self._response("knowledge_answer", answer, tool_result=result)

    async def _generate_design(self, message: str, context: dict, history: list) -> dict:
        if not self.generate_tool:
            return self._response("generate_design", "生成工具暂时不可用，请稍后再试。")

        result = await self.generate_tool(
            prompt=self._compose_design_prompt(message, history),
            context=context,
        )
        if result.get("error"):
            return self._response(
                "generate_design",
                f"生成失败：{result['error']}。请稍后重试。",
                tool_result=result,
            )

        output_urls = result.get("output_urls") or []
        state_patch = {}
        if output_urls:
            state_patch["generated_image"] = output_urls[0]
            state_patch["selected_mask"] = None

        return self._response(
            "generate_design",
            "已为您生成新的设计方案，请查看预览区域。",
            state_patch=state_patch,
            tool_result=result,
        )

    async def _refine_region(self, message: str, context: dict, history: list) -> dict:
        if not self.refine_tool:
            return self._response("refine_region", "局部精修工具暂时不可用，请稍后再试。")

        result = await self.refine_tool(
            prompt=self._compose_design_prompt(message, history),
            context=context,
        )
        if result.get("error"):
            return self._response(
                "refine_region",
                f"局部精修失败：{result['error']}。请保留选区后重试。",
                tool_result=result,
            )

        result_image = result.get("result_image")
        state_patch = {"selected_mask": None}
        if result_image:
            state_patch["generated_image"] = result_image

        return self._response(
            "refine_region",
            "局部精修完成。如需继续修改，请重新框选区域或描述新的整体需求。",
            state_patch=state_patch,
            tool_result=result,
        )

    def _compose_design_prompt(self, message: str, history: list) -> str:
        recent_user_messages = [
            item.get("text", "")
            for item in history[-6:]
            if item.get("type") == "user" and item.get("text")
        ]
        if not recent_user_messages:
            return message

        preferences = "；".join(recent_user_messages[-2:])
        return f"{message}\n\n本轮对话中用户此前偏好：{preferences}"

    def _is_question(self, message: str) -> bool:
        return any(word in message for word in QUESTION_WORDS)

    def _is_design_action(self, message: str) -> bool:
        return any(word in message for word in DESIGN_ACTION_WORDS)

    def _is_local_edit(self, message: str) -> bool:
        has_object = any(word in message for word in LOCAL_OBJECT_WORDS)
        has_pointer = any(word in message for word in LOCAL_POINTER_WORDS)
        return has_object and has_pointer and self._is_design_action(message)

    def _response(
        self,
        action: str,
        assistant_message: str,
        state_patch: Optional[dict] = None,
        tool_result: Optional[dict] = None,
        ui_hint: Optional[str] = None,
    ) -> dict:
        response = {
            "action": action,
            "assistant_message": assistant_message,
            "state_patch": state_patch or {},
            "tool_result": tool_result or {},
        }
        if ui_hint:
            response["ui_hint"] = ui_hint
        return response
