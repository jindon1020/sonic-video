
import os
import json
import base64
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI
from PIL import Image

load_dotenv()

def test_gemini_vision(image_path):
    print("\n--- Testing Gemini Vision ---")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Skipping Gemini: No API Key")
        return False
        
    try:
        genai.configure(api_key=api_key)
        # Try both common names
        for model_name in ['gemini-1.5-flash', 'gemini-pro-vision']:
            print(f"Trying Gemini model: {model_name}...")
            try:
                model = genai.GenerativeModel(model_name)
                img = Image.open(image_path)
                response = model.generate_content(["Describe this image in one sentence.", img])
                print(f"✅ Success with {model_name}: {response.text}")
                return True
            except Exception as e:
                print(f"❌ Failed with {model_name}: {e}")
    except Exception as e:
        print(f"Critical Gemini Error: {e}")
    return False

def test_qwen_vl(image_path):
    print("\n--- Testing Qwen-VL (via DashScope) ---")
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("Skipping Qwen-VL: No API Key")
        return False

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    
    def encode_image(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    try:
        base64_image = encode_image(image_path)
        response = client.chat.completions.create(
            model="qwen-vl-plus", # Or qwen-vl-max
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this image in one sentence."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        },
                    ],
                }
            ],
        )
        print(f"✅ Success with Qwen-VL: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"❌ Failed with Qwen-VL: {e}")
        return False

if __name__ == "__main__":
    # Create a dummy image if none exists for testing
    test_img = "debug_vision_test.jpg"
    img = Image.new('RGB', (100, 100), color = (73, 109, 137))
    img.save(test_img)
    
    gemini_ok = test_gemini_vision(test_img)
    qwen_ok = test_qwen_vl(test_img)
    
    print("\n=== Final Results ===")
    print(f"Gemini Vision: {'WORKING' if gemini_ok else 'FAILED'}")
    print(f"Qwen-VL: {'WORKING' if qwen_ok else 'FAILED'}")
    
    if os.path.exists(test_img):
        os.remove(test_img)
