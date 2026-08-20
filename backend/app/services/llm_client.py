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

from app.utils.prompt_builder import (
    GLOBAL_STRUCTURE_CONSTRAINTS,
    STYLE_PROMPTS,
    build_prompt_v2,
    normalize_llm_analysis,
)


class LLMModel(str, Enum):
    """支持的 LLM 模型列表（API易平台，2026-07 更新）"""
    # Gemini 图像模型 — 支持 image→text 和 text→text（API易上唯一可用系列）
    GEMINI_25_FLASH_IMAGE = "gemini-2.5-flash-image"          # 首选：快速、便宜
    GEMINI_3_PRO_IMAGE_PREVIEW = "gemini-3-pro-image-preview" # 备选：质量更高
    # 已下线: gemini-3-flash-preview, gemini-2.5-flash-preview, deepseek-chat, deepseek-v3


def _get_llm_providers() -> List[Dict[str, str]]:
    """Load LLM providers: custom first, API易 last."""
    providers = []
    for i in range(1, 11):
        url = os.getenv(f"CUSTOM_API_{i}_URL")
        key = os.getenv(f"CUSTOM_API_{i}_KEY")
        if not url or not key:
            continue
        providers.append({"name": os.getenv(f"CUSTOM_API_{i}_NAME", f"custom_{i}"), "url": url.rstrip("/"), "key": key})
    # API易 as last resort
    apiyi_key = os.getenv("CHAT_APIYI_KEY") or os.getenv("LLM_APIYI_KEY")
    if apiyi_key:
        providers.append({"name": "apiyi", "url": "https://api.apiyi.com", "key": apiyi_key})
    return providers


class LLMClient:
    """LLM 客户端 — 多供应商自动降级"""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    def image_to_base64(self, image_data: bytes) -> str:
        return base64.b64encode(image_data).decode("utf-8")

    _VISION_MODEL_PRIORITY = [
        LLMModel.GEMINI_3_PRO_IMAGE_PREVIEW,
        LLMModel.GEMINI_25_FLASH_IMAGE,
    ]

    async def _try_vision_request(
        self, provider: dict, model, payload: dict
    ) -> Optional[str]:
        """Try a single vision API call on one provider. Returns text or None."""
        model_name = model.value if hasattr(model, 'value') else str(model)
        api_url = f"{provider['url']}/v1beta/models/{model_name}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {provider['key']}"
        }
        response = await self.client.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if "candidates" in result and len(result["candidates"]) > 0:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        return None

    async def analyze_room_and_generate_prompt(
        self,
        image_data: bytes,
        style: str,
        room_type: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        model: LLMModel = LLMModel.GEMINI_3_PRO_IMAGE_PREVIEW
    ) -> Dict[str, Any]:
        """Analyze room image and generate design prompt — multi-provider fallback."""
        analysis_prompt = self._build_analysis_prompt(style, room_type, custom_prompt)
        image_base64 = self.image_to_base64(image_data)

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

        # --- Tier 1: Vision analysis across all providers ---
        providers = _get_llm_providers()
        for provider in providers:
            for vision_model in self._VISION_MODEL_PRIORITY:
                try:
                    print(f"[LLM] Vision: {provider['name']} / {vision_model}")
                    content = await self._try_vision_request(provider, vision_model, payload)
                    if content:
                        parsed = self._parse_llm_response(content, style, room_type, custom_prompt)
                        if parsed.get("code") == 0 and isinstance(parsed.get("data"), dict):
                            parsed["data"]["vision_used"] = True
                        return parsed
                except Exception as e:
                    print(f"[LLM] Vision {provider['name']}/{vision_model} failed: {e}")
                    continue

        # --- Tier 2: Text-only analysis across all providers ---
        print("[LLM] All vision models exhausted, falling back to text-only analysis")
        text_prompt = self._build_text_only_prompt(style, room_type, custom_prompt)
        for provider in providers:
            try:
                print(f"[LLM] Text: {provider['name']}")
                text_result = await self._chat_with_provider(
                    provider, text_prompt,
                    system_prompt="You are a professional interior designer. Analyze spaces and generate design prompts.",
                    max_tokens=2048
                )
                parsed = self._parse_llm_response(text_result, style, room_type, custom_prompt)
                if parsed.get("code") == 0 and isinstance(parsed.get("data"), dict):
                    parsed["data"]["vision_used"] = False
                return parsed
            except Exception as e:
                print(f"[LLM] Text {provider['name']} failed: {e}")
                continue

        return {
            "code": -1,
            "message": "LLM analysis failed across all providers",
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

            raw_analysis = json.loads(json_str)
            analysis_data, analysis_valid = normalize_llm_analysis(raw_analysis)
            if not analysis_valid:
                raise ValueError("LLM 分析缺少有效的空间分析字段")

            print(
                "[LLM] analysis_valid=true "
                f"room_fields={list(analysis_data['room_analysis'].keys())} "
                f"design_fields={list(analysis_data['design_recommendations'].keys())}"
            )

            # 使用 build_prompt_v2 构建最终提示词
            enhanced_prompt = build_prompt_v2(
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
                    "analysis_valid": True,
                    "fallback_reason": "",
                    "enhanced_prompt": enhanced_prompt,
                    "original_style": style,
                    "room_type": room_type,
                    "custom_prompt": custom_prompt
                }
            }
            
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            # JSON 解析或结构校验失败，使用静态提示词作为备用
            fallback_prompt = build_prompt_v2(style, room_type, custom_prompt=custom_prompt)
            fallback_reason = (
                "json_parse_error"
                if isinstance(e, json.JSONDecodeError)
                else "invalid_analysis_structure"
            )
            print(f"[LLM] analysis_valid=false fallback_reason={fallback_reason}")
            
            return {
                "code": 0,
                "message": "LLM 响应不可用，已使用静态提示词",
                "data": {
                    "analysis": {"raw_response": content[:500]},
                    "analysis_valid": False,
                    "fallback_reason": fallback_reason,
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
    
    async def _chat_with_provider(
        self, provider: dict, prompt: str,
        system_prompt: str = "", max_tokens: int = 2048
    ) -> str:
        """Send a text request to a specific provider using Gemini native format."""
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT"],
                "responseMimeType": "text/plain",
                "temperature": 0.7,
                "maxOutputTokens": max_tokens
            }
        }
        # Use first available model for text
        model_name = "gemini-2.5-flash-image"
        api_url = f"{provider['url']}/v1beta/models/{model_name}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {provider['key']}"
        }
        response = await self.client.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        if "candidates" in result and len(result["candidates"]) > 0:
            return result["candidates"][0]["content"]["parts"][0]["text"]
        raise ValueError(f"Empty response from {provider['name']}")

    async def chat_text(
        self,
        prompt: str,
        model: LLMModel = LLMModel.GEMINI_25_FLASH_IMAGE,
        system_prompt: str = "You are a professional interior design consultant.",
        max_tokens: int = 2048
    ) -> str:
        """Pure text chat — multi-provider fallback."""
        last_error = None
        for provider in _get_llm_providers():
            try:
                return await self._chat_with_provider(provider, prompt, system_prompt, max_tokens)
            except Exception as e:
                print(f"[LLM] chat_text {provider['name']} failed: {e}")
                last_error = e
        raise Exception(f"All text providers exhausted: {last_error}")

    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()


# 全局客户端实例
llm_client = LLMClient()
