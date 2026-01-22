"""
简单测试 API易 文生图（无需本地图片）
"""
import httpx
import asyncio

API_KEY = "sk-5Cd5C9UJNSYfblvr375057376f6746Eb9b3818D27b3e00A3"
BASE_URL = "https://api.apiyi.com"
MODEL = "gemini-2.5-flash-image"

async def test_text_to_image():
    url = f"{BASE_URL}/v1beta/models/{MODEL}:generateContent"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "contents": [{
            "parts": [{"text": "A modern minimalist living room"}]
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": "4:3", "imageSize": "1K"}
        }
    }
    
    print(f"Testing API: {url}")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("SUCCESS!")
            else:
                print(f"Error: {response.text[:500]}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_text_to_image())
