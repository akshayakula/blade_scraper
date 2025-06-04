#!/usr/bin/env python3
import os
import json
import requests
import sys

def main():
    # Read token from environment
    token = os.getenv("VAPI_API_KEY")
    if not token:
        raise RuntimeError("Please set the VAPI_API_TOKEN environment variable.")
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch list of files from VAPI
    url = "https://api.vapi.ai/file"
    resp = requests.get(url, headers=headers)
    if not resp.ok:
        print(f"Failed to fetch file list: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

    # Parse response JSON
    data = resp.json()
    if isinstance(data, dict) and "data" in data:
        files = data["data"]
    elif isinstance(data, list):
        files = data
    else:
        print("Unexpected response format from VAPI API.", file=sys.stderr)
        sys.exit(1)

    # Extract IDs
    file_ids = [f.get("id") or f.get("file_id") for f in files if f.get("id") or f.get("file_id")]

    # Write out file IDs
    output_path = "vapi_file_ids.json"
    with open(output_path, "w", encoding="utf-8") as out_f:
        json.dump(file_ids, out_f, indent=2)
    print(f"Wrote {len(file_ids)} file IDs to {output_path}")

if __name__ == "__main__":
    main() 