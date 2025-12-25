import asyncio
from app.core.llm_engine import LLMEngine
import os

async def test_qwen():
    print("Testing Alibaba Qwen integration...")
    try:
        engine = LLMEngine()
        result = await engine.generate_visual_script("海浪拍打着沙滩", "温馨的夏日旅行")
        print("\nSuccess! Qwen Result:")
        print(f"Reasoning: {result['reasoning']}")
        print(f"Visual Prompt: {result['visual_prompt']}")
    except Exception as e:
        print(f"\nFailed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_qwen())
