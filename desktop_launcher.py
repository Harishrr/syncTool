import sys
import os
import time
import threading
import webbrowser
import requests
import uvicorn

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORT = 8000
HOST = "127.0.0.1"
URL = f"http://{HOST}:{PORT}"

def start_server():
    from app.main import app
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")

def wait_for_server():
    max_retries = 30
    for _ in range(max_retries):
        try:
            r = requests.get(f"{URL}/", timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.3)
    return False

def main():
    print("=" * 60)
    print("               SYNC TOOL - DESKTOP LAUNCHER               ")
    print("=" * 60)
    print("Starting background API & database services...")

    # Start FastAPI in background daemon thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    print(f"Waiting for Sync Tool server at {URL}...")
    if not wait_for_server():
        print("Error: Server did not respond in time.")
        sys.exit(1)

    print("Server online! Opening desktop interface...")

    # Attempt to open with pywebview (Edge WebView2 native window)
    try:
        import webview
        window = webview.create_window(
            title="Sync Tool - Enterprise Data Synchronization",
            url=URL,
            width=1280,
            height=820,
            min_size=(900, 600),
            text_select=True
        )
        webview.start()
    except Exception as e:
        print(f"Native desktop window unavailable ({e}). Opening in default browser...")
        webbrowser.open(URL)
        print("Sync Tool is active in your browser. Press Ctrl+C in this terminal to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down Sync Tool.")

if __name__ == "__main__":
    main()
