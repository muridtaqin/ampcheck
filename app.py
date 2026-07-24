from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import time
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Get these from your Render Environment Variables
SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "3fa7a3a17dd32d0cb50e2af662b49d5d")
ZENROWS_KEY = os.environ.get("ZENROWS_KEY", "")
SCRAPINGBEE_KEY = os.environ.get("SCRAPINGBEE_KEY", "NBGHXBWL8XKOXHWHA103T6SZDEIYRA3TXXA5NZOHXN4HNJPAA6DLY23DGOZBRO4DF83QWNB59XN3X9U1")

def fetch_with_fallback(target_url):
    """
    Tries multiple scraping APIs in order. 
    Returns the HTML text if successful, or raises an Exception if all fail.
    """
    providers = []
    
    # 1. ScraperAPI
    if SCRAPERAPI_KEY:
        providers.append({
            "name": "ScraperAPI",
            "url": "http://api.scraperapi.com",
            "params": {
                "api_key": SCRAPERAPI_KEY,
                "url": target_url,
                "render": "true",
                "country_code": "us"
            }
        })
    
    # 2. ZenRows
    if ZENROWS_KEY:
        providers.append({
            "name": "ZenRows",
            "url": "https://api.zenrows.com/v1/",
            "params": {
                "apikey": ZENROWS_KEY,
                "url": target_url,
                "js_render": "true",
                "premium_proxy": "true"
            }
        })
        
    # 3. ScrapingBee
    if SCRAPINGBEE_KEY:
        providers.append({
            "name": "ScrapingBee",
            "url": "https://app.scrapingbee.com/api/v1/",
            "params": {
                "api_key": SCRAPINGBEE_KEY,
                "url": target_url,
                "render_js": "true",
                "premium_proxy": "true"
            }
        })

    if not providers:
        raise Exception("No scraping API keys configured")

    last_error = "Unknown error"

    for provider in providers:
        try:
            # Scraping APIs with JS rendering can take 10-20 seconds
            response = requests.get(provider["url"], params=provider["params"], timeout=30)
            
            # Check for API-level failures (Out of credits, rate limited, bad key)
            if response.status_code in [401, 402, 403, 429, 500]:
                last_error = f"{provider['name']} failed (Status: {response.status_code})"
                time.sleep(0.5) # Brief pause before trying next provider
                continue
            
            # Check if the API successfully got the page, BUT the page is still a Cloudflare block
            if response.status_code == 200:
                text_lower = response.text.lower()
                if "cf-browser-verification" in text_lower or "just a moment" in text_lower or "captcha" in text_lower:
                    last_error = f"{provider['name']} returned a Cloudflare block page"
                    time.sleep(0.5)
                    continue
                
                # Success! We have the real HTML
                return response.text
                
        except requests.exceptions.Timeout:
            last_error = f"{provider['name']} timed out"
            continue
        except Exception as e:
            last_error = f"{provider['name']} error: {str(e)}"
            continue

    # If we get here, all providers failed
    raise Exception(f"All providers failed. Last error: {last_error}")


@app.route('/')
def index():
    return send_file(os.path.join(BASE_DIR, 'index.html'))

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "providers_configured": sum([bool(SCRAPERAPI_KEY), bool(ZENROWS_KEY), bool(SCRAPINGBEE_KEY)])})

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
        if not url:
            continue
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            # Fetch HTML using the resilient fallback system
            html_content = fetch_with_fallback(url)
            
            soup = BeautifulSoup(html_content, 'html.parser')
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
        
        # Polite delay between URLs to avoid overwhelming the APIs
        time.sleep(0.5)
    
    return jsonify({"results": results})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)