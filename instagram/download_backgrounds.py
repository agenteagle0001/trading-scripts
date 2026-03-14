#!/usr/bin/env python3
"""Download bokeh background images from Pexels API"""

import requests, os, json

API_KEY = "kbiGTO5dFK7oE0fE4yEs1NTldpWQhBvVjnHxr6a8IE4qitOwt7POGo7o"
RAW_DIR = "/home/colton/.openclaw/workspace/instagram/content/raw_images"
SEEN_FILE = "/home/colton/.openclaw/workspace/instagram/used_pexel_ids.json"

def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except: return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def search_pextels(query="bokeh background", per_page=15):
    url = f"https://api.pexels.com/v1/search?query={query}&per_page={per_page}"
    headers = {"Authorization": API_KEY}
    r = requests.get(url, headers=headers)
    return r.json()

def download():
    seen = load_seen()
    
    print("Searching Pexels for 'bokeh background'...")
    results = search_pextels("bokeh background")
    
    new_count = 0
    for photo in results.get('photos', []):
        if photo['id'] in seen:
            continue
        
        # Download
        img_url = photo['src']['original']
        r = requests.get(img_url)
        
        # Save
        filename = f"bg_pe{photo['id']}.jpg"
        filepath = os.path.join(RAW_DIR, filename)
        
        if r.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(r.content)
            seen.add(photo['id'])
            new_count += 1
            print(f"✓ Downloaded: {filename}")
        else:
            print(f"✗ Failed: {photo['id']}")
    
    save_seen(seen)
    print(f"\nDownloaded {new_count} new images!")

if __name__ == "__main__":
    download()
