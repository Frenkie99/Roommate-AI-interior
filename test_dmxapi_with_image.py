"""
测试 DMXAPI 带参考图片的请求
"""
import requests
import base64

API_KEY = "sk-dyNah1c5HM6bod5dtfjBQPXmDapeFJAsaoPMm8GCPbgIAs9j"
BASE_URL = "https://www.dmxapi.cn"

# 读取测试图片
test_image_path = r"e:\vibe coding projects\20250109-AI 装修-agentic版\frontend\public\styles\美式.jpg"
with open(test_image_path, "rb") as f:
    image_data = f.read()

image_base64 = base64.b64encode(image_data).decode("utf-8")

model = "gemini-2.5-flash-image"
api_url = f"{BASE_URL}/v1beta/models/{model}:generateContent"

headers = {
    "x-goog-api-key": API_KEY,
    "Content-Type": "application/json"
}

# 带参考图片的请求
data = {
    "contents": [{
        "parts": [
            {
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": image_base64
                }
            },
            {"text": "Transform this room into a modern minimalist living room design. Keep the room structure but add modern furniture, clean lines, and neutral colors."}
        ]
    }]
}

print(f"Testing API with image: {api_url}")
print(f"Image size: {len(image_data)} bytes")
print("-" * 50)

try:
    response = requests.post(api_url, headers=headers, json=data, timeout=180)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        candidates = result.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    print("SUCCESS! Got image data back!")
                    # 保存图片
                    img_data = base64.b64decode(part["inlineData"]["data"])
                    with open("test_output.png", "wb") as f:
                        f.write(img_data)
                    print("Image saved to test_output.png")
                elif "text" in part:
                    print(f"Text: {part['text'][:200]}")
    else:
        print(f"Response: {response.text[:1000]}")
except Exception as e:
    print(f"Error: {e}")
