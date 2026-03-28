#!/usr/bin/env python3
"""Fetch quotes from Quoteable.io and add to quotes_db.json

Automatically fetches 20 quotes at a time. When quotes are nearly exhausted,
call this script again to fetch more.
"""

import requests, json, os, random

QUOTES_DB = "/home/colton/.openclaw/workspace/instagram/quotes_db.json"
LOCK_FILE = "/home/colton/.openclaw/workspace/instagram/quotes_db.lock"
FETCH_COUNT = 20

FALLBACK_QUOTES = [
    "The best time to plant a tree was 20 years ago. The second best time is now.",
    "Simplicity is the ultimate sophistication.",
    "The only limit to our realization of tomorrow is our doubts of today.",
    "In the middle of difficulty lies opportunity.",
    "Life is what happens when you're busy making other plans.",
    "The mind is everything. What you think you become.",
    "The journey of a thousand miles begins with one step.",
    "It does not matter how slowly you go as long as you do not stop.",
    "Everything you've ever wanted is on the other side of fear.",
    "Success is not final, failure is not fatal: it is the courage to continue that counts.",
    "The only way to do great work is to love what you do.",
    "Believe you can and you're halfway there.",
    "The future belongs to those who believe in the beauty of their dreams.",
    "You miss 100% of the shots you don't take.",
    "The best revenge is massive success.",
    "Don't count the days, make the days count.",
    "Hard work beats talent when talent doesn't work hard.",
    "The difference between ordinary and extraordinary is that little extra.",
    "Dream big and dare to fail.",
    "Act as if what you do makes a difference. It does.",
]

def load_db():
    with open(QUOTES_DB) as f:
        return json.load(f)

def save_db(db):
    with open(QUOTES_DB, "w") as f:
        json.dump(db, f, indent=2)

def norm(q):
    return q.rstrip('.').strip().lower()

def fetch_from_quoteable(count):
    """Fetch quotes from Quoteable.io API"""
    url = f"https://api.quotable.io/quotes/random?limit={count}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return [(item['content'], item.get('author', 'Unknown')) for item in data]
    except Exception as e:
        print(f"Quoteable.io error: {e}")
    return None

def fetch_quotes():
    print(f"Fetching {FETCH_COUNT} quotes...")
    
    # Try Quoteable.io first
    quotes = fetch_from_quoteable(FETCH_COUNT)
    
    if quotes is None:
        print("Quoteable.io failed, using fallback quotes...")
        # Use fallback quotes (shuffled, take FETCH_COUNT)
        available = FALLBACK_QUOTES.copy()
        random.shuffle(available)
        quotes = [(q, "Anonymous") for q in available[:FETCH_COUNT]]
    
    # Load DB and add new quotes
    db = load_db()
    
    # Get existing quotes to avoid duplicates
    existing = set(norm(q['quote']) for q in db['quotes'])
    
    added = 0
    for content, author in quotes:
        if norm(content) not in existing:
            db['quotes'].append({
                "quote": content,
                "author": author,
                "source": "Quoteable.io" if author != "Anonymous" else "Anonymous"
            })
            added += 1
            existing.add(norm(content))
    
    save_db(db)
    print(f"Added {added} new quotes (skipped duplicates). Total quotes: {len(db['quotes'])}")

if __name__ == "__main__":
    fetch_quotes()
