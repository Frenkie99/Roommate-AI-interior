"""
测试 DMXAPI 接口是否可用
"""
import requests

API_KEY = "sk-dyNah1c5HM6bod5dtfjBQPXmDapeFJAsaoPMm8GCPbgIAs9j"
BASE_URL = "https://www.dmxapi.cn"

# 测试 nano-banana-2 模型（DMXAPI 文档中提到的）
model = "nano-banana-2"
api_url = f"{BASE_URL}/v1beta/models/{model}:generateContent"

headers = {
    "x-goog-api-key": API_KEY,
    "Content-Type": "application/json"
}

# 简单的文生图测试
data = {
    "contents": [{
        "parts": [
            {"text": "A beautiful modern living room with minimalist design"}
        ]
    }]
}

print(f"Testing API: {api_url}")
print(f"Headers: {headers}")
print(f"Payload: {data}")
print("-" * 50)

try:
    response = requests.post(api_url, headers=headers, json=data, timeout=120)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:1000]}")
except Exception as e:
    print(f"Error: {e}")
