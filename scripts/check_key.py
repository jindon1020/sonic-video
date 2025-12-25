import httpx
import json

api_key = "AIzaSyBilY8UAEGVJuFv3Zp-jTqt-nR79g6smhs"
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    with httpx.Client() as client:
        response = client.get(url)
        if response.status_code == 200:
            models = response.json().get('models', [])
            print("Available models:")
            for model in models:
                print(f"- {model['name']} ({model['displayName']})")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
except Exception as e:
    print(f"Exception: {e}")
