import os
import dashscope
from dashscope.aigc.video_synthesis import VideoSynthesis
from dotenv import load_dotenv

load_dotenv()
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

def test_model(model_name):
    print(f"Testing model: {model_name}")
    try:
        rsp = VideoSynthesis.call(model=model_name, 
                                 prompt="A beautiful sunset over the ocean",
                                 size="1280*720")
        if rsp.status_code == 200:
            print(f"SUCCESS: {model_name} works! Task ID: {rsp.output.task_id}")
            return True
        else:
            print(f"FAILED: {model_name} - {rsp.code}: {rsp.message}")
            return False
    except Exception as e:
        print(f"ERROR: {model_name} - {str(e)}")
        return False

def main():
    candidates = [
        "wan2.1-t2v-14b",
        "modelscope-damo-text-to-video-synthesis",
        "wan-2.1-t2v-14b",
        "wan-t2v",
        "wanx-t2v"
    ]
    
    for model in candidates:
        if test_model(model):
            break

if __name__ == "__main__":
    main()
