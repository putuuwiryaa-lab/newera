import json
import time
import firebase_admin
from firebase_admin import credentials, firestore

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

def main():
    cred = credentials.Certificate('firebase-key.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    print("Reading current markets collection from Firestore...")
    all_docs = list(db.collection('markets').stream())
    print(f"Found {len(all_docs)} documents in Firestore 'markets'.")

    # Read local complete 64 markets
    json_path = 'C:/Users/HYPE AMD/.gemini/antigravity/scratch/newera-web/src/services/initialMarkets.json'
    with open(json_path, 'r', encoding='utf-8') as f:
        local_markets = json.load(f)

    # 1. Update / migrate old docs in Firestore
    for doc in all_docs:
        old_id = doc.id
        doc_data = doc.to_dict()

        if old_id in OLD_TO_NEW:
            new_id = OLD_TO_NEW[old_id]
            doc_data['id'] = new_id
            doc_data['name'] = new_id
            if new_id in PRIORITY_ORDER:
                doc_data['order'] = PRIORITY_ORDER[new_id]

            print(f"Migrating Firestore doc: '{old_id}' -> '{new_id}'...")
            db.collection('markets').document(new_id).set(doc_data)
            db.collection('markets').document(old_id).delete()
            print(f"  -> Migrated and deleted old doc '{old_id}'")
        elif old_id == 'WEST VIRGINIA':
            print("Deleting deprecated 'WEST VIRGINIA' from Firestore...")
            db.collection('markets').document(old_id).delete()

    # 2. Ensure all 64 local markets exist in Firestore
    print("\nEnsuring all 64 markets are synchronized to Firestore...")
    for market_name, market_data in local_markets.items():
        doc_ref = db.collection('markets').document(market_name)
        existing = doc_ref.get()
        if not existing.exists:
            print(f"Uploading missing market '{market_name}' to Firestore...")
            doc_ref.set(market_data)

    # 3. Verify final list in Firestore
    final_docs = list(db.collection('markets').stream())
    print(f"\nMigration complete! Total Firestore markets now: {len(final_docs)}")
    sample_names = sorted([d.id for d in final_docs])[:10]
    print(f"Sample market names in Firestore: {sample_names}")

if __name__ == '__main__':
    main()
