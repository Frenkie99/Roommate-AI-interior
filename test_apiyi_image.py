"""
测试 API易 图生图功能
"""
import httpx
import asyncio
import base64

API_KEY = "sk-5Cd5C9UJNSYfblvr375057376f6746Eb9b3818D27b3e00A3"
BASE_URL = "https://api.apiyi.com"
MODEL = "gemini-2.5-flash-image"

# 测试图片路径
TEST_IMAGE = r"C:\Users\youda\AppData\Local\Temp\taskpool-mcp-images\image_1769052558494_9c0i4.png"

async def test_image_to_image():
    """测试图生图"""
    url = f"{BASE_URL}/v1beta/models/{MODEL}:generateContent"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    # 读取并编码图片
    with open(TEST_IMAGE, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")
    
    payload = {
        "contents": [{
            "parts": [
                {
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": image_base64
                    }
                },
                {
                    "text": "Transform this unfinished room into a modern minimalist living room with white walls, wooden floor, and elegant furniture. Keep the window position and structure unchanged."
                }
            ]
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": "4:3",
                "imageSize": "2K"
            }
        }
    }
    
    print(f"URL: {url}")
    print(f"Testing image-to-image with: {TEST_IMAGE}")
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"\nStatus: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if "inlineData" in part:
                            print("SUCCESS! Image generated.")
                            # 保存图片
                            img_data = base64.b64decode(part["inlineData"]["data"])
                            with open("test_output.png", "wb") as f:
                                f.write(img_data)
                            print("Saved to test_output.png")
                            return
                print("No image in response")
            else:
                print(f"Response: {response.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_image_to_image())
