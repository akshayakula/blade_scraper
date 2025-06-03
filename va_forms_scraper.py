#!/usr/bin/env python3
"""
VA Forms Scraper
================

This script crawls the VA "Find Forms" page and extracts form field information
from both HTML forms and PDF documents.

Required Dependencies:
----------------------
pip install requests beautifulsoup4 pdfplumber lxml PyPDF2 pymupdf pdfform

Optional Dependencies (for dynamic content):
pip install playwright
playwright install

Usage:
------
python va_forms_scraper.py

Output:
-------
Creates va_forms.json with extracted form data in the current directory.
"""

import json
import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import pdfplumber
import requests
from bs4 import BeautifulSoup
import PyPDF2
import fitz  # PyMuPDF
try:
    import pdfform
    PDFFORM_AVAILABLE = True
except ImportError:
    PDFFORM_AVAILABLE = False


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VAFormsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.base_url = "https://www.va.gov"
        self.forms_url = "https://www.va.gov/find-forms/"
        self.forms_data = []

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a webpage."""
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def crawl_forms_index(self) -> List[str]:
        """Crawl the main forms page and extract form detail URLs."""
        logger.info("Crawling form index...")
        
        form_links = []
        
        # Method 1: Try to scrape the main forms page first
        try:
            soup = self.get_page(self.forms_url)
            if soup:
                # Look for form links in various selectors
                link_selectors = [
                    'a[href*="/find-forms/about-"]',
                    'a[href*="about-form"]',
                    'a[href*="va-form"]',
                    '.form-link a',
                    '.va-form a'
                ]
                
                for selector in link_selectors:
                    links = soup.select(selector)
                    for link in links:
                        href = link.get('href')
                        if href:
                            full_url = urljoin(self.base_url, href)
                            if 'about-form' in full_url or 'about-va-form' in full_url:
                                form_links.append(full_url)
                                
        except Exception as e:
            logger.debug(f"Main page scraping failed: {e}")
        
        # Method 2: Try common VA forms
        try:
            common_forms = [
                'va-form-10-10ez',  # Healthcare application
                'va-form-21-526ez', # Disability compensation
                'va-form-22-1990',  # Education benefits
                'va-form-26-1880',  # Home loan
                'va-form-40-1330',  # Burial benefits
                'va-form-21-0966',  # Intent to file
                'va-form-21-4138',  # Statement in support
                'va-form-10-0003',  # Application update
                'va-form-22-5490',  # Dependents education
                'va-form-22-5495',  # Dependents education update
                'va-form-21-22',    # Power of attorney
                'va-form-21-0779',  # Request for hearing
                'va-form-20-0995',  # Supplemental claim
                'va-form-10-5345',  # Request medical records
                'va-form-26-4555',  # Application in acquiring home
            ]
            
            for form_id in common_forms:
                form_url = f"{self.base_url}/find-forms/about-{form_id}/"
                try:
                    response = self.session.head(form_url, timeout=10)
                    if response.status_code == 200:
                        form_links.append(form_url)
                        logger.info(f"Found form: {form_url}")
                except:
                    pass
            
            # Method 3: Try to find sitemap or API endpoint
            sitemap_urls = [
                f"{self.base_url}/sitemap.xml",
                f"{self.base_url}/find-forms/sitemap.xml"
            ]
            
            for sitemap_url in sitemap_urls:
                try:
                    response = self.session.get(sitemap_url, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'xml')
                        urls = soup.find_all('url')
                        for url in urls:
                            loc = url.find('loc')
                            if loc and ('about-form' in loc.text or 'about-va-form' in loc.text):
                                form_links.append(loc.text)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Error crawling forms index: {e}")
        
        # Remove duplicates while preserving order
        unique_links = list(dict.fromkeys(form_links))
        logger.info(f"Found {len(unique_links)} form links")
        return unique_links

    def extract_html_form_fields(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract fields from HTML forms on the page."""
        fields = []
        forms = soup.find_all('form')
        
        for form in forms:
            # Find all input, select, and textarea elements
            form_elements = form.find_all(['input', 'select', 'textarea'])
            
            for element in form_elements:
                field_data = self.parse_form_element(element, soup)
                if field_data:
                    fields.append(field_data)
        
        return fields

    def parse_form_element(self, element, soup: BeautifulSoup) -> Optional[Dict]:
        """Parse a single form element and extract its metadata."""
        # Get field name (prefer name attribute, fallback to id)
        field_name = element.get('name') or element.get('id')
        if not field_name:
            return None

        # Determine field type
        field_type = element.get('type', element.name)
        if element.name == 'select':
            field_type = 'select'
        elif element.name == 'textarea':
            field_type = 'textarea'

        # Check if required
        required = bool(element.get('required'))
        
        # Try to find associated label
        label_text = self.find_field_label(element, soup)
        if label_text and '*' in label_text:
            required = True

        field_data = {
            'name': field_name,
            'type': field_type,
            'required': required
        }
        
        if label_text:
            field_data['label'] = label_text.strip()

        return field_data

    def find_field_label(self, element, soup: BeautifulSoup) -> Optional[str]:
        """Find the label associated with a form element."""
        # Try to find label by 'for' attribute
        element_id = element.get('id')
        if element_id:
            label = soup.find('label', {'for': element_id})
            if label:
                return label.get_text(strip=True)

        # Try to find parent label
        parent_label = element.find_parent('label')
        if parent_label:
            return parent_label.get_text(strip=True)

        # Try to find nearby text that might be a label
        previous_elements = element.find_all_previous(['label', 'span', 'div', 'p'], limit=3)
        for prev_elem in previous_elements:
            text = prev_elem.get_text(strip=True)
            if text and len(text) < 100:  # Reasonable label length
                return text

        return None

    def find_pdf_links(self, soup: BeautifulSoup, form_url: str) -> List[str]:
        """Find all PDF download links on a form page."""
        pdf_urls = []
        
        # Method 1: Look for direct PDF links
        pdf_selectors = [
            'a[href*=".pdf"]',
            'a[download*=".pdf"]', 
            'a[href*="download"]',
            'button[onclick*="pdf"]',
            '.download-link',
            '.pdf-link',
            '.pdf-download',
            'a[href*="vaforms"]',
            'a[href*="form"]'
        ]
        
        for selector in pdf_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href') or link.get('data-href')
                if href:
                    # Skip mailto and other non-http links
                    if href.startswith(('mailto:', 'tel:', 'javascript:')):
                        continue
                    
                    pdf_url = urljoin(self.base_url, href)
                    if pdf_url.lower().endswith('.pdf') or 'download' in pdf_url.lower():
                        pdf_urls.append(pdf_url)
        
        # Method 2: Look for data attributes that might contain PDF URLs
        pdf_elements = soup.find_all(attrs={"data-href": re.compile(r'\.pdf$', re.I)})
        for element in pdf_elements:
            href = element.get('data-href')
            if href:
                pdf_url = urljoin(self.base_url, href)
                pdf_urls.append(pdf_url)
        
        # Method 3: Extract form number and try common VA PDF URL patterns
        form_numbers = self.extract_form_numbers(soup)
        for form_number in form_numbers:
            potential_urls = [
                f"https://www.va.gov/vaforms/va/pdf/VA{form_number}.pdf",
                f"https://www.va.gov/vaforms/medical/pdf/VA{form_number}.pdf",
                f"https://www.vba.va.gov/pubs/forms/VA{form_number}.pdf",
                f"https://www.va.gov/vaforms/form_detail.asp?FormNo={form_number}",
                f"https://www.va.gov/forms/download.cfm?ID={form_number}",
                f"https://www.va.gov/vaforms/{form_number}.pdf"
            ]
            
            for pdf_url in potential_urls:
                if self.url_exists(pdf_url):
                    pdf_urls.append(pdf_url)
                    logger.info(f"Found PDF via pattern: {pdf_url}")
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(pdf_urls))

    def extract_form_numbers(self, soup: BeautifulSoup) -> List[str]:
        """Extract form numbers from the page content."""
        form_numbers = []
        text = soup.get_text()
        
        # Common VA form number patterns
        patterns = [
            r'VA Form (\d+-\d+[a-zA-Z]*)',
            r'Form (\d+-\d+[a-zA-Z]*)',
            r'VA(\d+-\d+[a-zA-Z]*)',
            r'(\d+-\d+[a-zA-Z]*)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.I)
            form_numbers.extend(matches)
        
        # Clean up form numbers (remove duplicates, normalize)
        cleaned_numbers = []
        for num in form_numbers:
            num = num.upper().replace('-', '-')  # Normalize dashes
            if num not in cleaned_numbers and len(num) >= 4:  # Reasonable form number length
                cleaned_numbers.append(num)
        
        return cleaned_numbers

    def url_exists(self, url: str) -> bool:
        """Check if a URL exists without downloading the full content."""
        try:
            response = self.session.head(url, timeout=10)
            return response.status_code == 200
        except:
            return False

    def download_pdf(self, pdf_url: str) -> Optional[str]:
        """Download PDF to temporary file and return path."""
        try:
            response = self.session.get(pdf_url, timeout=60)
            response.raise_for_status()
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.write(response.content)
            temp_file.close()
            
            return temp_file.name
        except requests.RequestException as e:
            logger.error(f"Error downloading PDF {pdf_url}: {e}")
            return None

    def extract_pdf_form_fields(self, pdf_path: str) -> List[Dict]:
        """Extract form fields from a PDF document using multiple methods."""
        fields = []
        
        try:
            # Method 1: Try PyPDF2 for interactive form fields
            pdf_fields = self.extract_pdf_form_fields_pypdf2(pdf_path)
            if pdf_fields:
                fields.extend(pdf_fields)
                logger.info(f"Extracted {len(pdf_fields)} fields using PyPDF2")
            
            # Method 2: Try PyMuPDF for form fields
            mupdf_fields = self.extract_pdf_form_fields_mupdf(pdf_path)
            if mupdf_fields:
                fields.extend(mupdf_fields)
                logger.info(f"Extracted {len(mupdf_fields)} fields using PyMuPDF")
            
            # Method 3: Try pdfform if available
            if PDFFORM_AVAILABLE:
                pdfform_fields = self.extract_pdf_form_fields_pdfform(pdf_path)
                if pdfform_fields:
                    fields.extend(pdfform_fields)
                    logger.info(f"Extracted {len(pdfform_fields)} fields using pdfform")
            
            # Method 4: Fallback to text parsing with pdfplumber
            if not fields:
                with pdfplumber.open(pdf_path) as pdf:
                    all_text = ""
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            all_text += page_text + "\n"
                    
                    text_fields = self.parse_pdf_text_for_fields(all_text)
                    fields.extend(text_fields)
                    logger.info(f"Extracted {len(text_fields)} fields using text parsing")
                
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
        
        finally:
            # Clean up temporary file
            try:
                Path(pdf_path).unlink()
            except Exception:
                pass
        
        # Remove duplicates while preserving order
        seen = set()
        unique_fields = []
        for field in fields:
            field_key = f"{field.get('name', '')}_{field.get('type', '')}"
            if field_key not in seen:
                seen.add(field_key)
                unique_fields.append(field)
        
        return unique_fields

    def extract_pdf_form_fields_pypdf2(self, pdf_path: str) -> List[Dict]:
        """Extract form fields using PyPDF2."""
        fields = []
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Check if the PDF has form fields
                if "/AcroForm" in pdf_reader.trailer["/Root"]:
                    form_dict = pdf_reader.trailer["/Root"]["/AcroForm"]
                    if "/Fields" in form_dict:
                        for field in form_dict["/Fields"]:
                            field_obj = field.get_object()
                            field_name = field_obj.get("/T", "unknown")
                            field_type = field_obj.get("/FT", "/Tx")  # Default to text
                            field_required = "/Ff" in field_obj and field_obj["/Ff"] & 2
                            
                            # Map PDF field types to our types
                            type_mapping = {
                                "/Tx": "text",
                                "/Ch": "select",
                                "/Btn": "checkbox",
                                "/Sig": "signature"
                            }
                            
                            fields.append({
                                "name": str(field_name),
                                "type": type_mapping.get(str(field_type), "text"),
                                "required": bool(field_required)
                            })
                            
        except Exception as e:
            logger.debug(f"PyPDF2 extraction failed: {e}")
            
        return fields

    def extract_pdf_form_fields_mupdf(self, pdf_path: str) -> List[Dict]:
        """Extract form fields using PyMuPDF."""
        fields = []
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                widgets = page.widgets()
                
                for widget in widgets:
                    field_name = widget.field_name or f"field_{len(fields)}"
                    field_type = widget.field_type
                    field_required = widget.field_flags & 2  # Required flag
                    
                    # Map PyMuPDF field types to our types
                    type_mapping = {
                        fitz.PDF_WIDGET_TYPE_TEXT: "text",
                        fitz.PDF_WIDGET_TYPE_CHECKBOX: "checkbox",
                        fitz.PDF_WIDGET_TYPE_RADIOBUTTON: "radio",
                        fitz.PDF_WIDGET_TYPE_LISTBOX: "select",
                        fitz.PDF_WIDGET_TYPE_COMBOBOX: "select",
                        fitz.PDF_WIDGET_TYPE_SIGNATURE: "signature",
                        fitz.PDF_WIDGET_TYPE_BUTTON: "button"
                    }
                    
                    fields.append({
                        "name": field_name,
                        "type": type_mapping.get(field_type, "text"),
                        "required": bool(field_required)
                    })
            
            doc.close()
            
        except Exception as e:
            logger.debug(f"PyMuPDF extraction failed: {e}")
            
        return fields

    def extract_pdf_form_fields_pdfform(self, pdf_path: str) -> List[Dict]:
        """Extract form fields using pdfform library."""
        fields = []
        try:
            form_fields = pdfform.read_pdf_fields(pdf_path)
            
            for field_name, field_info in form_fields.items():
                field_type = "text"  # pdfform primarily handles text fields
                field_required = False  # pdfform doesn't provide required flag
                
                fields.append({
                    "name": field_name,
                    "type": field_type,
                    "required": field_required
                })
                
        except Exception as e:
            logger.debug(f"pdfform extraction failed: {e}")
            
        return fields

    def parse_pdf_text_for_fields(self, text: str) -> List[Dict]:
        """Parse PDF text to identify potential form fields."""
        fields = []
        lines = text.split('\n')
        
        # Common patterns for form fields in VA PDFs
        field_patterns = [
            (r'Social Security Number.*?:', 'social_security_number', 'text', True),
            (r'First Name.*?:', 'first_name', 'text', True),
            (r'Last Name.*?:', 'last_name', 'text', True),
            (r'Middle Initial.*?:', 'middle_initial', 'text', False),
            (r'Date of Birth.*?:', 'date_of_birth', 'date', True),
            (r'Address.*?:', 'address', 'text', True),
            (r'Phone.*?:', 'phone', 'tel', False),
            (r'Email.*?:', 'email', 'email', False),
            (r'Signature.*?:', 'signature', 'text', True),
            (r'Date.*?:', 'date', 'date', False),
            (r'Veteran.*?ID.*?:', 'veteran_id', 'text', True),
            (r'Service.*?Number.*?:', 'service_number', 'text', True),
        ]
        
        text_lower = text.lower()
        
        for pattern, field_name, field_type, required in field_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                fields.append({
                    'name': field_name,
                    'type': field_type,
                    'required': required
                })
        
        # Look for checkbox-like patterns
        checkbox_patterns = [
            (r'☐|□|\[ \]', 'checkbox'),
            (r'Yes.*?No', 'radio'),
        ]
        
        for pattern, field_type in checkbox_patterns:
            matches = re.findall(pattern, text)
            for i, match in enumerate(matches[:10]):  # Limit to reasonable number
                fields.append({
                    'name': f'checkbox_{i+1}',
                    'type': field_type,
                    'required': False
                })
        
        return fields

    def process_form_detail_page(self, form_url: str) -> Optional[Dict]:
        """Process a single form detail page."""
        soup = self.get_page(form_url)
        if not soup:
            return None

        # Extract form name from page
        form_name = self.extract_form_name(soup)
        logger.info(f"Processing form: {form_name}")

        fields = []

        # First, try to find HTML forms
        html_fields = self.extract_html_form_fields(soup)
        if html_fields:
            fields.extend(html_fields)
            logger.info(f"Extracted {len(html_fields)} HTML form fields")
        # Always look for PDF links, regardless of HTML forms
        pdf_urls = self.find_pdf_links(soup, form_url)
        
        for pdf_url in pdf_urls:
            logger.info(f"Processing PDF: {pdf_url}")
            pdf_path = self.download_pdf(pdf_url)
            if pdf_path:
                pdf_fields = self.extract_pdf_form_fields(pdf_path)
                fields.extend(pdf_fields)
                logger.info(f"Extracted {len(pdf_fields)} PDF form fields")

        return {
            'form_name': form_name,
            'url': form_url,
            'fields': fields
        }

    def extract_form_name(self, soup: BeautifulSoup) -> str:
        """Extract the form name from the page."""
        # Try different selectors for form name
        selectors = ['h1', '.page-title', '.form-title', 'title']
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text:
                    # Clean up the form name
                    # Remove "About " prefix if present
                    if text.startswith('About '):
                        text = text[6:]
                    return text
        
        # Fallback to first h1 or title
        h1 = soup.find('h1')
        if h1:
            text = h1.get_text(strip=True)
            if text.startswith('About '):
                text = text[6:]
            return text
        
        title = soup.find('title')
        if title:
            text = title.get_text(strip=True)
            if text.startswith('About '):
                text = text[6:]
            return text
        
        return "Unknown Form"

    def run(self):
        """Main execution method."""
        logger.info("Starting VA Forms Scraper...")
        
        # Get all form URLs
        form_urls = self.crawl_forms_index()
        if not form_urls:
            logger.error("No form URLs found!")
            return

        # Process each form
        for i, form_url in enumerate(form_urls, 1):
            logger.info(f"Processing form {i}/{len(form_urls)}")
            
            form_data = self.process_form_detail_page(form_url)
            if form_data:
                self.forms_data.append(form_data)
            
            # Rate limiting - be polite to VA servers
            time.sleep(1)

        # Save results
        self.save_results()
        logger.info(f"Scraping complete! Processed {len(self.forms_data)} forms")

    def save_results(self):
        """Save the extracted data to JSON file."""
        output_file = "va_forms.json"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.forms_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Results saved to {output_file}")
        except IOError as e:
            logger.error(f"Error saving results: {e}")


def main():
    scraper = VAFormsScraper()
    scraper.run()


if __name__ == "__main__":
    main()