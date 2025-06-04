#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin

# Regex to match US-style phone numbers
phone_pattern = re.compile(r'(?:\(\d{3}\)\s*\d{3}-\d{4}|\d{3}-\d{3}-\d{4})')

# Wikipedia category for American veterans' organizations
WIKI_CATEGORY_URL = "https://en.wikipedia.org/wiki/Category:American_veterans%27_organizations"

API_URL = 'https://en.wikipedia.org/w/api.php'

# Custom headers for HTTP requests
HEADERS = {'User-Agent': 'veteran-services-scraper/1.0 (https://example.com)'}

def get_org_links():
    """Fetch all members of the American veterans' organizations category via the MediaWiki API."""
    params = {
        'action': 'query',
        'list': 'categorymembers',
        'cmtitle': "Category:American_veterans'_organizations",
        'cmlimit': 'max',
        'format': 'json'
    }
    org_links = []
    while True:
        r = requests.get(API_URL, params=params, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        members = data.get('query', {}).get('categorymembers', [])
        for cm in members:
            title = cm.get('title')
            url = 'https://en.wikipedia.org/wiki/' + title.replace(' ', '_')
            org_links.append({'name': title, 'wiki_url': url})
        if 'continue' in data:
            params.update(data['continue'])
        else:
            break
    return org_links


def parse_infobox(soup):
    infobox = soup.find('table', {'class': 'infobox'})
    website_url = None
    type_text = ''
    if infobox:
        for th in infobox.find_all('th'):
            header = th.get_text().strip().lower()
            if header == 'website':
                td = th.find_next_sibling('td')
                if td:
                    a = td.find('a', class_='external')
                    if a and 'href' in a.attrs:
                        website_url = a['href']
            if header == 'type':
                td = th.find_next_sibling('td')
                if td:
                    type_text = td.get_text().strip().lower()
    return website_url, type_text


def get_details(wiki_url):
    try:
        r = requests.get(wiki_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
    except Exception:
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    # Get summary: first non-empty paragraph
    summary = ''
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        if text:
            summary = text
            break
    website_url, type_text = parse_infobox(soup)
    # First fallback: check 'External links' section for official site
    if not website_url:
        ext_header = soup.find('span', id='External_links')
        if ext_header:
            for sib in ext_header.parent.next_siblings:
                if getattr(sib, 'name', None) == 'ul':
                    link = sib.find('a', href=True)
                    if link:
                        website_url = link['href']
                    break
    # Second fallback: pick the first external link on the page
    if not website_url:
        ext_link = soup.find('a', class_='external')
        if ext_link and ext_link.has_attr('href') and 'wikipedia.org' not in ext_link['href']:
            website_url = ext_link['href']
    # Exclude government-run organizations if indicated
    if type_text and any(keyword in type_text for keyword in ['government', 'agency', 'department']):
        return None
    phone = None
    if website_url:
        try:
            # Check homepage for phone
            r2 = requests.get(website_url, headers=HEADERS, timeout=10)
            r2.raise_for_status()
            text = r2.text
            match = phone_pattern.search(text)
            if match:
                phone = match.group(0)
            else:
                # Fallback: look for contact page
                soup2 = BeautifulSoup(text, 'html.parser')
                contact_link = soup2.find('a', href=True, text=re.compile(r'contact', re.I))
                if contact_link:
                    href = contact_link['href']
                    contact_url = href if href.startswith('http') else urljoin(website_url, href)
                    r3 = requests.get(contact_url, headers=HEADERS, timeout=10)
                    r3.raise_for_status()
                    match2 = phone_pattern.search(r3.text)
                    if match2:
                        phone = match2.group(0)
        except Exception:
            pass
    return {
        'website': website_url,
        'phone': phone,
        'summary': summary
    }


def main():
    org_links = get_org_links()
    services = []
    for org in org_links:
        details = get_details(org['wiki_url'])
        if details:
            services.append({
                'name': org['name'],
                'website': details['website'],
                'phone': details['phone'],
                'summary': details['summary']
            })
    # Manually include Veterans Forge
    services.append({
        'name': 'Veterans Forge',
        'website': 'https://veteransforge.org',
        'phone': '1 833 858 4338',
        'summary': 'A nonprofit founded by veterans that provides specialized training in AI, emerging technologies, and career support to help US military veterans transition into tech careers.'
    })
    print(json.dumps(services, indent=2))

if __name__ == '__main__':
    main()