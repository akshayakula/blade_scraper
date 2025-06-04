#!/usr/bin/env python3
import os
import json
import requests
import urllib.parse

"""
This script loads phone_services.json and stores each entry in Upstash Redis
with a key prefixed by 'rucksack:' so they're identified as core, non-government
veteran services. Values are stored indefinitely.
Requires environment variables:
- UPSTASH_REDIS_REST_URL
- UPSTASH_REDIS_REST_TOKEN
Usage:
    python3 upstash_rucksack_cache.py
"""

def main():
    url = os.getenv("UPSTASH_REDIS_REST_URL")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        print("Error: Please set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN environment variables.")
        return
    # Ensure URL has scheme
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    params = {"_token": token}
    # Load phone services
    try:
        with open('phone_services.json', 'r', encoding='utf-8') as f:
            services = json.load(f)
    except FileNotFoundError:
        print("Error: 'phone_services.json' not found. Run filter_phone_services.py first.")
        return
    except Exception as e:
        print(f"Error loading 'phone_services.json': {e}")
        return
    # Store each entry with prefix
    for service in services:
        name = service.get('name')
        if not name:
            continue
        key = f"rucksack:{name}"
        # JSON encode the service
        value = json.dumps(service, ensure_ascii=False)
        key_enc = urllib.parse.quote(key, safe="")
        value_enc = urllib.parse.quote(value, safe="")
        endpoint = f"{url}/SET/{key_enc}/{value_enc}"
        try:
            resp = requests.get(endpoint, params=params)
            if resp.status_code == 200:
                print(f"OK: Set {key}")
            else:
                print(f"Error setting {key}: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Request failed for {key}: {e}")
    print("Rucksack cache load complete.")

if __name__ == '__main__':
    main() 