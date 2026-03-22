#!/usr/bin/env python3
"""Create Instagram posts - uses quotes DB and raw images"""

import os, glob, json, random, fcntl
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CONTENT_DIR = "/home/colton/.openclaw/workspace/instagram/content"
RAW_DIR = f"{CONTENT_DIR}/raw_images"
FINISHED_DIR = f"{CONTENT_DIR}/finished"
QUOTE_DB = f"{CONTENT_DIR}/../quotes_db.json"
LOCK_FILE = f"{CONTENT_DIR}/../quotes_db.lock"

os.makedirs(FINISHED_DIR, exist_ok=True)

def load_quotes():
    with open(QUOTE_DB) as f:
        return json.load(f)

def save_quotes(db):
    with open(QUOTE_DB, "w") as f:
        json.dump(db, f, indent=2)

def get_quote():
    # Use file lock to prevent race conditions
    with open(LOCK_FILE, 'w') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            db = load_quotes()
            available = [q for q in db["quotes"] if q["quote"] not in db.get("used", [])]
            if not available:
                print("All quotes used! Resetting...")
                db["used"] = []
                available = db["quotes"]
            q = random.choice(available)
            db["used"].append(q["quote"])
            save_quotes(db)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return q

def create_post(output_name=None):
    # Get random background
    images = [f for f in os.listdir(RAW_DIR) if f.endswith('.jpg')]
    if not images:
        print("No images found!")
        return
    img_file = random.choice(images)
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
        output_name = f"{FINISHED_DIR}/post_{len(os.listdir(FINISHED_DIR))+1}.jpg"
    img.save(output_name, quality=95)
    print(f"Saved: {output_name}")
    return output_name

if __name__ == "__main__":
    create_post()
