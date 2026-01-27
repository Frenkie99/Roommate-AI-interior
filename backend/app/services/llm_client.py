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
        """构建图片分析提示词"""
        
        prompt = f"""你是一位专业的室内设计师和建筑分析师。请仔细分析这张毛坯房图片，并生成高质量的装修设计提示词。

## 任务要求：
1. **空间分析**：识别房间类型、尺寸比例、窗户位置和采光方向
2. **结构保持**：明确指出必须保留的建筑结构元素
3. **设计建议**：基于 {style} 风格，提供专业的设计方案
4. **布局优化**：推荐合理的家具布局，符合使用习惯

## 输出格式（JSON）：
{{
    "room_analysis": {{
        "room_type": "识别出的房间类型",
        "space_description": "空间特征描述",
        "lighting_analysis": "采光分析",
        "structural_elements": "必须保留的结构元素"
    }},
    "design_recommendations": {{
        "layout_suggestion": "布局建议",
        "furniture_placement": "家具摆放建议",
        "lighting_design": "照明设计建议",
        "color_scheme": "色彩搭配建议"
    }},
    "prompt_enhancement": {{
        "spatial_constraints": "空间约束描述",
        "design_focus": "设计重点",
        "quality_requirements": "质量要求描述",
        "custom_elements": "定制化元素描述"
    }}
}}

## 附加要求：
- 如果用户指定了房间类型 {room_type}，请重点考虑该类型的特点
- 如果有自定义需求 "{custom_prompt}"，请融入设计方案
- 确保设计方案既美观又实用
- 输出必须是有效的 JSON 格式

请开始分析并生成设计方案："""
        
        return prompt
    
    def _parse_llm_response(
        self,
        content: str,
        style: str,
        room_type: Optional[str],
        custom_prompt: Optional[str]
    ) -> Dict[str, Any]:
        """解析 LLM 响应并构建完整提示词"""
        
        try:
            # 尝试解析 JSON
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                # 尝试直接解析
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                json_str = content[json_start:json_end]
            
            analysis_data = json.loads(json_str)
            
            # 构建增强版提示词
            enhanced_prompt = self._build_enhanced_prompt(
                analysis_data, style, room_type, custom_prompt
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
            # JSON 解析失败，使用原始内容
            fallback_prompt = self._build_fallback_prompt(
                content, style, room_type, custom_prompt
            )
            
            return {
                "code": 0,
                "message": "LLM 分析成功（使用备用格式）",
                "data": {
                    "analysis": {"raw_response": content},
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
    
    def _build_enhanced_prompt(
        self,
        analysis: Dict[str, Any],
        style: str,
        room_type: Optional[str],
        custom_prompt: Optional[str]
    ) -> str:
        """基于 LLM 分析构建增强版提示词"""
        
        room_analysis = analysis.get("room_analysis", {})
        design_rec = analysis.get("design_recommendations", {})
        prompt_enh = analysis.get("prompt_enhancement", {})
        
        prompt_parts = []
        
        # 角色与任务
        prompt_parts.append("Act as a professional architectural visualization engine.")
        prompt_parts.append(f"Task: Renovate the provided raw space into a {style} interior.")
        
        # 空间分析结果
        if room_analysis:
            prompt_parts.append("## SPACE ANALYSIS:")
            prompt_parts.append(f"Room type: {room_analysis.get('room_type', 'unknown')}")
            prompt_parts.append(f"Space characteristics: {room_analysis.get('space_description', '')}")
            prompt_parts.append(f"Lighting analysis: {room_analysis.get('lighting_analysis', '')}")
            prompt_parts.append(f"Structural constraints: {room_analysis.get('structural_elements', '')}")
        
        # 设计建议
        if design_rec:
            prompt_parts.append("## DESIGN RECOMMENDATIONS:")
            prompt_parts.append(f"Layout: {design_rec.get('layout_suggestion', '')}")
            prompt_parts.append(f"Furniture placement: {design_rec.get('furniture_placement', '')}")
            prompt_parts.append(f"Lighting design: {design_rec.get('lighting_design', '')}")
            prompt_parts.append(f"Color scheme: {design_rec.get('color_scheme', '')}")
        
        # 增强约束
        if prompt_enh:
            prompt_parts.append("## ENHANCED CONSTRAINTS:")
            prompt_parts.append(f"Spatial constraints: {prompt_enh.get('spatial_constraints', '')}")
            prompt_parts.append(f"Design focus: {prompt_enh.get('design_focus', '')}")
            prompt_parts.append(f"Quality requirements: {prompt_enh.get('quality_requirements', '')}")
            prompt_parts.append(f"Custom elements: {prompt_enh.get('custom_elements', '')}")
        
        # 用户自定义
        if custom_prompt:
            prompt_parts.append(f"## USER REQUIREMENTS:")
            prompt_parts.append(custom_prompt)
        
        # 质量要求
        prompt_parts.append("## QUALITY STANDARDS:")
        prompt_parts.append("photorealistic architecture photography, ultra-detailed textures, highly realistic")
        prompt_parts.append("shot on Canon EOS R5, 16mm f/8, professional architectural composition")
        prompt_parts.append("natural lighting, cinematic lighting, 8k resolution")
        
        return "\n\n".join(prompt_parts)
    
    def _build_fallback_prompt(
        self,
        raw_content: str,
        style: str,
        room_type: Optional[str],
        custom_prompt: Optional[str]
    ) -> str:
        """构建备用提示词（当 JSON 解析失败时）"""
        
        prompt_parts = []
        
        prompt_parts.append("Act as a professional architectural visualization engine.")
        prompt_parts.append(f"Task: Renovate the provided raw space into a {style} interior.")
        
        # LLM 分析内容
        prompt_parts.append("## AI ANALYSIS:")
        prompt_parts.append(raw_content)
        
        # 基础风格信息
        prompt_parts.append(f"## STYLE: {style}")
        if room_type:
            prompt_parts.append(f"## ROOM TYPE: {room_type}")
        if custom_prompt:
            prompt_parts.append(f"## CUSTOM REQUIREMENTS: {custom_prompt}")
        
        # 质量要求
        prompt_parts.append("## QUALITY: photorealistic, 8K, professional architectural photography")
        
        return "\n\n".join(prompt_parts)
    
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
