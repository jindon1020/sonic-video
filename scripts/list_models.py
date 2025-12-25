import os
import dashscope
from dashscope import Models
from dotenv import load_dotenv

load_dotenv()
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

def list_models():
    # Only list the first page of models
    rsp = Models.list(page=1, page_size=20)
    if rsp.status_code == 200:
        for m in rsp.output['models']:
            print(f"Model ID: {m}")
    else:
        print(f"Error: {rsp.message}")

if __name__ == "__main__":
    list_models()
