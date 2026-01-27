"""
测试新架构 - 验证 build_prompt_v2 和 LLM 集成
"""
import asyncio
import os
import sys

# 添加 backend 目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# 设置环境变量
os.environ["LLM_APIYI_KEY"] = "sk-x4iJS9s8HuVz5aUF6d78B49b66Cd4aE8B3014128F1562937"

from app.utils.prompt_builder import build_prompt_v2, GLOBAL_STRUCTURE_CONSTRAINTS
from app.services.llm_client import llm_client, LLMModel

async def test_full_integration():
    """测试完整集成流程"""
    
    # 查找测试图片
    test_image_path = None
    for f in os.listdir("input"):
        if f.endswith(('.jpg', '.jpeg', '.png')):
            test_image_path = os.path.join("input", f)
            break
    
    if not test_image_path:
        print("未找到测试图片")
        return
    
    print(f"测试图片: {test_image_path}")
    
    # 读取图片
    with open(test_image_path, "rb") as f:
        image_data = f.read()
    
    # 测试参数
    style = "modern_luxury"
    room_type = "living_room"
    custom_prompt = "需要暖色调"
    
    print(f"\n=== 测试参数 ===")
    print(f"风格: {style}")
    print(f"房间类型: {room_type}")
    print(f"自定义需求: {custom_prompt}")
    
    # 调用 LLM 分析
    print(f"\n=== LLM 分析中... ===")
    result = await llm_client.analyze_room_and_generate_prompt(
        image_data=image_data,
        style=style,
        room_type=room_type,
        custom_prompt=custom_prompt,
        model=LLMModel.GEMINI_3_FLASH_PREVIEW
    )
    
    if result.get("code") != 0:
        print(f"LLM 分析失败: {result.get('message')}")
        return
    
    print(f"\n=== LLM 分析成功 ===")
    
    data = result.get("data", {})
    analysis = data.get("analysis", {})
    enhanced_prompt = data.get("enhanced_prompt", "")
    
    print(f"\n=== 分析结果 ===")
    print(f"房间类型: {analysis.get('room_analysis', {}).get('room_type', 'N/A')}")
    print(f"空间描述: {analysis.get('room_analysis', {}).get('space_description', 'N/A')[:100]}...")
    
    print(f"\n=== 生成的提示词（前 1500 字符）===")
    print(enhanced_prompt[:1500])
    
    # 验证结构约束是否存在
    print(f"\n=== 验证结构约束 ===")
    if "CRITICAL STRUCTURAL CONSTRAINTS" in enhanced_prompt:
        print("✅ 结构约束已包含在提示词中")
    else:
        print("❌ 警告：结构约束缺失！")
    
    if "WINDOWS" in enhanced_prompt and "WALLS" in enhanced_prompt:
        print("✅ 窗户和墙体约束完整")
    else:
        print("❌ 警告：窗户或墙体约束缺失！")
    
    # 验证风格材质库
    if "MATERIAL & FINISHES" in enhanced_prompt:
        print("✅ 风格材质库已注入")
    else:
        print("⚠️ 风格材质库可能缺失")
    
    print(f"\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_full_integration())
