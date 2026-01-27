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
    GEMINI_3_FLASH_PREVIEW = "gemini-3-flash-preview"
    GEMINI_25_FLASH_PREVIEW = "gemini-2.5-flash-preview"


class LLMClient:
    """LLM 客户端 - API易平台"""
    
    def __init__(self):
        self.BASE_URL = "https://api.apiyi.com"
        self.client = httpx.AsyncClient(timeout=60.0)
        self._api_key = None
    
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
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            
            analysis_data = json.loads(json_str)
            
            # 使用 build_prompt_v2 构建最终提示词（统一架构）
            enhanced_prompt = build_prompt_v2(
                style=style,
                room_type=room_type,
                llm_analysis=analysis_data,
                custom_prompt=custom_prompt
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
    
    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()


# 模型优先级配置
DEFAULT_LLM_MODEL_PRIORITY = [
    LLMModel.GEMINI_3_FLASH_PREVIEW,
    LLMModel.GEMINI_25_FLASH_PREVIEW,
]

# 全局客户端实例
llm_client = LLMClient()
