#!/usr/bin/env python3
import os
import requests
import urllib.parse

"""
This script clears all entries in the Upstash Redis cache.
It fetches all keys (KEYS *) and deletes each (DEL key).
Requires:
- UPSTASH_REDIS_REST_URL (with or without scheme)
- UPSTASH_REDIS_REST_TOKEN
"""

def main():
    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        print("Error: Please set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN environment variables.")
        return
    # Ensure scheme
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    params = {"_token": token}
    # Fetch all keys
    try:
        resp = requests.get(f"{url}/KEYS/*", params=params)
        resp.raise_for_status()
        keys = resp.json().get('result', [])
    except Exception as e:
        print(f"Error fetching keys: {e}")
        return
    if not keys:
        print("No keys found to delete.")
        return
    # Delete each key
    for k in keys:
        key_enc = urllib.parse.quote(k, safe="")
        try:
            r = requests.get(f"{url}/DEL/{key_enc}", params=params)
            r.raise_for_status()
            print(f"Deleted key: {k}")
        except Exception as e:
            print(f"Failed to delete {k}: {e}")
    print("Cache clear complete.")

if __name__ == '__main__':
    main() 