#!/usr/bin/env python3

import os
import re
import requests

API_URL = "https://api.vapi.ai/tool"
API_KEY = os.getenv("VAPI_API_KEY")

if not API_KEY:
    print("Error: Please set the VAPI_API_KEY environment variable.")
    exit(1)

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# List of VA hotlines with names, numbers, and descriptions
hotlines = [
    {"name": "VA Main Line", "phone": "1-800-827-1000", "description": "Everything: benefits, pensions, status checks"},
    {"name": "VA Health Care (VHA)", "phone": "1-877-222-8387", "description": "Enrollment, eligibility, treatment, etc."},
    {"name": "Caregiver Support", "phone": "1-855-260-3274", "description": "For families of injured veterans"},
    {"name": "VA Debt Management Center", "phone": "1-800-827-0648", "description": "For resolving benefit-related debts"},
    {"name": "VA GI Bill Education Line", "phone": "1-888-442-4551", "description": "All education benefits + claims"},
    {"name": "VA Homeless Hotline", "phone": "1-877-424-3838", "description": "For vets at risk or already unhoused"},
    {"name": "VA Burial & Memorial Benefits", "phone": "1-800-535-1117", "description": "For cemetery scheduling + burial benefits"},
    {"name": "White House VA Hotline", "phone": "1-855-948-2311", "description": "Directly escalates unresolved complaints"}
]

def make_function_name(name: str) -> str:
    """Convert a hotline name to a valid snake_case function name."""
    s = name.lower()
    s = re.sub(r"[\(\)&]", "", s)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "_", s.strip())
    return f"transfer_to_{s}"


def create_tool(line: dict):
    function_name = make_function_name(line["name"])
    payload = {
        "type": "transferCall",
        "function": {
            "name": function_name,
            "description": f"Transfer to {line['name']} at {line['phone']} for {line['description']}",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
    response = requests.post(API_URL, headers=headers, json=payload)
    try:
        response.raise_for_status()
        data = response.json()
        print(f"Created tool {data.get('id')} for {line['name']}")
    except Exception as e:
        print(f"Failed to create tool for {line['name']}: {e}\nResponse: {response.text}")


def main():
    for hotline in hotlines:
        create_tool(hotline)


if __name__ == "__main__":
    main() 