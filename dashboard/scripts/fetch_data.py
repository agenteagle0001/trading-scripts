#!/usr/bin/env python3
"""
Greenville, TX Dashboard Data Fetcher
Run daily to update dashboard data
"""

import json
import os
from datetime import datetime

DATA_DIR = "/home/colton/.openclaw/workspace/dashboard/data"

def fetch_weather():
    """Get weather for Greenville, TX"""
    import urllib.request
    url = "https://wttr.in/75402?format=j1"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
            return {
                "source": "wttr.in",
                "updated": datetime.now().isoformat(),
                "temp_f": data['current_condition'][0]['temp_F'],
                "condition": data['current_condition'][0]['weatherDesc'][0]['value'],
                "humidity": data['current_condition'][0]['humidity'],
                "wind_mph": data['current_condition'][0]['windspeedMiles'],
                "feels_like": data['current_condition'][0]['FeelsLikeF']
            }
    except Exception as e:
        return {"error": str(e)}

def fetch_traffic():
    """
    Traffic data - placeholder
    Options for real data:
    - Mapbox Traffic API
    - Google Maps API
    - TomTom API
    - Texas DOT API
    """
    return {
        "source": "placeholder",
        "note": "Traffic API needs setup",
        "options": ["mapbox", "google", "tomtom", "txdot"]
    }

def fetch_jail():
    """
    Hunt County Jail listings
    Source: https://apps.huntcounty.net/jail/ (expired cert, but works with -k)
    """
    import urllib.request
    import re
    import ssl
    
    url = "https://apps.huntcounty.net/jail/results.asp"
    data = urllib.parse.urlencode({"limit": 50}).encode()
    
    try:
        req = urllib.request.Request(url, data=data, method='POST')
        # Ignore SSL certificate errors
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=15, context=ctx) as response:
            html = response.read().decode('utf-8', errors='ignore')
        
        # Parse inmate data
        rows = re.findall(r'<tr>.*?data-party="(\d+)".*?<th[^>]*>([^<]+)</th>.*?<td>([^<]*)</td>.*?<td>([^<]*)</td>.*?<td>([^<]*)</td>', html, re.DOTALL)
        
        inmates = []
        for party, name, gender, race, date in rows:
            if name and 'Jailing' not in name and name.strip():
                inmates.append({
                    'name': name.strip(),
                    'gender': gender.strip(),
                    'race': race.strip(),
                    'booking_date': date.strip()
                })
        
        return {
            'source': 'apps.huntcounty.net/jail',
            'status': 'ok',
            'total_count': len(inmates),
            'inmates': inmates[:30],
            'updated': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'source': 'apps.huntcounty.net/jail',
            'status': 'error',
            'error': str(e)
        }

def fetch_news():
    """Local news from Herald Banner"""
    import urllib.request
    import re
    
    url = "https://www.heraldbanner.com"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
        
        # Parse headlines
        headlines = re.findall(r'<a[^>]*href=\"([^\"]+article[^\"]*)\"[^>]*>\s*([^<]{10,80})', html)
        
        news = []
        seen = set()
        for url_path, title in headlines:
            title = title.strip().replace('&hellip;', '...').replace('&amp;', '&')
            if title and 'article' in url_path and title not in seen:
                seen.add(title)
                news.append({
                    'title': title,
                    'url': 'https://www.heraldbanner.com' + url_path
                })
                if len(news) >= 10:
                    break
        
        return {
            'source': 'heraldbanner.com',
            'status': 'ok',
            'count': len(news),
            'headlines': news,
            'updated': datetime.now().isoformat()
        }
    except Exception as e:
        return {
            'source': 'heraldbanner.com',
            'status': 'error',
            'error': str(e)
        }

def main():
    print("Fetching dashboard data for Greenville, TX...")
    
    # Create data directory if needed
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Fetch all data
    data = {
        "location": "Greenville, TX 75402",
        "updated": datetime.now().isoformat(),
        "weather": fetch_weather(),
        "traffic": fetch_traffic(),
        "jail": fetch_jail(),
        "news": fetch_news()
    }
    
    # Save to file
    output_path = os.path.join(DATA_DIR, "dashboard_data.json")
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Data saved to {output_path}")
    print(f"\nWeather: {data['weather'].get('temp_f', 'N/A')}°F - {data['weather'].get('condition', 'N/A')}")

if __name__ == "__main__":
    main()
