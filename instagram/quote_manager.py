#!/usr/bin/env python3
"""Quote database manager - literary + generated quotes"""

import json, random, os
from datetime import datetime

QUOTE_DB = "/home/colton/.openclaw/workspace/instagram/quotes_db.json"

def load_db():
    try:
        with open(QUOTE_DB) as f:
            return json.load(f)
    except:
        return {"quotes": [], "used": []}

def save_db(db):
    with open(QUOTE_DB, "w") as f:
        json.dump(db, f, indent=2)

def add_quote(quote, author, source="generated"):
    db = load_db()
    for q in db["quotes"]:
        if q["quote"] == quote:
            return "Quote already exists"
    db["quotes"].append({
        "quote": quote,
        "author": author,
        "source": source,
        "added": str(datetime.now())
    })
    save_db(db)
    return f"Added: {quote[:50]}... - {author}"

def get_random_quote():
    db = load_db()
    available = [q for q in db["quotes"] if q["quote"] not in db["used"]]
    if not available:
        return None, "No quotes available"
    q = random.choice(available)
    db["used"].append(q["quote"])
    save_db(db)
    return q, "Success"

def list_quotes():
    return load_db()

# Literary quotes
LITERARY_QUOTES = [
    {"quote": "I am no bird; and no net ensnares me: I am a free human being with an independent will.", "author": "Charlotte Brontë", "source": "Jane Eyre"},
    {"quote": "It is nothing to die; it is dreadful not to live.", "author": "Victor Hugo", "source": "Les Misérables"},
    {"quote": "The only way out of the labyrinth of suffering is to forgive.", "author": "John Green", "source": "Looking for Alaska"},
    {"quote": "So we beat on, boats against the current, borne back ceaselessly into the past.", "author": "F. Scott Fitzgerald", "source": "The Great Gatsby"},
    {"quote": "I would always rather be happy than dignified.", "author": "Charlotte Brontë", "source": "Jane Eyre"},
    {"quote": "The only thing worse than being in an awkward situation is having to witness it.", "author": "Kurt Vonnegut", "source": "Hocus Pocus"},
    {"quote": "I am not afraid of storms, for I am learning how to sail my ship.", "author": "Louisa May Alcott", "source": "Little Women"},
    {"quote": "There is some good in this world, and it's worth fighting for.", "author": "J.R.R. Tolkien", "source": "The Two Towers"},
    {"quote": "I take my sanity very seriously, but I also know that it fluctuates.", "author": "David Sedaris", "source": "Me Talk Pretty One Day"},
    {"quote": "The best way to predict the future is to create it.", "author": "Peter Drucker", "source": "Management"},
]

def init_db():
    db = load_db()
    if not db["quotes"]:
        for q in LITERARY_QUOTES:
            add_quote(q["quote"], q["author"], q["source"])
        print(f"Initialized with {len(LITERARY_QUOTES)} literary quotes")
    return db

if __name__ == "__main__":
    db = init_db()
    print(f"Total quotes: {len(db['quotes'])}")
    print(f"Used: {len(db['used'])}")
