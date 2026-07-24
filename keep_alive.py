import requests
import time

# Replace with your actual Render URL
RENDER_URL = "https://your-app-name.onrender.com"

while True:
    try:
        response = requests.get(f"{RENDER_URL}/api/health", timeout=10)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Pinged health endpoint: {response.status_code}")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Failed to ping: {e}")
    
    # Ping every 10 minutes to prevent sleeping
    time.sleep(600)