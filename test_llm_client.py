"""
测试 LLM 智能提示词生成功能
"""
import httpx
import asyncio
import base64
import os

# 设置环境变量
os.environ["LLM_APIYI_KEY"] = "sk-x4iJS9s8HuVz5aUF6d78B49b66Cd4aE8B3014128F1562937"

API_KEY = "sk-x4iJS9s8HuVz5aUF6d78B49b66Cd4aE8B3014128F1562937"
BASE_URL = "https://api.apiyi.com"
MODEL = "gemini-3-flash-preview"

async def test_llm_analysis():
    """测试 LLM 分析功能"""
    
    # 使用一个简单的测试图片（如果有的话）
    test_image_path = None
    
    # 查找测试图片
    possible_paths = [
        "input",
        "test_images",
        "."
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            for f in os.listdir(path):
                if f.endswith(('.jpg', '.jpeg', '.png')):
                    test_image_path = os.path.join(path, f)
                    break
        if test_image_path:
            break
    
    if not test_image_path:
        print("未找到测试图片，使用纯文本测试")
        # 纯文本测试
        payload = {
            "contents": [{
                "parts": [{
                    "text": "请分析一个典型的毛坯房客厅空间，并给出现代简约风格的装修建议。输出 JSON 格式。"
                }]
            }],
            "generationConfig": {
                "responseModalities": ["TEXT"],
                "temperature": 0.7,
                "maxOutputTokens": 2048
            }
        }
    else:
        print(f"使用测试图片: {test_image_path}")
        with open(test_image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
        
        analysis_prompt = """你是一位专业的室内设计师。请分析这张毛坯房图片，并生成装修设计建议。

输出格式（JSON）：
{
    "room_analysis": {
        "room_type": "识别出的房间类型",
        "space_description": "空间特征描述",
        "lighting_analysis": "采光分析"
    },
    "design_recommendations": {
        "layout_suggestion": "布局建议",
        "furniture_placement": "家具摆放建议"
    }
}

请开始分析："""
        
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
    
    url = f"{BASE_URL}/v1beta/models/{MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    print(f"Testing LLM API: {url}")
    print(f"Model: {MODEL}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0]["content"]["parts"][0]["text"]
                    print("\n=== LLM 分析结果 ===")
                    print(content[:1500])
                    print("\n=== SUCCESS ===")
                else:
                    print("未获取到响应内容")
                    print(result)
            else:
                print(f"Error: {response.text[:500]}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm_analysis())
