import requests
import re
import time
import random
import os
import json
import base64
import urllib3
import firebase_admin
from firebase_admin import credentials, firestore
import engine

# Nonaktifkan warning SSL karena server paito menggunakan sertifikat self-signed/khusus
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://159.65.133.131"

MARKETS = {
    "MAGNUM CAMBODIA": "/data-pengeluaran-togel-magnum-cambodia/",
    "BULLSEYE": "/data-pengeluaran-togel-bullseye/",
    "SYDNEY LOTTO": "/data-pengeluaran-togel-sdlotto/",
    "SYDNEY POOLS": "/data-pengeluaran-togel-sydney-pools/",
    "CHINA POOLS": "/data-pengeluaran-togel-chinapools/",
    "JAPAN": "/data-pengeluaran-togel-japan/",
    "SINGAPORE": "/data-pengeluaran-togel-singapore/",
    "TAIWAN": "/data-pengeluaran-togel-taiwan/",
    "HONGKONG POOLS": "/data-pengeluaran-togel-hongkong-pools/",
    "HONGKONG LOTTO": "/data-pengeluaran-togel-hklotto/",
    "MARYLAND MIDDAY": "/data-pengeluaran-togel-maryland-midday/",
    "GEORGIA MIDDAY": "/data-pengeluaran-togel-georgia-midday/",
    "MOROCCO 23:59": "/data-pengeluaran-togel-morocco-quatro-23-59-wib/",
    "MICHIGAN MIDDAY": "/data-pengeluaran-togel-michigan-midday/",
    "NEW JERSEY MIDDAY": "/data-pengeluaran-togel-new-jersey-midday/",
    "GERMANY PLUS5": "/data-pengeluaran-togel-germany-plus5/",
    "INDIANA MIDDAY": "/data-pengeluaran-togel-indiana-midday/",
    "TENNESSE MIDDAY": "/data-pengeluaran-togel-tennesse-midday/",
    "KENTUCKY MID": "/data-pengeluaran-togel-kentucky-midday/",
    "TEXAS DAY": "/data-pengeluaran-togel-texas-day/",
    "FLORIDA MID": "/data-pengeluaran-togel-florida-midday/",
    "ILLINOIS MIDDAY": "/data-pengeluaran-togel-illinois-midday/",
    "MISSOURI MIDDAY": "/data-pengeluaran-togel-missouri-midday/",
    "WASHINGTON DC MIDDAY": "/data-pengeluaran-togel-washington-dc-midday/",
    "CONNECTICUT DAY": "/data-pengeluaran-togel-connecticut-day/",
    "VIRGINIA DAY": "/data-pengeluaran-togel-virginia-day/",
    "NEW YORK MID": "/data-pengeluaran-togel-new-york-midday/",
    "MOROCCO 03:00": "/data-pengeluaran-togel-morocco-quatro-03-00-wib/",
    "CAROLINA DAY": "/data-pengeluaran-togel-north-carolina-day/",
    "OREGON 4": "/data-pengeluaran-togel-oregon-04-00-wib/",
    "WEST VIRGINIA": "/data-pengeluaran-togel-west-virginia/",
    "GEORGIA EVE": "/data-pengeluaran-togel-georgia-evening/",
    "OREGON 7": "/data-pengeluaran-togel-oregon-07-00-wib/",
    "TEXAS EVE": "/data-pengeluaran-togel-texas-evening/",
    "TENNESSE EVE": "/data-pengeluaran-togel-tennesse-evening/",
    "MICHIGAN EVE": "/data-pengeluaran-togel-michigan-evening/",
    "MARYLAND EVE": "/data-pengeluaran-togel-maryland-evening/",
    "WASHINGTON DC EVE": "/data-pengeluaran-togel-washington-dc-evening/",
    "CALIFORNIA": "/data-pengeluaran-togel-california/",
    "FLORIDA EVE": "/data-pengeluaran-togel-florida-evening/",
    "MISSOURI EVE": "/data-pengeluaran-togel-missouri-evening/",
    "OREGON 10": "/data-pengeluaran-togel-oregon-10-00-wib/",
    "WISCONSIN EVE": "/data-pengeluaran-togel-wisconsin-evening/",
    "ILLINOIS EVE": "/data-pengeluaran-togel-illinois-evening/",
    "CONNECTICUT NIGHT": "/data-pengeluaran-togel-connecticut-night/",
    "NEW YORK EVE": "/data-pengeluaran-togel-new-york-evening/",
    "INDIANA EVE": "/data-pengeluaran-togel-indiana-evening/",
    "NEW JERSEY EVE": "/data-pengeluaran-togel-new-jersey-evening/",
    "KENTUCKY EVE": "/data-pengeluaran-togel-kentucky-evening/",
    "VIRGINIA NIGHT": "/data-pengeluaran-togel-virginia-night/",
    "TEXAS NIGHT": "/data-pengeluaran-togel-texas-night/",
    "CAROLINA EVE": "/data-pengeluaran-togel-north-carolina-evening/",
    "GEORGIA NIGHT": "/data-pengeluaran-togel-georgia-night/",
    "OREGON 13": "/data-pengeluaran-togel-oregon-13-00-wib/",
    "MOROCCO 18:00": "/data-pengeluaran-togel-morocco-quatro-18-00-wib/",
    "PCSO": "/data-pengeluaran-togel-pcso/",
    "MOROCCO 21:00": "/data-pengeluaran-togel-morocco-quatro-21-00-wib/",
    "TEXAS MORNING": "/data-pengeluaran-togel-texas-morning/",
}

PRIORITY_ORDER = {
    "MAGNUM CAMBODIA": 1,
    "SYDNEY POOLS": 2,
    "SYDNEY LOTTO": 3,
    "CHINA POOLS": 4,
    "JAPAN": 5,
    "SINGAPORE": 6,
    "PCSO": 7,
    "TAIWAN": 8,
    "HONGKONG POOLS": 9,
    "HONGKONG LOTTO": 10,
}

def init_firebase():
    """Inisialisasi koneksi Firebase Firestore dari Secrets atau File lokal."""
    # 1. Cek dari environment variable (GitHub Secrets atau env local)
    sa_env = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_env:
        try:
            # Coba parse sebagai raw JSON
            cred_dict = json.loads(sa_env)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            return firestore.client()
        except Exception:
            # Coba decode jika base64
            try:
                decoded = base64.b64decode(sa_env).decode("utf-8")
                cred_dict = json.loads(decoded)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                return firestore.client()
            except Exception as e:
                print(f"Gagal memuat kredensial dari FIREBASE_SERVICE_ACCOUNT: {e}")

    # 2. Cek file lokal standar
    local_keys = ["firebase-key.json", "serviceAccountKey.json"]
    for key_file in local_keys:
        if os.path.exists(key_file):
            cred = credentials.Certificate(key_file)
            firebase_admin.initialize_app(cred)
            return firestore.client()

    print("PERINGATAN: Kredensial Firebase tidak ditemukan. Berjalan dalam mode DRY-RUN (tidak menyimpan ke DB).")
    return None

def scrape_market(url):
    """Scrape data pengeluaran dari URL paito."""
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

        # Ambil maksimal 500 result terakhir
        return ' '.join(results[-500:])
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ''

def main():
    db = init_firebase()
    
    next_order = 11
    success = 0
    errors = 0

    print(f"Memulai scraping {len(MARKETS)} pasaran...\n")

    for market_id, url in MARKETS.items():
        data = scrape_market(url)
        if data:
            current_order = PRIORITY_ORDER.get(market_id, next_order)
            if market_id not in PRIORITY_ORDER:
                next_order += 1

            doc_payload = {
                'id': market_id,
                'name': market_id,
                'history_data': data,
                'order': current_order,
                'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }

            if db is not None:
                try:
                    # 1. Cek diffing: Apakah ada result baru yang belum tercatat?
                    existing_doc = db.collection('markets').document(market_id).get()
                    existing_data = existing_doc.to_dict() if existing_doc.exists else {}
                    existing_history = existing_data.get('history_data', '').split()
                    new_history = data.split()

                    is_new_draw = (
                        len(new_history) > 0 and
                        (len(existing_history) == 0 or new_history[-1] != existing_history[-1])
                    )

                    tuning_info = {}
                    if is_new_draw and len(new_history) >= 15:
                        # Jalankan Auto-Tuning Cerdas & Audit membandingkan prediksi kemarin
                        tuning_info = engine.audit_and_tune(new_history, existing_data.get('next_prediction'))
                        if tuning_info:
                            log_payload = {
                                'market_id': market_id,
                                'market_name': market_id,
                                'date': time.strftime('%Y-%m-%d', time.gmtime()),
                                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                **tuning_info
                            }
                            # Simpan snapshot tuning permanen ke koleksi 'tuning_logs'
                            db.collection('tuning_logs').add(log_payload)
                            print(f"🎯 [SMART TUNE] {market_id}: {tuning_info['status_ai']} (Result: {tuning_info['actual_result']})")

                    # 2. Simpan / update ke collection 'markets'
                    if tuning_info.get('next_prediction'):
                        doc_payload['next_prediction'] = tuning_info['next_prediction']
                        doc_payload['last_audit'] = {
                            'status_ai': tuning_info.get('status_ai'),
                            'status_bbfs': tuning_info.get('status_bbfs'),
                            'actual_result': tuning_info.get('actual_result')
                        }

                    db.collection('markets').document(market_id).set(doc_payload)
                    print(f"OK (Saved to Firebase): {market_id}")
                except Exception as err:
                    print(f"ERR (Firebase save failed for {market_id}): {err}")
            else:
                print(f"OK (Dry-run, scraped {len(data.split())} numbers): {market_id}")

            success += 1
        else:
            print(f"SKIP: {market_id} (data kosong / gagal koneksi)")
            errors += 1

        delay = random.uniform(1.5, 3.0)
        time.sleep(delay)

    print(f"\nSelesai: {success} OK, {errors} skip/error")

if __name__ == "__main__":
    main()
