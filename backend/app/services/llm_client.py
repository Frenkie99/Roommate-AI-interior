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

from app.utils.prompt_builder import GLOBAL_STRUCTURE_CONSTRAINTS, STYLE_PROMPTS, build_prompt_v2


class LLMModel(str, Enum):
    """支持的 LLM 模型列表"""
    # DeepSeek 模型（OpenAI 兼容格式）
    DEEPSEEK_CHAT = "deepseek-chat"
    DEEPSEEK_V3 = "deepseek-v3"
    # Gemini 模型（Gemini 格式）
    GEMINI_3_FLASH_PREVIEW = "gemini-3-flash-preview"
    GEMINI_25_FLASH_PREVIEW = "gemini-2.5-flash-preview"


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
        """动态获取 API Key"""
        if self._api_key is None:
            self._api_key = os.getenv("LLM_APIYI_KEY")
        return self._api_key
    
    def image_to_base64(self, image_data: bytes) -> str:
        """将图片数据转换为 base64"""
        return base64.b64encode(image_data).decode("utf-8")
    
    async def analyze_room_and_generate_prompt(
        self,
        image_data: bytes,
        style: str,
        room_type: Optional[str] = None,
        custom_prompt: Optional[str] = None,
        model: LLMModel = LLMModel.GEMINI_3_FLASH_PREVIEW
    ) -> Dict[str, Any]:
        """
        分析毛坯房图片并生成定制化装修提示词
        
        Args:
            image_data: 毛坯房图片数据
            style: 装修风格
            room_type: 房间类型
            custom_prompt: 用户自定义需求
            model: LLM 模型
            
        Returns:
            包含分析结果和生成提示词的字典
        """
        # 构建分析提示词
        analysis_prompt = self._build_analysis_prompt(style, room_type, custom_prompt)
        
        # 准备请求数据
        image_base64 = self.image_to_base64(image_data)
        
        payload = {
            "contents": [{
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": image_base64
                        }
                    },
                    {
                        "text": analysis_prompt
                    }
                ]
            }],
            "generationConfig": {
                "responseModalities": ["TEXT"],
                "responseMimeType": "application/json",
                "temperature": 0.7,
                "maxOutputTokens": 2048
            }
        }
        
        # API URL
        model_name = model.value if hasattr(model, 'value') else str(model)
        api_url = f"{self.BASE_URL}/v1beta/models/{model_name}:generateContent"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            response = await self.client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # 解析响应
            if "candidates" in result and len(result["candidates"]) > 0:
                content = result["candidates"][0]["content"]["parts"][0]["text"]
                
                # 提取结构化信息
                return self._parse_llm_response(content, style, room_type, custom_prompt)
            else:
                return {
                    "code": -1,
                    "message": "未获取到 LLM 响应",
                    "data": None
                }
                
        except httpx.HTTPStatusError as e:
            return {
                "code": e.response.status_code,
                "message": f"LLM API 请求失败: {e.response.text}",
                "data": None
            }
        except Exception as e:
            return {
                "code": -1,
                "message": f"LLM 分析异常: {str(e)}",
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
            
            # 使用 build_prompt_v2 构建最终提示词（统一架构）
            enhanced_prompt = build_prompt_v2(
                style=style,
                room_type=room_type,
                llm_analysis=analysis_data,
                custom_prompt=custom_prompt,
                preserve_structure=True  # 结构约束默认开启
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
            # JSON 解析失败，使用静态提示词作为备用
            from app.utils.prompt_builder import build_prompt
            fallback_prompt = build_prompt(style, room_type, custom_prompt)
            
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
    
    async def chat_text(
        self,
        prompt: str,
        model: LLMModel = LLMModel.DEEPSEEK_CHAT,
        system_prompt: str = "你是专业室内设计顾问。",
        max_tokens: int = 2048
    ) -> str:
        """
        纯文本对话（用于RAG问答）- 支持 OpenAI 兼容格式

        Args:
            prompt: 完整的对话提示词
            model: LLM模型（默认使用 DeepSeek）
            system_prompt: 系统提示词（可自定义）
            max_tokens: 最大输出 token 数

        Returns:
            AI生成的文本回复
        """
        # 判断使用哪种格式
        is_deepseek = model in [LLMModel.DEEPSEEK_CHAT, LLMModel.DEEPSEEK_V3]

        if is_deepseek:
            # DeepSeek 使用 OpenAI 兼容格式
            payload = {
                "model": model.value,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": max_tokens
            }
            api_url = f"{self.BASE_URL}/v1/chat/completions"
        else:
            # Gemini 使用原生格式
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
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

        try:
            response = await self.client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            if is_deepseek:
                # OpenAI 格式响应
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                else:
                    raise ValueError("DeepSeek 响应格式错误：缺少 choices")
            else:
                # Gemini 格式响应
                if "candidates" in result and len(result["candidates"]) > 0:
                    return result["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    raise ValueError("Gemini 响应格式错误：缺少 candidates")
        except httpx.HTTPStatusError as e:
            raise Exception(f"LLM API 请求失败: {e.response.status_code}") from e
        except Exception as e:
            raise Exception(f"LLM 调用失败: {str(e)}") from e

    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()


# 模型优先级配置（DeepSeek 优先）
DEFAULT_LLM_MODEL_PRIORITY = [
    LLMModel.DEEPSEEK_CHAT,
    LLMModel.DEEPSEEK_V3,
    LLMModel.GEMINI_3_FLASH_PREVIEW,
    LLMModel.GEMINI_25_FLASH_PREVIEW,
]

# 全局客户端实例
llm_client = LLMClient()
