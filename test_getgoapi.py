"""
测试 GetGoAPI 连接
"""
import httpx
import asyncio

API_KEY = "sk-slz4gd4sw0WcrJLcqMhyZW0aNatVsVKyy8clTXLKqoWGUM87"
BASE_URL = "https://api.getgoapi.com"
MODEL = "gemini-3-pro-image-preview"

async def test_text_to_image():
    """测试文生图"""
    url = f"{BASE_URL}/v1beta/models/{MODEL}:generateContent"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "contents": [{
            "parts": [{
                "text": "A modern minimalist living room with white walls and wooden floor"
            }]
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": "4:3",
                "imageSize": "2K",
                "numberOfImages": 1
            }
        }
    }
    
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Payload: {payload}")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"\nStatus: {response.status_code}")
            print(f"Response: {response.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_text_to_image())
