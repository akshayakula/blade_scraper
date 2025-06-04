import json
import os
import argparse


# Load file ID mappings from JSON

def load_file_ids(file_path="vapi_file_ids.json"):
    """Load the mapping of file IDs to metadata."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"[DEBUG] Loaded file IDs manifest from {file_path}: {list(data.keys())}")
    return data


def build_knowledge_base():
    """Build the knowledge base by reading each file's content and its description."""
    file_ids = load_file_ids()
    print(f"[DEBUG] Building knowledge base from files: {file_ids}")
    kb = {}
    for file_id, meta in file_ids.items():
        path = meta.get('path')
        description = meta.get('description', '')
        print(f"[DEBUG] Processing file '{file_id}' at path '{path}'")
        content = ''
        if path:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    print(f"[DEBUG] Loaded content from {path} ({len(content)} chars)")
                except Exception as e:
                    print(f"[DEBUG] Error reading {path}: {e}")
                    content = ''
            else:
                print(f"[DEBUG] File path does not exist: {path}")
        kb[file_id] = {
            'description': description,
            'content': content
        }
    return kb


def query_knowledge_base(query):
    """Query the knowledge base for a given text and return matching files with snippets."""
    kb = build_knowledge_base()
    print(f"[DEBUG] Querying knowledge base with query: '{query}'")
    words = [w.lower() for w in query.split()]
    print(f"[DEBUG] Query words: {words}")
    results = []
    for file_id, doc in kb.items():
        desc_lower = doc['description'].lower()
        content_lower = doc['content'].lower()
        combined_text = desc_lower + ' ' + content_lower
        print(f"[DEBUG] Searching in file '{file_id}': description='{desc_lower[:50]}...', content length={len(content_lower)}")
        # Check if all words are in the combined text
        if all(word in combined_text for word in words):
            print(f"[DEBUG] Matched file '{file_id}' for all query words")
            # Determine snippet
            snippet = ''
            # Find snippet around first word occurrence in content, if present
            content_positions = [(content_lower.find(word), word) for word in words if word in content_lower]
            if content_positions:
                first_pos, first_word = min((pos, w) for pos, w in content_positions)
                start = max(0, first_pos - 50)
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