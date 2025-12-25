import os
import dashscope
from dashscope import Models
from dotenv import load_dotenv

load_dotenv()
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

def search_models():
    print("Searching for 'wan' or 'video' models in ALL pages...")
    for page in range(1, 50):
        try:
            rsp = Models.list(page=page, page_size=50)
            if rsp.status_code == 200:
                models = rsp.output['models']
                if not models:
                    break
                for m in models:
                    name = m.get('model_id', m.get('model_name'))
                    if name and ('wan' in name.lower() or 'video' in name.lower()):
                        print(f"FOUND: {name} - {m.get('description')}")
            else:
                print(f"Page {page} error: {rsp.message}")
                break
        except Exception as e:
            print(f"Error on page {page}: {e}")
            break

if __name__ == "__main__":
    search_models()
