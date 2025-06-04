#!/usr/bin/env python3
import os
import json
import openai
from va_forms_scraper import VAFormsScraper
import requests

# Ensure OpenAI API key is set in environment
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise RuntimeError("Please set the OPENAI_API_KEY environment variable.")

# Load forms data
with open("va_forms.json", encoding="utf-8") as f:
    data = json.load(f)

# Find form with ID 5333
form_entry = None
for item in data.get("data", []):
    if item.get("id") == "5333":
        form_entry = item
        break

if not form_entry:
    raise ValueError("Form ID 5333 not found in va_forms.json.")

attributes = form_entry["attributes"]
form_name = attributes.get("form_name")
form_title = attributes.get("title")
pdf_url = attributes.get("url")

print(f"Processing Form {form_name}: {form_title}\nPDF URL: {pdf_url}\n")

# Initialize scraper and download PDF
scraper = VAFormsScraper()
pdf_path = scraper.download_pdf(pdf_url)
if not pdf_path:
    raise RuntimeError(f"Failed to download PDF from {pdf_url}")

# Extract form fields from the PDF
fields = scraper.extract_pdf_form_fields(pdf_path)
print("Extracted Fields:")
print(json.dumps(fields, indent=2))

# Prepare prompt for summarization
prompt = (
    f"The following VA form (number: {form_name}, title: {form_title}) has these fields:\n"
    f"{json.dumps(fields, indent=2)}\n"
    "Please provide a concise summary of the purpose of this form."
)

# Initialize the OpenAI client and summarize the form's purpose with retry/fallback
client = openai.OpenAI()
messages = [
    {"role": "system", "content": "You are an assistant that summarizes the purpose of VA forms."},
    {"role": "user", "content": prompt}
]
summary = None
try:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.7
    )
    summary = response.choices[0].message.content.strip()
except openai.RateLimitError as e:
    print(f"Rate limit error on GPT-4: {e}. Falling back to gpt-3.5-turbo...")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.7
        )
        summary = response.choices[0].message.content.strip()
    except Exception as e2:
        print(f"Fallback summarization failed: {e2}")
except Exception as e:
    print(f"Error during summarization: {e}")
finally:
    if summary is None:
        summary = "Summary unavailable due to API errors."

print("\nForm Purpose Summary:")
print(summary)

# --- Upsert into vector store (Chroma) ---
try:
    from langchain.embeddings import OpenAIEmbeddings
    from langchain.vectorstores import Chroma
    from langchain.schema import Document
except ImportError:
    raise RuntimeError("Please install langchain and chromadb: pip install langchain chromadb")

# Combine content into a single document string
doc_content = (
    f"Form {form_name} - {form_title}\n"
    f"Fields:\n{json.dumps(fields, indent=2)}\n"
    f"Summary:\n{summary}"
)

# Initialize embeddings and Chroma vector store
embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))
vector_store = Chroma(
    collection_name="va_forms",
    persist_directory="./chroma_db",
    embedding_function=embeddings
)

# Create and add the document
doc = Document(page_content=doc_content, metadata={"form_id": form_name})
vector_store.add_documents([doc])
vector_store.persist()

print("Upsert complete: form 5333 added to vector store at ./chroma_db")

# --- Upsert to Trieve ---
retrieve_key = os.getenv("TRIEVE_KEY")
if not retrieve_key:
    raise RuntimeError("Please set the TRIEVE_KEY environment variable.")
headers = {
    "Content-Type": "application/json",
    "TR-Dataset": "55847173-1659-4e29-a457-9db3a2524cf6",
    "Authorization": retrieve_key
}
payload = {
    "chunk_html": doc_content,
    "link": pdf_url
}
response = requests.post("https://api.trieve.ai/api/chunk", headers=headers, json=payload)
if not response.ok:
    raise RuntimeError(f"Trieve upsert failed: {response.status_code} {response.text}")
print("Trieve upsert succeeded:", response.json()) 