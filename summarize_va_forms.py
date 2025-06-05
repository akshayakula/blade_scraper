#!/usr/bin/env python3

import os
import argparse
import json
import requests
import tempfile
import logging
import pickle
from pathlib import Path
from PyPDF2 import PdfReader
import openai

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure OPENAI_API_KEY is set
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("Error: Please set the OPENAI_API_KEY environment variable.")
    exit(1)

openai.api_key = OPENAI_API_KEY

# Create necessary directories
SUMMARIES_DIR = Path("summaries")
EMBEDDINGS_DIR = Path("embeddings")
SUMMARIES_DIR.mkdir(exist_ok=True)
EMBEDDINGS_DIR.mkdir(exist_ok=True)
logger.info(f"Created/verified directories: {SUMMARIES_DIR}, {EMBEDDINGS_DIR}")

def extract_text_from_pdf(pdf_path):
    """Extract all text content from a PDF file."""
    try:
        reader = PdfReader(pdf_path)
        text_content = []
        for page_num, page in enumerate(reader.pages):
            try:
                text = page.extract_text()
                if text:
                    text_content.append(text)
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num}: {e}")
        return "\n\n".join(text_content)
    except Exception as e:
        logger.error(f"Failed to read PDF {pdf_path}: {e}")
        return ""

def cleanup_text_with_ai(raw_text):
    """Use AI to clean up raw extracted text from forms."""
    if not raw_text:
        return raw_text
    
    try:
        # Limit text length to avoid token limits
        truncated_text = raw_text[:8000]
        
        prompt = (
            "Clean up this raw form text by removing OCR artifacts, fixing broken line breaks, "
            "standardizing whitespace, and making it more readable. Return only the cleaned text:\n\n"
            f"{truncated_text}"
        )
        
        response = openai.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[
                {'role': 'system', 'content': 'You are a text cleanup assistant. Clean up OCR text while preserving all important information.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        cleaned_text = response.choices[0].message.content.strip()
        logger.info("Text cleanup completed successfully")
        return cleaned_text
    except Exception as e:
        logger.warning(f"Text cleanup failed: {e}. Using uncleaned text.")
        return raw_text

def generate_embedding(text, identifier):
    """Generate embedding for given text using OpenAI API."""
    try:
        # Truncate text to avoid token limits (8191 tokens max)
        truncated_text = text[:30000]
        
        response = openai.embeddings.create(
            model="text-embedding-ada-002",
            input=truncated_text
        )
        
        embedding = response.data[0].embedding
        logger.info(f"Generated embedding for {identifier}")
        return embedding
    except Exception as e:
        logger.error(f"Embedding failed for {identifier}: {e}")
        return None

def save_embedding(embedding, identifier, embedding_type):
    """Save embedding to disk."""
    if embedding is None:
        return
    
    filename = EMBEDDINGS_DIR / f"{identifier}_{embedding_type}.pkl"
    try:
        with open(filename, 'wb') as f:
            pickle.dump({
                'identifier': identifier,
                'type': embedding_type,
                'embedding': embedding
            }, f)
        logger.info(f"Saved embedding to {filename}")
    except Exception as e:
        logger.error(f"Failed to save embedding for {identifier}: {e}")

def embed_all_documents():
    """Generate embeddings for all forms and summaries."""
    logger.info("Starting embedding generation for all documents...")
    
    # Embed summaries
    for summary_file in SUMMARIES_DIR.glob("*.txt"):
        try:
            if "_raw.txt" in str(summary_file):
                continue  # Skip raw files in this loop
                
            identifier = summary_file.stem
            embedding_file = EMBEDDINGS_DIR / f"{identifier}_summary.pkl"
            
            if embedding_file.exists():
                logger.info(f"Embedding for {identifier} summary already exists, skipping")
                continue
                
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary_text = f.read()
            
            embedding = generate_embedding(summary_text, f"{identifier}_summary")
            save_embedding(embedding, identifier, "summary")
            
        except Exception as e:
            logger.error(f"Failed to process summary {summary_file}: {e}")
            continue
    
    # Embed raw form texts
    for raw_file in SUMMARIES_DIR.glob("*_raw.txt"):
        try:
            identifier = raw_file.stem.replace('_raw', '')
            embedding_file = EMBEDDINGS_DIR / f"{identifier}_raw.pkl"
            
            if embedding_file.exists():
                logger.info(f"Embedding for {identifier} raw text already exists, skipping")
                continue
                
            with open(raw_file, 'r', encoding='utf-8') as f:
                raw_text = f.read()
            
            embedding = generate_embedding(raw_text, f"{identifier}_raw")
            save_embedding(embedding, identifier, "raw")
            
        except Exception as e:
            logger.error(f"Failed to process raw text {raw_file}: {e}")
            continue

# Parse optional start-id argument to resume processing after a given form entry id
parser = argparse.ArgumentParser(description='Summarize VA forms PDFs with optional resume support')
parser.add_argument('--start-id', help='Entry id in va_forms.json after which to start processing', default=None)
args = parser.parse_args()
start_id = args.start_id
# If start-id provided, skip entries until we hit that id, then resume on subsequent entries
skip = bool(start_id)

# Load VA forms metadata
try:
    with open('va_forms.json', 'r') as f:
        data_obj = json.load(f)
        va_forms = data_obj.get('data', [])
    logger.info(f"Loaded {len(va_forms)} forms from va_forms.json")
except Exception as e:
    logger.error(f"Failed to load va_forms.json: {e}")
    exit(1)

# Process each form
for entry in va_forms:
    # Handle resume: skip until after start_id
    if skip:
        if entry.get('id') == start_id:
            skip = False
        continue
    
    attrs = entry.get('attributes', {})
    url = attrs.get('url', '')
    if not url.lower().endswith('.pdf'):
        continue

    form_name = attrs.get('form_name', 'Unknown')
    title = attrs.get('title', 'No title')
    form_id = entry.get('id', form_name)
    
    # Check if summary already exists
    summary_filename = SUMMARIES_DIR / f"{form_name}.txt"
    if summary_filename.exists():
        logger.info(f"Summary exists for {form_name}, skipping")
        continue
    
    logger.info(f"Processing {form_name}: {title}")

    # Download PDF
    pdf_path = None
    try:
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            for chunk in resp.iter_content(chunk_size=8192):
                tmp.write(chunk)
            pdf_path = tmp.name
            
    except Exception as e:
        logger.warning(f"Failed to download {form_name} from {url}: {e}")
        # Log missed form and continue
        with open('missed_forms.txt', 'a') as mf:
            mf.write(f"{form_id}|{form_name}|{url}|{e}\n")
        continue

    try:
        # Extract text content from PDF
        logger.info(f"Extracting text from {form_name}...")
        raw_text = extract_text_from_pdf(pdf_path)
        
        if not raw_text:
            logger.warning(f"No text extracted from {form_name}, skipping")
            continue
        
        # Extract form fields
        reader = PdfReader(pdf_path)
        fields = reader.get_fields() or {}
        field_list = []
        for name, info in fields.items():
            ftype = info.get('/FT', 'Unknown')
            label = info.get('/TU') or info.get('/T') or name
            field_list.append({
                'name': name,
                'label': label,
                'type': ftype
            })
        
        # Clean up text with AI
        logger.info(f"Cleaning text for {form_name}...")
        cleaned_text = cleanup_text_with_ai(raw_text)
        
        # Prepare context for summarization
        fields_context = ""
        if field_list:
            fields_context = "\n\nForm fields found:\n" + "\n".join([
                f"- {field['label']} (type: {field['type']})" 
                for field in field_list[:20]  # Limit to first 20 fields
            ])
        
        # Summarize using OpenAI
        logger.info(f"Generating summary for {form_name}...")
        prompt = (
            f"You are an AI assistant. Summarize the following VA PDF form focusing on what this document can accomplish for a veteran. "
            f"Provide a concise overview.\n\n"
            f"Form: {form_name} - {title}\n"
            f"PDF URL: {url}\n"
            f"{fields_context}\n\n"
            f"Cleaned form text (excerpt):\n{cleaned_text[:3000]}"
        )
        
        response = openai.chat.completions.create(
            model='gpt-4',
            messages=[
                {'role': 'system', 'content': 'You summarize VA forms for veterans.'},
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        summary_text = response.choices[0].message.content.strip()
        
        # Save summary immediately
        with open(summary_filename, 'w', encoding='utf-8') as f:
            f.write(f"Form: {form_name}\n")
            f.write(f"Title: {title}\n")
            f.write(f"URL: {url}\n")
            f.write(f"Fields Count: {len(field_list)}\n")
            f.write(f"\nSummary:\n{summary_text}\n")
        
        logger.info(f"Summary for {form_name} saved to {summary_filename}")
        
        # Save the raw text for embedding later
        raw_text_file = SUMMARIES_DIR / f"{form_name}_raw.txt"
        with open(raw_text_file, 'w', encoding='utf-8') as f:
            f.write(raw_text)
            
    except Exception as e:
        logger.error(f"Failed to summarize {form_name}: {e}")
        continue
    
    finally:
        # Clean up temporary PDF file
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.unlink(pdf_path)
            except:
                pass

# After all summaries are generated, create embeddings
logger.info("All form processing complete. Starting embeddings generation...")
embed_all_documents()

# Generate final report
summary_count = len(list(SUMMARIES_DIR.glob("*.txt")))
embedding_count = len(list(EMBEDDINGS_DIR.glob("*.pkl")))
logger.info(f"Processing complete. Generated {summary_count} summaries and {embedding_count} embeddings.")

# Also create a consolidated summary file for backwards compatibility
logger.info("Creating consolidated summary JSON...")
summaries = []
for summary_file in SUMMARIES_DIR.glob("*.txt"):
    if "_raw.txt" in str(summary_file):
        continue
    try:
        with open(summary_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Parse the structured content
            lines = content.split('\n')
            form_name = lines[0].replace('Form: ', '') if lines else ''
            title = lines[1].replace('Title: ', '') if len(lines) > 1 else ''
            url = lines[2].replace('URL: ', '') if len(lines) > 2 else ''
            summary_start = content.find('\nSummary:\n')
            summary = content[summary_start + 10:].strip() if summary_start != -1 else ''
            
            summaries.append({
                'form_name': form_name,
                'title': title,
                'url': url,
                'summary': summary
            })
    except Exception as e:
        logger.error(f"Failed to read summary file {summary_file}: {e}")

with open('va_forms_summaries.json', 'w') as out:
    json.dump(summaries, out, indent=2)

logger.info(f"Created consolidated summary file with {len(summaries)} entries")