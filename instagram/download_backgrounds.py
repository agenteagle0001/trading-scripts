#!/usr/bin/env python3
"""Download bokeh background images from Pexels API"""

import requests, os, json, glob

API_KEY = "kbiGTO5dFK7oE0fE4yEs1NTldpWQhBvVjnHxr6a8IE4qitOwt7POGo7o"
RAW_DIR = "/home/colton/.openclaw/workspace/instagram/content/raw_images"
SEEN_FILE = "/home/colton/.openclaw/workspace/instagram/used_pexel_ids.json"

def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except:
        return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def get_next_bokeh_num():
    """Find the next available bokeh_N.jpg number"""
    existing = glob.glob(os.path.join(RAW_DIR, "bokeh_*.jpg"))
    nums = []
    for f in existing:
        try:
            num = int(os.path.basename(f).split("_")[1].split(".")[0])
            nums.append(num)
        except:
            pass
    return max(nums) + 1 if nums else 1

def search_pexels(query="bokeh background", per_page=15):
    url = f"https://api.pexels.com/v1/search?query={query}&per_page={per_page}"
    headers = {"Authorization": API_KEY}
    r = requests.get(url, headers=headers)
    return r.json()

def download():
    seen = load_seen()
    next_num = get_next_bokeh_num()
    
    print(f"Next bokeh number: {next_num}")
    print("Searching Pexels for 'bokeh background'...")
    results = search_pexels("bokeh background")
    
    new_count = 0
    for photo in results.get('photos', []):
        if photo['id'] in seen:
            continue
        
        # Download
        img_url = photo['src']['original']
        r = requests.get(img_url)
        
        # Save as bokeh_N.jpg
        filename = f"bokeh_{next_num}.jpg"
        filepath = os.path.join(RAW_DIR, filename)
        
        if r.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(r.content)
            seen.add(photo['id'])
            new_count += 1
            print(f"✓ Downloaded: {filename}")
            next_num += 1
        else:
            print(f"✗ Failed: {photo['id']}")
    
    save_seen(seen)
    print(f"\nDownloaded {new_count} new images!")

if __name__ == "__main__":
    download()
