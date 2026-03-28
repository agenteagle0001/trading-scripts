#!/usr/bin/env python3
"""Send daily Instagram post to Telegram"""

import os, glob

FOLDER = "/home/colton/.openclaw/workspace/instagram/content/finished"
INDEX_FILE = "/home/colton/.openclaw/workspace/instagram/used_index.txt"

posts = sorted(glob.glob(f"{FOLDER}/post_*_clean.jpg"))
if not posts:
    print("No posts found!")
    exit(1)

# Get last used index
if os.path.exists(INDEX_FILE):
    with open(INDEX_FILE) as f:
        last_index = int(f.read().strip())
else:
    last_index = -1

# Next post (round robin)
next_index = (last_index + 1) % len(posts)

# Save new index
with open(INDEX_FILE, 'w') as f:
    f.write(str(next_index))

post = posts[next_index]

print(f"Sending: {post}")

os.system(f'/home/colton/.npm-global/bin/openclaw message send --target 7381765039 --media "{post}" --message "📱 Daily @CurativeQuote post (#{next_index+1})"')

print("Done!")
