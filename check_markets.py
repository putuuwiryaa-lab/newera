import json
import requests
import urllib3
import re
from html.parser import HTMLParser

urllib3.disable_warnings()

headers = {'User-Agent': 'Mozilla/5.0'}
try:
    r = requests.get('https://159.65.133.131/data-pengeluaran-togel/', headers=headers, verify=False, timeout=10)
    print("Data page status:", r.status_code, "Length:", len(r.text))
    print("URL final:", r.url)
    print("=== SEARCHING A TAGS ===")
    matches = re.findall(r'(<a[^>]+wla-portal[^>]*>.*?</a>)', r.text, re.DOTALL)
    markets_dict = {}
    for card in matches:
        href_match = re.search(r'href=["\']([^"\']+)["\']', card)
        name_match = re.search(r'class="wla-portal-market">([^<]+)</div>', card)
        tutup_match = re.search(r'class="wla-portal-tutup">([^<]+)</div>', card)
        if href_match and name_match:
            raw_href = href_match.group(1)
            path = re.sub(r'^https?://[^/]+', '', raw_href)
            clean_name = name_match.group(1).strip()
            tutup = tutup_match.group(1).strip() if tutup_match else ""
            markets_dict[clean_name] = {
                'path': path,
                'tutup': tutup
            }
            print(f"'{clean_name}': '{path}',  # {tutup}")

    with open('scraped_markets.json', 'w', encoding='utf-8') as f:
        json.dump(markets_dict, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(markets_dict)} markets to scraped_markets.json")


    # Sample page check
    r2 = requests.get('https://159.65.133.131/data-pengeluaran-togel-singapore/', headers=headers, verify=False, timeout=10)
    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', r2.text, re.IGNORECASE | re.DOTALL)
    title_match = re.search(r'<title[^>]*>(.*?)</title>', r2.text, re.IGNORECASE | re.DOTALL)
    print("\nSample Singapore Page:")
    if h1_match:
        print("H1:", re.sub(r'<[^>]+>', '', h1_match.group(1)).strip())
    if title_match:
        print("Title:", re.sub(r'<[^>]+>', '', title_match.group(1)).strip())

except Exception as e:
    print("Error:", e)

