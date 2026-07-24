from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import time
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "3fa7a3a17dd32d0cb50e2af662b49d5d")
SCRAPINGBEE_KEY = os.environ.get("SCRAPINGBEE_KEY", "NBGHXBWL8XKOXHWHA103T6SZDEIYRA3TXXA5NZOHXN4HNJPAA6DLY23DGOZBRO4DF83QWNB59XN3X9U1")

# Read the HTML file once at startup to guarantee it's not empty
try:
    with open(os.path.join(BASE_DIR, 'index.html'), 'r', encoding='utf-8') as f:
        HTML_CONTENT = f.read()
except FileNotFoundError:
    HTML_CONTENT = "<h1>Error: index.html not found in root directory</h1>"

def fetch_with_fallback(target_url):
    providers = []
    
    if SCRAPERAPI_KEY:
        providers.append({
            "name": "ScraperAPI",
            "url": "http://api.scraperapi.com",
            "params": {"api_key": SCRAPERAPI_KEY, "url": target_url, "render": "true", "country_code": "us"}
        })
        
    if SCRAPINGBEE_KEY:
        providers.append({
            "name": "ScrapingBee",
            "url": "https://app.scrapingbee.com/api/v1/",
            "params": {"api_key": SCRAPINGBEE_KEY, "url": target_url, "render_js": "true", "premium_proxy": "true"}
        })

    if not providers:
        raise Exception("No scraping API keys configured in Render Environment Variables")

    for provider in providers:
        try:
            # Increased timeout to 45s to match Gunicorn's new 120s limit
            response = requests.get(provider["url"], params=provider["params"], timeout=45)
            
            if response.status_code in [401, 402, 403, 429, 500]:
                continue
            
            if response.status_code == 200:
                text_lower = response.text.lower()
                if "cf-browser-verification" in text_lower or "just a moment" in text_lower:
                    continue
                return response.text
        except Exception:
            continue

    raise Exception("All scraping providers failed or returned Cloudflare blocks")

@app.route('/')
def index():
    return Response(HTML_CONTENT, mimetype='text/html')

@app.route('/favicon.ico')
def favicon():
    # Return a 204 No Content to stop the browser from spamming 404/500 errors
    return '', 204

@app.route('/api/health')
def health():
    keys_count = sum([bool(SCRAPERAPI_KEY), bool(SCRAPINGBEE_KEY)])
    return jsonify({"status": "ok", "providers_configured": keys_count})

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
    for url in urls:
        url = url.strip()
        if not url: continue
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            html_content = fetch_with_fallback(url)
            soup = BeautifulSoup(html_content, 'html.parser')
            amp_tag = soup.find('link', rel='amphtml')
            
            if amp_tag and amp_tag.get('href'):
                results.append({"source_url": url, "amp_url": urljoin(url, amp_tag['href']), "status": "found"})
            else:
                results.append({"source_url": url, "amp_url": None, "status": "not_found"})
        except Exception as e:
            results.append({"source_url": url, "amp_url": None, "status": "error", "error": str(e)})
        
        time.sleep(0.3)
    
    return jsonify({"results": results})

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"CRITICAL ERROR: {str(e)}")
    return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)