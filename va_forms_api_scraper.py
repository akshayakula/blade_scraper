import requests
import json
import time

API_URL = "https://api.va.gov/v0/forms"
OUTPUT_FILE = "all_va_forms.json"


def fetch_all_forms():
    all_forms = []
    page = 1
    per_page = 100  # Try a high value if supported
    session = requests.Session()

    while True:
        params = {"page": page, "per_page": per_page}
        try:
            resp = session.get(API_URL, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break

        # The API may return forms in different keys; try common ones
        forms = data.get("data") or data.get("forms") or data.get("results") or []
        if not forms:
            print(f"No forms found on page {page}. Stopping.")
            break

        all_forms.extend(forms)
        print(f"Fetched {len(forms)} forms from page {page} (total: {len(all_forms)})")

        # Check for pagination info
        meta = data.get("meta") or {}
        total_pages = meta.get("total_pages") or meta.get("totalPages")
        if total_pages:
            if page >= total_pages:
                break
        else:
            # Fallback: stop if less than per_page returned
            if len(forms) < per_page:
                break
        page += 1
        time.sleep(0.5)  # Be polite

    return all_forms


def main():
    all_forms = fetch_all_forms()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_forms, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(all_forms)} forms to {OUTPUT_FILE}")


if __name__ == "__main__":
    main() 