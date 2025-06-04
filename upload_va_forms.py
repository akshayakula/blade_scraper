#!/usr/bin/env python3
import os
import json
import sys
import requests
from va_forms_scraper import VAFormsScraper

def main():
    # Get API token from environment
    token = os.getenv("VAPI_API_KEY")
    if not token:
        raise RuntimeError("Please set the VAPI_API_KEY environment variable.")
    headers = {"Authorization": f"Bearer {token}"}

    # Collect uploaded file IDs
    uploaded_ids = []

    # Load VA forms metadata
    with open("va_forms.json", encoding="utf-8") as f:
        data = json.load(f).get("data", [])

    scraper = VAFormsScraper()
    for item in data:
        form_id = item.get("id")
        attrs = item.get("attributes", {})
        form_name = attrs.get("form_name")
        pdf_url = attrs.get("url")

        print(f"Downloading Form {form_id} ({form_name}) from {pdf_url}")
        pdf_path = scraper.download_pdf(pdf_url)
        if not pdf_path:
            print(f"Failed to download PDF for form {form_id}", file=sys.stderr)
            continue

        print(f"Uploading {pdf_path} to VAPI endpoint...")
        with open(pdf_path, "rb") as pf:
            files = {"file": pf}
            response = requests.post(
                "https://api.vapi.ai/file",
                headers=headers,
                files=files
            )
        if response.ok:
            resp_json = response.json()
            print(f"Upload succeeded for form {form_id}: {resp_json}")
            # Capture file ID if present
            file_id = resp_json.get('id') or resp_json.get('file_id')
            if file_id:
                uploaded_ids.append(file_id)
        else:
            print(f"Upload failed for form {form_id}: {response.status_code} {response.text}", file=sys.stderr)

    # After uploading all, output and save the list of file IDs
    print("\nAll uploaded file IDs:", uploaded_ids)
    with open('uploaded_file_ids.json', 'w', encoding='utf-8') as out_f:
        json.dump(uploaded_ids, out_f, indent=2)

if __name__ == "__main__":
    main() 