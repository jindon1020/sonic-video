"""
SonicVideo — Native macOS Desktop Launcher
Starts FastAPI server in a background thread and opens a pywebview native window.
"""
import os
import sys
import threading
import time
import urllib.request

# Ensure working directory is the project root (important for py2app bundle)
if getattr(sys, 'frozen', False):
    # Running inside a py2app bundle
    os.chdir(os.path.dirname(os.path.abspath(sys.executable)))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

# FFmpeg PATH supplement (Homebrew locations)
for p in ("/opt/homebrew/bin", "/usr/local/bin"):
    if p not in os.environ.get("PATH", "") and os.path.exists(p):
        os.environ["PATH"] = f"{p}:{os.environ['PATH']}"

HOST = "127.0.0.1"
PORT = 8001


def start_server():
    """Run uvicorn in a daemon thread."""
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="warning")


def wait_for_server(timeout=30):
    """Block until the server responds to HTTP requests."""
    url = f"http://{HOST}:{PORT}/"
    for _ in range(timeout * 10):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.1)
    return False


def main():
    import webview

    # Start FastAPI in background
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    if not wait_for_server():
        print("Error: Server failed to start.")
        sys.exit(1)

    # Open native window
    window = webview.create_window(
        title="SonicVideo",
        url=f"http://{HOST}:{PORT}",
        width=1440,
        height=900,
        min_size=(1024, 680),
    )
    webview.start()


if __name__ == "__main__":
    main()
