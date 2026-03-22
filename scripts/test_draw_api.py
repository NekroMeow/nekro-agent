#!/usr/bin/env python3
"""
Draw API 测试脚本 - 针对 Nekro AI API
"""
import asyncio
import json
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from httpx import AsyncClient, Timeout


async def test_nekro_draw_api():
    """测试 Nekro AI 绘图 API"""

    # Nekro API 配置
    api_base_url = "https://api.nekro.ai/v1"
    model_name = "gemini-2.5-flash-image-preview"

    # 测试 prompt
    test_prompt = "A cute anime girl with cat ears, pink hair, big eyes, kawaii style, illustration"

    print("=" * 60)
    print("Nekro AI Draw API 测试")
    print("=" * 60)
    print(f"API Base URL: {api_base_url}")
    print(f"Model: {model_name}")
    print(f"Prompt: {test_prompt}")
    print("=" * 60)

    # 测试 chat/completions 接口（非流式）
    print("\n📡 测试 /chat/completions 接口 (非流式)...")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    messages = [
        {"role": "user", "content": f"Generate an image: {test_prompt}"}
    ]

    json_data = {
        "model": model_name,
        "messages": messages,
        "stream": False,
    }

    try:
        async with AsyncClient(timeout=Timeout(120)) as client:
            response = await client.post(
                f"{api_base_url}/chat/completions",
                headers=headers,
                json=json_data,
            )

            print(f"\n📊 HTTP 状态码: {response.status_code}")
            print(f"📋 Response Headers: {dict(response.headers)}")

            # 保存完整响应
            try:
                data = response.json()
                print(f"\n📦 完整响应 JSON:")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:5000])

                # 分析响应结构
                print("\n🔍 响应结构分析:")
                print(f"  - 顶层 keys: {list(data.keys())}")
                if "choices" in data:
                    print(f"  - choices 数组长度: {len(data['choices'])}")
                    if len(data['choices']) > 0:
                        msg = data['choices'][0].get('message', {})
                        print(f"  - message keys: {list(msg.keys())}")
                        if 'image' in msg:
                            print(f"  - ⚠️ image 字段存在!")
                            print(f"    类型: {type(msg['image'])}")
                            print(f"    值: {str(msg['image'])[:500]}")
                        if 'content' in msg:
                            print(f"  - ⚠️ content 字段存在!")
                            print(f"    类型: {type(msg['content'])}")
                            print(f"    值: {str(msg['content'])[:500]}")

                # 保存到文件
                output_file = "/workspace/default/shared/final_debug_evidence.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "api_type": "nekro_chat_completions",
                        "api_url": f"{api_base_url}/chat/completions",
                        "model": model_name,
                        "request": json_data,
                        "response_status": response.status_code,
                        "response_headers": dict(response.headers),
                        "response_body": data
                    }, f, indent=2, ensure_ascii=False)
                print(f"\n✅ 响应已保存到: {output_file}")

            except json.JSONDecodeError:
                print(f"\n❌ JSON 解析失败!")
                print(f"原始响应文本:\n{response.text[:2000]}")

                output_file = "/workspace/default/shared/final_debug_evidence.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "api_type": "nekro_chat_completions",
                        "error": "JSON decode failed",
                        "response_status": response.status_code,
                        "raw_response": response.text
                    }, f, indent=2, ensure_ascii=False)
                print(f"\n✅ 原始响应已保存到: {output_file}")

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    await test_nekro_draw_api()
    print("\n🏁 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
