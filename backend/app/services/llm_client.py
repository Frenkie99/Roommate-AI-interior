"""
LLM 客户端 - 智能提示词生成器
用于分析毛坯房图片并生成专业级定制化装修提示词
"""

import os
import httpx
import base64
from typing import Optional, Dict, Any, List
from enum import Enum
import json

from app.utils.prompt_builder import GLOBAL_STRUCTURE_CONSTRAINTS, STYLE_PROMPTS, build_prompt_v3


class LLMModel(str, Enum):
    """支持的 LLM 模型列表（API易平台，2026-07 更新）"""
    # Gemini 图像模型 — 支持 image→text 和 text→text（API易上唯一可用系列）
    GEMINI_25_FLASH_IMAGE = "gemini-2.5-flash-image"          # 首选：快速、便宜
    GEMINI_3_PRO_IMAGE_PREVIEW = "gemini-3-pro-image-preview" # 备选：质量更高
    # 已下线: gemini-3-flash-preview, gemini-2.5-flash-preview, deepseek-chat, deepseek-v3


class LLMClient:
    """LLM 客户端 - API易平台"""

    def __init__(self):
        self.BASE_URL = "https://api.apiyi.com"
        self._client = None
        self._api_key = None

    @property
    def client(self):
        """懒初始化 httpx client，reload 后自动重建"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client
    
    @property
    def api_key(self) -> str:
        """动态获取 API Key - 优先用 CHAT_APIYI_KEY (DeepSeek)，备选 LLM_APIYI_KEY"""
        if self._api_key is None:
            self._api_key = os.getenv("CHAT_APIYI_KEY") or os.getenv("LLM_APIYI_KEY")
        return self._api_key
    
    def image_to_base64(self, image_data: bytes) -> str:
        """将图片数据转换为 base64"""
        return base64.b64encode(image_data).decode("utf-8")
    
    # 视觉模型降级顺序（3 Pro 优先，质量更高）
    _VISION_MODEL_PRIORITY = [
        LLMModel.GEMINI_3_PRO_IMAGE_PREVIEW,
        LLMModel.GEMINI_25_FLASH_IMAGE,
    ]

    async def analyze_room_and_generate_prompt(
        self,
        image_data: bytes,
        style: str,
        room_type: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        model: LLMModel = LLMModel.GEMINI_3_PRO_IMAGE_PREVIEW
    ) -> Dict[str, Any]:
        """
        分析毛坯房图片并生成定制化装修提示词

        自动降级：先尝试 Gemini 视觉模型（支持图片输入），
        失败后降级到 DeepSeek 纯文本模型（仅基于风格/类型推测）。

        Args:
            image_data: 毛坯房图片数据
            style: 装修风格
            room_type: 房间类型
            custom_prompt: 用户自定义需求
            model: LLM 模型

        Returns:
            包含分析结果和生成提示词的字典
        """
        # --- 尝试 Gemini 视觉模型 ---
        analysis_prompt = self._build_analysis_prompt(style, room_type, custom_prompt)
        image_base64 = self.image_to_base64(image_data)

        for vision_model in self._VISION_MODEL_PRIORITY:
            try:
                payload = {
                    "contents": [{
                        "parts": [
                            {"inlineData": {"mimeType": "image/jpeg", "data": image_base64}},
                            {"text": analysis_prompt}
                        ]
                    }],
                    "generationConfig": {
                        "responseModalities": ["TEXT"],
                        "temperature": 0.7,
                        "maxOutputTokens": 2048
                    }
                }
                model_name = vision_model.value if hasattr(vision_model, 'value') else str(vision_model)
                api_url = f"{self.BASE_URL}/v1beta/models/{model_name}:generateContent"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                response = await self.client.post(api_url, headers=headers, json=payload)
                response.raise_for_status()

                result = response.json()
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = self._parse_llm_response(content, style, room_type, custom_prompt)
                    if parsed.get("code") == 0 and isinstance(parsed.get("data"), dict):
                        parsed["data"]["vision_used"] = True  # 视觉识别真实成功（trace 埋点用）
                    return parsed
            except Exception as e:
                print(f"[LLM] Gemini 视觉模型 {vision_model} 失败: {e}, 尝试下一个...")
                continue

        # --- 降级：纯文本分析（不需要图片，使用 Gemini 图像模型做纯文本） ---
        print("[LLM] 所有 Gemini 视觉模型不可用，降级到纯文本分析")
        try:
            text_prompt = self._build_text_only_prompt(style, room_type, custom_prompt)
            text_result = await self.chat_text(
                prompt=text_prompt,
                model=LLMModel.GEMINI_25_FLASH_IMAGE,
                system_prompt="You are a professional interior designer. Analyze spaces and generate design prompts.",
                max_tokens=2048
            )
            parsed = self._parse_llm_response(text_result, style, room_type, custom_prompt)
            if parsed.get("code") == 0 and isinstance(parsed.get("data"), dict):
                parsed["data"]["vision_used"] = False  # 降级到纯文本（trace 埋点用）
            return parsed
        except Exception as e:
            return {
                "code": -1,
                "message": f"LLM 分析异常（含降级）: {str(e)}",
                "data": None
            }
    
    def _build_analysis_prompt(
        self,
        style: str,
        room_type: Optional[str],
        custom_prompt: Optional[str]
    ) -> str:
        """构建图片分析提示词 - 专注于视觉识别和设计意图提取"""
        
        # 获取风格信息
        style_info = STYLE_PROMPTS.get(style, {})
        style_name = style_info.get("name", style)
        
        prompt = f"""You are a professional interior designer. Analyze this raw room image.

Your task is to identify PHYSICAL FACTS about the space, NOT to generate rendering prompts.

## Analysis Requirements:
1. Identify the room type (is it a {room_type or 'unknown room'}?)
2. Describe window positions, ceiling height, and floor material
3. Based on {style_name} style, suggest specific furniture placement and color nodes
4. How to incorporate user requirements: "{custom_prompt or 'none'}" into this specific space

## Output Format (Strict JSON):
{{
    "room_analysis": {{
        "room_type": "identified room type",
        "space_description": "physical space characteristics",
        "physical_features": "window positions, ceiling height, floor material",
        "lighting_analysis": "natural light direction and quality"
    }},
    "design_recommendations": {{
        "layout_suggestion": "furniture layout based on space constraints",
        "furniture_placement": "specific placement recommendations",
        "color_scheme": "color palette suggestions for {style_name}",
        "lighting_design": "artificial lighting recommendations"
    }}
}}

IMPORTANT: Focus on FACTS about the space. Do NOT include structural modification suggestions.
Output a single valid JSON object."""
        
        return prompt

    def _build_text_only_prompt(
        self,
        style: str,
        room_type: Optional[str],
        custom_prompt: Optional[str]
    ) -> str:
        """构建纯文本分析提示词（DeepSeek 降级用，不依赖图片）"""
        style_info = STYLE_PROMPTS.get(style, {})
        style_name = style_info.get("name", style)
        style_desc = style_info.get("prompt", "")

        return f"""You are a professional interior designer. Generate design recommendations for a raw room.

## Context:
- Target style: {style_name}
- Room type: {room_type or 'general room'}
- User requirements: "{custom_prompt or 'none'}"
- Style reference: {style_desc[:200]}

## Output Format (Strict JSON):
{{
    "room_analysis": {{
        "room_type": "{room_type or 'general room'}",
        "space_description": "typical {room_type or 'room'} space characteristics",
        "physical_features": "standard ceiling height, typical window layout",
        "lighting_analysis": "natural and artificial lighting plan"
    }},
    "design_recommendations": {{
        "layout_suggestion": "furniture layout for {style_name} style",
        "furniture_placement": "specific {style_name} furniture pieces and positions",
        "color_scheme": "{style_name} color palette",
        "lighting_design": "ambient, task, and accent lighting for {style_name}"
    }}
}}

IMPORTANT: Output a single valid JSON object only."""

    def _extract_first_json_block(self, text: str) -> Optional[str]:
        """使用 stack-based 平衡括号匹配提取第一个完整的 JSON 块"""
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i+1]
        return None

    def _parse_llm_response(
        self,
        content: str,
        style: str,
        room_type: Optional[str],
        custom_prompt: Optional[str]
    ) -> Dict[str, Any]:
        """解析 LLM 响应并使用 build_prompt_v2 构建最终提示词"""

        try:
            # 尝试解析 JSON（开启 JSON Mode 后应该直接是 JSON）
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif content.strip().startswith("{"):
                json_str = content.strip()
            else:
                # 使用 stack-based 匹配提取第一个完整的 JSON 块
                json_str = self._extract_first_json_block(content)
                if not json_str:
                    raise ValueError("无法在响应中找到有效的 JSON 块")

            analysis_data = json.loads(json_str)
            
            # 使用 build_prompt_v3 构建指令式提示词
            enhanced_prompt = build_prompt_v3(
                style=style,
                room_type=room_type,
                llm_analysis=analysis_data,
                custom_prompt=custom_prompt,
                preserve_structure=True
            )
            
            return {
                "code": 0,
                "message": "LLM 分析成功",
                "data": {
                    "analysis": analysis_data,
                    "enhanced_prompt": enhanced_prompt,
                    "original_style": style,
                    "room_type": room_type,
                    "custom_prompt": custom_prompt
                }
            }
            
        except json.JSONDecodeError as e:
            # JSON 解析失败，使用 v3 指令式提示词作为备用
            from app.utils.prompt_builder import build_prompt_v3
            fallback_prompt = build_prompt_v3(style, room_type, custom_prompt=custom_prompt)
            
            return {
                "code": 0,
                "message": "LLM 分析成功（JSON解析失败，使用静态提示词）",
                "data": {
                    "analysis": {"raw_response": content[:500]},
                    "enhanced_prompt": fallback_prompt,
                    "original_style": style,
                    "room_type": room_type,
                    "custom_prompt": custom_prompt
                }
            }
        except Exception as e:
            return {
                "code": -1,
                "message": f"响应解析失败: {str(e)}",
                "data": None
            }
    
    # chat_text 自动降级模型列表（API易仅 Gemini 图像模型可用）
    _TEXT_MODEL_FALLBACK = [
        ("gemini", LLMModel.GEMINI_25_FLASH_IMAGE),
        ("gemini", LLMModel.GEMINI_3_PRO_IMAGE_PREVIEW),
    ]

    async def chat_text(
        self,
        prompt: str,
        model: LLMModel = LLMModel.GEMINI_25_FLASH_IMAGE,
        system_prompt: str = "You are a professional interior design consultant.",
        max_tokens: int = 2048
    ) -> str:
        """
        纯文本对话（用于RAG问答）- 自动降级

        依次尝试: gemini-2.5-flash-image → gemini-3-pro-image-preview

        Returns:
            AI生成的文本回复
        """
        last_error = None
        for fmt, m in self._TEXT_MODEL_FALLBACK:
            try:
                if fmt == "deepseek":
                    return await self._chat_deepseek(prompt, m, system_prompt, max_tokens)
                else:
                    return await self._chat_gemini(prompt, m, system_prompt, max_tokens)
            except Exception as e:
                print(f"[LLM] chat_text {m} 失败: {e}, 尝试下一个...")
                last_error = e
        raise Exception(f"所有文本模型都不可用: {last_error}")

    async def _chat_deepseek(self, prompt: str, model, system_prompt: str, max_tokens: int) -> str:
        """DeepSeek OpenAI 兼容格式"""
        payload = {
            "model": model.value if hasattr(model, 'value') else str(model),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens
        }
        api_url = f"{self.BASE_URL}/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        response = await self.client.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"]
        raise ValueError("DeepSeek 响应格式错误：缺少 choices")

    async def _chat_gemini(self, prompt: str, model, system_prompt: str, max_tokens: int) -> str:
        """Gemini 原生格式（也适用于图像模型的文本模式）"""
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "responseModalities": ["TEXT"],
                "responseMimeType": "text/plain",
                "temperature": 0.7,
                "maxOutputTokens": max_tokens
            }
        }
        model_name = model.value if hasattr(model, 'value') else str(model)
        api_url = f"{self.BASE_URL}/v1beta/models/{model_name}:generateContent"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        response = await self.client.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if "candidates" in result and len(result["candidates"]) > 0:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        raise ValueError("Gemini 响应格式错误：缺少 candidates")

    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()


# 模型优先级配置（仅 Gemini 图像模型可用）
DEFAULT_LLM_MODEL_PRIORITY = [
    LLMModel.GEMINI_25_FLASH_IMAGE,
    LLMModel.GEMINI_3_PRO_IMAGE_PREVIEW,
]

# 全局客户端实例
llm_client = LLMClient()
