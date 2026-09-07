import json
import time
import requests
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://159.65.133.131"

OLD_TO_NEW = {
    'BULLSEYE': 'Bullseye',
    'CALIFORNIA': 'California',
    'CAROLINA DAY': 'North Carolina Day',
    'CAROLINA EVE': 'North Carolina Evening',
    'CHINA POOLS': 'Chinapools',
    'CONNECTICUT DAY': 'Connecticut Day',
    'CONNECTICUT NIGHT': 'Connecticut Night',
    'FLORIDA EVE': 'Florida Evening',
    'FLORIDA MID': 'Florida Midday',
    'GEORGIA EVE': 'Georgia Evening',
    'GEORGIA MIDDAY': 'Georgia Midday',
    'GEORGIA NIGHT': 'Georgia Night',
    'GERMANY PLUS5': 'Germany Plus5',
    'HONGKONG LOTTO': 'Hongkong Lotto',
    'HONGKONG POOLS': 'Hongkong Pools',
    'ILLINOIS EVE': 'Illinois Evening',
    'ILLINOIS MIDDAY': 'Illinois Midday',
    'INDIANA EVE': 'Indiana Evening',
    'INDIANA MIDDAY': 'Indiana Midday',
    'JAPAN': 'Japan',
    'KENTUCKY EVE': 'Kentucky Evening',
    'KENTUCKY MID': 'Kentucky Midday',
    'MAGNUM CAMBODIA': 'Magnum Cambodia',
    'MARYLAND EVE': 'Maryland Evening',
    'MARYLAND MIDDAY': 'Maryland Midday',
    'MICHIGAN EVE': 'Michigan Evening',
    'MICHIGAN MIDDAY': 'Michigan Midday',
    'MISSOURI EVE': 'Missouri Evening',
    'MISSOURI MIDDAY': 'Missouri Midday',
    'MOROCCO 03:00': 'Morocco Quatro 03:00 Wib',
    'MOROCCO 18:00': 'Morocco Quatro 18:00 Wib',
    'MOROCCO 21:00': 'Morocco Quatro 21:00 Wib',
    'MOROCCO 23:59': 'Morocco Quatro 23:59 Wib',
    'NEW JERSEY EVE': 'New Jersey Evening',
    'NEW JERSEY MIDDAY': 'New Jersey Midday',
    'NEW YORK EVE': 'New York Evening',
    'NEW YORK MID': 'New York Midday',
    'OREGON 10': 'Oregon 10:00 Wib',
    'OREGON 13': 'Oregon 13:00 Wib',
    'OREGON 4': 'Oregon 04:00 Wib',
    'OREGON 7': 'Oregon 07:00 Wib',
    'PCSO': 'Pcso',
    'SINGAPORE': 'SGP | Singapore',
    'SYDNEY LOTTO': 'Sydney Lotto',
    'SYDNEY POOLS': 'Sydneypools',
    'TAIWAN': 'Taiwan',
    'TENNESSE EVE': 'Tennesse Evening',
    'TENNESSE MIDDAY': 'Tennesse Midday',
    'TEXAS DAY': 'Texas Day',
    'TEXAS EVE': 'Texas Evening',
    'TEXAS MORNING': 'Texas Morning',
    'TEXAS NIGHT': 'Texas Night',
    'VIRGINIA DAY': 'Virginia Day',
    'VIRGINIA NIGHT': 'Virginia Night',
    'WASHINGTON DC EVE': 'Washington Dc Evening',
    'WASHINGTON DC MIDDAY': 'Washington Dc Midday',
    'WISCONSIN EVE': 'Wisconsin Evening'
}

PRIORITY_ORDER = {
    "Magnum Cambodia": 1,
    "Sydneypools": 2,
    "Sydney Lotto": 3,
    "Chinapools": 4,
    "Japan": 5,
    "SGP | Singapore": 6,
    "Pcso": 7,
    "Taiwan": 8,
    "Hongkong Pools": 9,
    "Hongkong Lotto": 10,
}

def scrape_market(url):
    try:
        res = requests.get(
            BASE + url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15,
            verify=False
        )
        html = res.text
        start_idx = html.find('Tema Terang')
        end_idx = html.find('RESET')
        if start_idx == -1 or end_idx == -1:
            return ''
        section = html[start_idx:end_idx]
        digits = re.findall(r'class="paito-digit">(\d)</span>', section)
        results = []
        for i in range(0, len(digits) - 3, 4):
            results.append(digits[i] + digits[i+1] + digits[i+2] + digits[i+3])
        return ' '.join(results[-500:])
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ''

def main():
    with open('scraped_markets.json', 'r', encoding='utf-8') as f:
        scraped_markets = json.load(f)

    json_path = 'C:/Users/HYPE AMD/.gemini/antigravity/scratch/newera-web/src/services/initialMarkets.json'
    with open(json_path, 'r', encoding='utf-8') as f:
        initial_data = json.load(f)

    new_data = {}
    next_order = 11

    # 1. Remap existing data
    for old_id, item in initial_data.items():
        if old_id in OLD_TO_NEW:
            new_id = OLD_TO_NEW[old_id]
            current_order = PRIORITY_ORDER.get(new_id, item.get('order', next_order))
            new_data[new_id] = {
                'id': new_id,
                'name': new_id,
                'history_data': item.get('history_data', ''),
                'order': current_order,
                'updated_at': item.get('updated_at', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
            }
            if new_id not in PRIORITY_ORDER:
                next_order = max(next_order, current_order + 1)

    print(f"Remapped {len(new_data)} existing markets.")

    # 2. Scrape any missing markets in scraped_markets
    missing_markets = [name for name in scraped_markets if name not in new_data]
    print(f"Found {len(missing_markets)} new markets to scrape: {missing_markets}")

    for name in missing_markets:
        path = scraped_markets[name]['path']
        print(f"Scraping new market: {name} ({path})...")
        hist = scrape_market(path)
        if hist:
            current_order = PRIORITY_ORDER.get(name, next_order)
            new_data[name] = {
                'id': name,
                'name': name,
                'history_data': hist,
                'order': current_order,
                'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
            if name not in PRIORITY_ORDER:
                next_order += 1
            print(f"  -> OK ({len(hist.split())} draws)")
        else:
            print(f"  -> FAILED to scrape {name}")
        time.sleep(1)

    print(f"\nTotal markets in updated initialMarkets: {len(new_data)}")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)
    print("Successfully wrote updated initialMarkets.json!")

if __name__ == '__main__':
    main()
