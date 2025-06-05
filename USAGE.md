# VA Forms Summarizer - Usage Guide

## Overview
This script processes VA forms PDFs, generates AI-powered summaries, and creates embeddings for semantic search.

## Key Features
1. **Per-form summary saving**: Summaries are saved immediately after generation
2. **Skip completed work**: Already processed forms are automatically skipped
3. **AI text cleanup**: Raw PDF text is cleaned before summarization
4. **Embeddings generation**: Creates vector embeddings for both summaries and raw text
5. **Comprehensive error handling**: Continues processing even if individual forms fail
6. **Detailed logging**: All operations are logged with timestamps

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set OpenAI API key:
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```

## Usage
Basic usage:
```bash
python3 summarize_va_forms.py
```

Resume from a specific form ID:
```bash
python3 summarize_va_forms.py --start-id form_id_here
```

## Directory Structure
The script creates and uses:
- `summaries/`: Individual form summaries and raw text
- `embeddings/`: Vector embeddings for semantic search
- `missed_forms.txt`: Log of forms that failed to process
- `va_forms_summaries.json`: Consolidated summary file

## Output Files
- `summaries/{form_name}.txt`: Structured summary with metadata
- `summaries/{form_name}_raw.txt`: Extracted raw text from PDF
- `embeddings/{form_name}_summary.pkl`: Embedding of summary
- `embeddings/{form_name}_raw.pkl`: Embedding of raw text

## Error Handling
- Failed downloads are logged to `missed_forms.txt`
- API failures (cleanup/summary/embedding) are logged but don't stop processing
- Each stage has independent error handling to maximize successful outputs