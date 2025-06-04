#!/usr/bin/env python3
import json
import urllib.parse

def is_valid_entry(entry):
    name = entry.get('name', '')
    website = entry.get('website') or ''
    # Exclude category entries
    if name.startswith('Category:'):
        return False
    # Exclude event or protest entries
    if 'protest' in name.lower():
        return False
    # Exclude entries whose website is search/link to google/wikipedia
    invalid_domains = ['google.com', 'books.google.com', 'wikipedia.org', 'wikimediafoundation.org', 'archive.org', 'nypost.com']
    for d in invalid_domains:
        if d in website:
            return False
    # Exclude entries without a genuine URL (e.g. None)
    if not website:
        return False
    # Passed all checks
    return True


def main():
    # Load all services
    with open('veteran_services.json', 'r', encoding='utf-8') as f:
        services = json.load(f)
    # Filter
    filtered = [s for s in services if is_valid_entry(s)]
    # Save
    with open('filtered_services.json', 'w', encoding='utf-8') as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)
    print(f"Filtered down to {len(filtered)} services from {len(services)} total.")

if __name__ == '__main__':
    main() 