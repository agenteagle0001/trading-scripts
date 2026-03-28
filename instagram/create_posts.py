#!/usr/bin/env python3
"""Create Instagram posts - uses quotes DB and raw images"""

import os, glob, json, random, fcntl
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CONTENT_DIR = "/home/colton/.openclaw/workspace/instagram/content"
RAW_DIR = f"{CONTENT_DIR}/raw_images"
FINISHED_DIR = f"{CONTENT_DIR}/finished"
QUOTE_DB = f"{CONTENT_DIR}/../quotes_db.json"
LOCK_FILE = f"{CONTENT_DIR}/../quotes_db.lock"
USED_IMAGES_FILE = f"{CONTENT_DIR}/../used_images.json"

os.makedirs(FINISHED_DIR, exist_ok=True)

def load_quotes():
    with open(QUOTE_DB) as f:
        return json.load(f)

def save_quotes(db):
    with open(QUOTE_DB, "w") as f:
        json.dump(db, f, indent=2)

def _norm(q):
    """Normalize quote text for comparison - strips punctuation, whitespace, lowercases"""
    return q.rstrip('.').strip().lower()

def get_quote():
    """Get a random unused quote with race-condition protection"""
    for attempt in range(10):  # retry up to 10 times
        with open(LOCK_FILE, 'w') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                db = load_quotes()
                used_normalized = set(_norm(u) for u in db.get("used", []))
                available = [q for q in db["quotes"] 
                            if _norm(q["quote"]) not in used_normalized]
                if not available:
                    print("All quotes used! Resetting...")
                    db["used"] = []
                    available = db["quotes"]
                q = random.choice(available)
                db["used"].append(q["quote"].rstrip('.'))
                save_quotes(db)
                return q
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        # If we get here, something went wrong - retry
    raise RuntimeError("Failed to get quote after 10 attempts")

def load_used_images():
    try:
        with open(USED_IMAGES_FILE) as f:
            return set(json.load(f))
    except:
        return set()

def save_used_images(images):
    with open(USED_IMAGES_FILE, 'w') as f:
        json.dump(list(images), f)

def pick_unused_bokeh_image():
    """Pick a bokeh image that hasn't been used yet - race-condition safe"""
    lock_path = USED_IMAGES_FILE + '.lock'
    for attempt in range(10):
        with open(lock_path, 'w') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                used = load_used_images()
                available = [f for f in os.listdir(RAW_DIR) if f.startswith('bokeh_') and f not in used]
                if not available:
                    print("All bokeh images used! Resetting...")
                    used = set()
                    available = [f for f in os.listdir(RAW_DIR) if f.startswith('bokeh_')]
                    if not available:
                        raise RuntimeError("No bokeh images found!")
                chosen = random.choice(available)
                used.add(chosen)
                save_used_images(used)
                return chosen
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    raise RuntimeError("Failed to pick bokeh image after 10 attempts")

def create_post(output_name=None):
    # Pick unused bokeh background
    img_file = pick_unused_bokeh_image()
    img_path = f"{RAW_DIR}/{img_file}"
    
    # Get quote
    quote = get_quote()
    print(f"Using: {quote['quote'][:50]}...")
    
    # Load and process image
    img = Image.open(img_path).convert('RGB')
    img = img.resize((1080, 1080), Image.Resampling.LANCZOS)
    
    # Darken for text readability
    from PIL import ImageEnhance
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(0.6)
    
    draw = ImageDraw.Draw(img)
    
    # Fonts
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Wrap text
    import textwrap
    quote_text = f'"{quote["quote"]}"'
    lines = textwrap.wrap(quote_text, width=22)
    
    # Draw
    W, H = 1080, 1080
    y = H/2 - (len(lines)*30)
    
    for line in lines:
        draw.text((W/2, y), line, font=font, fill="white", anchor="mm")
        y += 55
    
    # Author
    author = f"- {quote['author']}"
    draw.text((W/2, y + 30), author, font=font_small, fill="#cccccc", anchor="mm")
    
    # Watermark
    draw.text((W/2, H - 40), "@CurativeQuote", font=font_small, fill="white", anchor="mm")
    
    # Save
    if not output_name:
        # Find the highest post number to avoid collisions
        existing = glob.glob(f"{FINISHED_DIR}/post_*.jpg")
        max_num = 0
        for f in existing:
            try:
                num = int(os.path.basename(f).split('_')[1].split('.')[0])
                max_num = max(max_num, num)
            except:
                pass
        output_name = f"{FINISHED_DIR}/post_{max_num + 1}.jpg"
    img.save(output_name, quality=95)
    print(f"Saved: {output_name}")
    return output_name

if __name__ == "__main__":
    create_post()
