from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from urllib.parse import urljoin
from curl_cffi import requests  # <-- Upgraded library
from bs4 import BeautifulSoup
import time
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    return send_file(os.path.join(BASE_DIR, 'index.html'))

@app.route('/api/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/api/check', methods=['POST', 'GET', 'OPTIONS'])
def check_amp():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    if request.method == 'GET':
        return jsonify({"message": "Send a POST request with {'urls': ['...']}"})

    try:
        data = request.get_json(force=True)
        urls = data.get('urls', [])
    except Exception as e:
        return jsonify({"error": f"Invalid JSON: {str(e)}"}), 400
    
    if not urls:
        return jsonify({"error": "Missing URLs"}), 400
    
    results = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }
    
    for url in urls:
        url = url.strip()
        if not url:
            continue
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            time.sleep(0.5)
            
            # UPGRADED: chrome124 has a much better success rate against modern Cloudflare
            api_key = "d6e07a45-ac7f-41b5-acf3-f3ffbe896130"
           proxy_url = f"http://proxy.scrapeops.io/v1/?api_key={api_key}&url={url}"
           
           # Use standard requests here, ScrapeOps handles the Cloudflare bypass
           response = requests.get(proxy_url, timeout=15) 
            
            # If Cloudflare still blocks it, the status code will be 403
            if response.status_code == 403:
                results.append({
                    "source_url": url,
                    "amp_url": None,
                    "status": "error",
                    "error": "Blocked by Cloudflare/WAF (403)"
                })
                continue
                
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            amp_tag = soup.find('link', rel='amphtml')
            
            if amp_tag and amp_tag.get('href'):
                results.append({
                    "source_url": url,
                    "amp_url": urljoin(url, amp_tag['href']),
                    "status": "found"
                })
            else:
                results.append({
                    "source_url": url,
                    "amp_url": None,
                    "status": "not_found"
                })
        except Exception as e:
            results.append({
                "source_url": url,
                "amp_url": None,
                "status": "error",
                "error": str(e)
            })
    
    return jsonify({"results": results})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)