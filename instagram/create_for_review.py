#!/usr/bin/env python3
"""Create Instagram post for review"""
import sys
sys.path.insert(0, '/home/colton/.openclaw/workspace/instagram')
from create_posts import create_post
import subprocess

output = create_post()
print(f"Created: {output}")

# Use OpenClaw message command
result = subprocess.run([
    '/home/colton/.npm-global/bin/openclaw', 'message', 'send',
    '--channel', 'telegram',
    '--target', '7381765039',
    '--media', output,
    '--message', '📱 New post ready for review!'
], capture_output=True, text=True)

print("Telegram notification sent")
