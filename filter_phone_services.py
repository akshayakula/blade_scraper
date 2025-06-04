#!/usr/bin/env python3
import json

"""
This script filters 'filtered_services.json' to include only entries
that have a non-null, non-empty 'phone' field, and writes the
result to 'phone_services.json'.
"""

def main():
    try:
        with open('filtered_services.json', 'r', encoding='utf-8') as f:
            services = json.load(f)
    except FileNotFoundError:
        print("Error: 'filtered_services.json' not found. Please run filter_services.py first.")
        return
    except Exception as e:
        print(f"Error loading 'filtered_services.json': {e}")
        return

    phone_services = [s for s in services if s.get('phone')]

    with open('phone_services.json', 'w', encoding='utf-8') as f:
        json.dump(phone_services, f, ensure_ascii=False, indent=2)

    print(f"Filtered down to {len(phone_services)} services with phone numbers out of {len(services)} total filtered entries.")

if __name__ == '__main__':
    main() 