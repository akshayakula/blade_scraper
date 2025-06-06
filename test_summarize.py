#!/usr/bin/env python3

import json
import os
from pathlib import Path

# Create a minimal test va_forms.json file
test_data = {
    "data": [
        {
            "id": "test-form-1",
            "attributes": {
                "form_name": "VA21-0781",
                "title": "Statement in Support of Claim for Service Connection for PTSD",
                "url": "https://www.vba.va.gov/pubs/forms/VBA-21-0781-ARE.pdf"
            }
        },
        {
            "id": "test-form-2", 
            "attributes": {
                "form_name": "VA10-10EZ",
                "title": "Application for Health Benefits",
                "url": "https://www.va.gov/vaforms/medical/pdf/10-10EZ-fillable.pdf"
            }
        }
    ]
}

# Save test data
with open('va_forms_test.json', 'w') as f:
    json.dump(test_data, f, indent=2)

print("Test data created in va_forms_test.json")
print("\nTo test the script:")
print("1. Ensure OPENAI_API_KEY is set in your environment")
print("2. Run: python summarize_va_forms.py")
print("\nThe script will:")
print("- Create summaries/ and embeddings/ directories")
print("- Download and process the two test forms")
print("- Save individual summaries and embeddings")
print("- Skip forms if summaries already exist")
print("\nTo test resume functionality:")
print("python summarize_va_forms.py --start-id test-form-1")
print("\nCheck the logs for detailed progress information.")