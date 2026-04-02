#!/usr/bin/env python3
"""Create Instagram posts - uses quotes DB and raw images"""

import os, glob, json, random, fcntl, argparse
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

HASH_FILE = f"{CONTENT_DIR}/../image_hashes.json"

def _avg_hash(img_path, hash_size=8):
    """Perceptual hash - identical images give same hash"""
    try:
        img = Image.open(img_path).convert('L').resize((hash_size, hash_size), Image.LANCZOS)
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        bits = [1 if p >= avg else 0 for p in pixels]
        return ''.join(f'{b:04b}' for b in bits)
    except:
        return None

def _rehash_all():
    """Rebuild hash file with all current images"""
    hashes = {}
    for fname in os.listdir(RAW_DIR):
        if not fname.startswith('bokeh_') or not fname.endswith('.jpg'):
            continue
        h = _avg_hash(os.path.join(RAW_DIR, fname))
        if h:
            hashes[fname] = h
    json.dump(hashes, open(HASH_FILE, 'w'), indent=2)
    return hashes

def _get_available_hashes():
    """Get set of unique image hashes (deduped)"""
    try:
        hashes = json.load(open(HASH_FILE))
    except:
        hashes = {}

    # Rehash any new images not yet in the file
    rehash_needed = False
    for fname in os.listdir(RAW_DIR):
        if not fname.startswith('bokeh_') or not fname.endswith('.jpg'):
            continue
        if fname not in hashes:
            rehash_needed = True
            break

    if rehash_needed:
        hashes = _rehash_all()

    # Find unique hashes only (not duplicates of another file)
    hash_to_primary = {}
    for fname, h in hashes.items():
        if h not in hash_to_primary:
            hash_to_primary[h] = fname

    return set(hash_to_primary.keys())

def pick_unused_bokeh_image():
    """Pick a visually unique bokeh image that hasn't been used yet"""
    lock_path = USED_IMAGES_FILE + '.lock'
    for attempt in range(10):
        with open(lock_path, 'w') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                used = load_used_images()
                hashes = json.load(open(HASH_FILE))
                hash_to_primary = {}
                for fname, h in hashes.items():
                    if h not in hash_to_primary:
                        hash_to_primary[h] = fname

                unique_hashes = set(hash_to_primary.keys())
                available = [
                    fname for fname, h in hashes.items()
                    if h in unique_hashes and fname not in used
                ]

                if not available:
                    # All used - try to find any unused hash
                    for h, fname in hash_to_primary.items():
                        if fname not in used:
                            available = [fname]
                            break

                if not available:
                    print("All bokeh images used! Resetting...")
                    used = set()
                    save_used_images(used)
                    # Pick any image (all are "used" now)
                    available = list(hash_to_primary.values())

                chosen = random.choice(available)
                used.add(chosen)
                save_used_images(used)
                return chosen
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    raise RuntimeError("Failed to pick bokeh image after 10 attempts")

def create_post(output_name=None, reuse_quote=False):
    # Pick unused bokeh background
    img_file = pick_unused_bokeh_image()
    img_path = f"{RAW_DIR}/{img_file}"
    
    # Get quote - reuse last used if requested
    if reuse_quote:
        db = load_quotes()
        used = db.get("used", [])
        if used:
            last_quote_text = used[-1]
            # Find the full quote object
            quote = next((q for q in db["quotes"] if q["quote"].rstrip('.').strip().lower() == last_quote_text.lower()), None)
            if quote:
                print(f"Reusing quote: {quote['quote'][:50]}...")
            else:
                # Stripped quote not found exactly - try matching
                quote = next((q for q in db["quotes"] if last_quote_text.lower() in q["quote"].lower()), None)
                if not quote:
                    print("Couldn't find last quote, picking new one")
                    quote = get_quote()
        else:
            print("No previous quote to reuse, picking new one")
            quote = get_quote()
    else:
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
    parser = argparse.ArgumentParser(description="Create Instagram quote posts")
    parser.add_argument("--reuse-quote", action="store_true", help="Reuse the last quote instead of picking a new one")
    args = parser.parse_args()
    create_post(reuse_quote=args.reuse_quote)
