#!/usr/bin/env python3
"""Post tweets, replies, and threads to X/Twitter via API v2.

Usage:
    python post.py "Your tweet text"
    python post.py "Reply text" --reply-to 1234567890
    python post.py "Thread part 1" --thread "Thread part 2" --thread "Thread part 3"

Environment variables (from .env):
    X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
"""

import argparse
import os
import sys
from pathlib import Path

# Load .env from workspace root
env_path = Path(__file__).resolve().parents[3] / '.env'
if env_path.exists():
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                key, value = key.strip(), value.strip()
                if key and value:
                    os.environ.setdefault(key, value)

try:
    import tweepy
except ImportError:
    print("Error: tweepy not installed. Run: pip install tweepy", file=sys.stderr)
    sys.exit(1)


def get_client():
    keys = {
        'consumer_key': os.environ.get('X_API_KEY'),
        'consumer_secret': os.environ.get('X_API_SECRET'),
        'access_token': os.environ.get('X_ACCESS_TOKEN'),
        'access_token_secret': os.environ.get('X_ACCESS_TOKEN_SECRET'),
    }
    missing = [k for k, v in keys.items() if not v]
    if missing:
        print(f"Error: Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return tweepy.Client(**keys)


def post_tweet(text, reply_to=None):
    client = get_client()
    kwargs = {'text': text}
    if reply_to:
        kwargs['in_reply_to_tweet_id'] = reply_to
    response = client.create_tweet(**kwargs)
    tweet_id = response.data['id']
    print(f"https://x.com/xerusHQ/status/{tweet_id}")
    return tweet_id


def post_thread(texts):
    prev_id = None
    for i, text in enumerate(texts):
        prev_id = post_tweet(text, reply_to=prev_id)
        if i < len(texts) - 1:
            print(f"  [{i+1}/{len(texts)}] posted")
    print(f"Thread complete ({len(texts)} tweets)")


def main():
    parser = argparse.ArgumentParser(description='Post to X/Twitter')
    parser.add_argument('text', help='Tweet text (max 280 chars)')
    parser.add_argument('--reply-to', help='Tweet ID to reply to')
    parser.add_argument('--thread', action='append', help='Additional tweets for a thread (repeatable)')
    args = parser.parse_args()

    if args.thread:
        post_thread([args.text] + args.thread)
    else:
        post_tweet(args.text, reply_to=args.reply_to)


if __name__ == '__main__':
    main()
