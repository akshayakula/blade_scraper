#!/usr/bin/env python3
import os
import json
import urllib.parse
import requests
import sys

"""
This script loads veteran_services.json and stores each entry in Upstash Redis
using the REST API. Each key is the service's name and the value is the JSON-encoded object.
Requires the environment variables:
- UPSTASH_REDIS_REST_URL (e.g. https://<your-upstash-endpoint>)
- UPSTASH_REDIS_REST_TOKEN
"""

def get_services(url, token):
    """Fetch all keys and values from Upstash and print as JSON list."""
    params = {'_token': token}
    try:
        # Get all keys
        resp = requests.get(f"{url}/KEYS/*", params=params)
        resp.raise_for_status()
        keys = resp.json().get('result', [])
    except Exception as e:
        print(f"Error fetching keys: {e}")
        return
    if not keys:
        print("No keys found.")
        return
    # Fetch all values via MGET
    key_list = [urllib.parse.quote(k, safe='') for k in keys]
    keys_path = '/'.join(key_list)
    try:
        resp = requests.get(f"{url}/MGET/{keys_path}", params=params)
        resp.raise_for_status()
        values = resp.json().get('result', [])
    except Exception as e:
        print(f"Error fetching values: {e}")
        return
    # Parse JSON values
    results = []
    for v in values:
        try:
            results.append(json.loads(v))
        except:
            results.append(v)
    print(json.dumps(results, indent=2))

def main():
    url = os.getenv("UPSTASH_REDIS_REST_URL")
    # Ensure URL includes scheme
    if url and not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        print("Error: Please set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN environment variables.")
        return
    # If 'get' mode, retrieve all entries
    if len(sys.argv) > 1 and sys.argv[1] == 'get':
        get_services(url, token)
        return

    # Load services from JSON
    try:
        with open("veteran_services.json", "r", encoding="utf-8") as f:
            services = json.load(f)
    except Exception as e:
        print(f"Error loading veteran_services.json: {e}")
        return

    for service in services:
        name = service.get("name")
        if not name:
            continue
        # JSON encode the service object
        value = json.dumps(service, ensure_ascii=False)
        # URL-encode key and value
        key_enc = urllib.parse.quote(name, safe="")
        value_enc = urllib.parse.quote(value, safe="")
        # Construct the Upstash REST endpoint for SET
        endpoint = f"{url}/SET/{key_enc}/{value_enc}"
        # Add token as query parameter
        params = {"_token": token}
        try:
            resp = requests.get(endpoint, params=params)
            if resp.status_code == 200:
                print(f"OK: Set key '{name}'")
            else:
                print(f"Error setting '{name}': {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Request failed for '{name}': {e}")

if __name__ == "__main__":
    main() 