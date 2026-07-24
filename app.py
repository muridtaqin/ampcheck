from flask import Flask, request, jsonify, send_from_directory
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import time
import os

app = Flask(__name__, static_folder='.', static_url_path='')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/check', methods=['POST'])
def check_amp():
    data = request.get_json()
    urls = data.get('urls', [])
    
    if not urls:
        return jsonify({"error": "Missing 'urls' array"}), 400
    
    results = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    for url in urls:
        url = url.strip()
        if not url:
            continue
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            time.sleep(0.3)
            response = requests.get(url, headers=headers, timeout=10)
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
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))