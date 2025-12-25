import os
import dashscope
from dashscope.aigc.video_synthesis import VideoSynthesis
from dotenv import load_dotenv

load_dotenv()
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

def test_video_gen():
    # Try the newest Wanx model name based on search results
    prompt = "A beautiful sunset over the ocean, cinematic lighting, high quality."
    print(f"Starting video generation with prompt: {prompt}")
    
    # Try wanx2.1-t2v-14b
    rsp = VideoSynthesis.call(model="wanx2.1-t2v-14b", 
                             prompt=prompt)
    print(f"Task Response: {rsp}")
    
    if rsp.status_code == 200:
        print(f"Task ID: {rsp.output.task_id}")
    else:
        print(f"Error: {rsp.message}")

if __name__ == "__main__":
    test_video_gen()
