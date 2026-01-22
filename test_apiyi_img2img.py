"""
测试 API易 图生图功能
使用服务器上的 input 目录中的图片
"""
import httpx
import asyncio
import base64
import os

API_KEY = "sk-5Cd5C9UJNSYfblvr375057376f6746Eb9b3818D27b3e00A3"
BASE_URL = "https://api.apiyi.com"
MODEL = "gemini-2.5-flash-image"

async def test_img2img():
    # 查找 input 目录中的任意图片
    input_dir = "/var/www/roommate/input"
    test_image = None
    
    if os.path.exists(input_dir):
        for f in os.listdir(input_dir):
            if f.endswith(('.jpg', '.jpeg', '.png')):
                test_image = os.path.join(input_dir, f)
                break
    
    if not test_image:
        print("No test image found in /var/www/roommate/input")
        print("Testing text-to-image instead...")
        # 退回到文生图测试
        payload = {
            "contents": [{"parts": [{"text": "A modern living room"}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": "4:3", "imageSize": "1K"}
            }
        }
    else:
        print(f"Using test image: {test_image}")
        with open(test_image, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
        
        payload = {
            "contents": [{
                "parts": [
                    {"inlineData": {"mimeType": "image/jpeg", "data": image_base64}},
                    {"text": "Transform this room into a modern minimalist style"}
                ]
            }],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": "4:3", "imageSize": "1K"}
            }
        }
    
    url = f"{BASE_URL}/v1beta/models/{MODEL}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    print(f"Testing API: {url}")
    print(f"Model: {MODEL}")
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("SUCCESS!")
            else:
                print(f"Error: {response.text[:800]}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_img2img())
