import json
import os
import argparse


# Load file ID mappings from JSON

def load_file_ids(file_path="vapi_file_ids.json"):
    """Load the mapping of file IDs to metadata."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_knowledge_base():
    """Build the knowledge base by reading each file's content and its description."""
    file_ids = load_file_ids()
    kb = {}
    for file_id, meta in file_ids.items():
        path = meta.get('path')
        description = meta.get('description', '')
        content = ''
        if path and os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                content = ''
        kb[file_id] = {
            'description': description,
            'content': content
        }
    return kb


def query_knowledge_base(query):
    """Query the knowledge base for a given text and return matching files with snippets."""
    kb = build_knowledge_base()
    results = []
    q_lower = query.lower()
    for file_id, doc in kb.items():
        desc_lower = doc['description'].lower()
        content_lower = doc['content'].lower()
        snippet = ''
        if q_lower in desc_lower or q_lower in content_lower:
            # Create a snippet from content if found
            if q_lower in content_lower:
                idx = content_lower.find(q_lower)
                start = max(0, idx - 50)
                snippet = doc['content'][start:start + 200].replace('\n', ' ')
            else:
                snippet = doc['description']
            results.append({
                'file_id': file_id,
                'path': load_file_ids()[file_id]['path'],
                'snippet': snippet
            })
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Query the VAPI knowledge base')
    parser.add_argument('query', help='Text to search in the knowledge base')
    args = parser.parse_args()
    matches = query_knowledge_base(args.query)
    if not matches:
        print('No matches found for query:', args.query)
    else:
        for match in matches:
            print(f"File ID: {match['file_id']}")
            print(f"Path: {match['path']}")
            print('Snippet:', match['snippet'])
            print('-' * 40)