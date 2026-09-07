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
    "North Carolina Day": "/data-pengeluaran-togel-north-carolina-day/",
    "Magnum Cambodia": "/data-pengeluaran-togel-magnum-cambodia/",
    "Bullseye": "/data-pengeluaran-togel-bullseye/",
    "Sydney Lotto": "/data-pengeluaran-togel-sdlotto/",
    "Sydneypools": "/data-pengeluaran-togel-sydney-pools/",
    "Chinapools": "/data-pengeluaran-togel-chinapools/",
    "Japan": "/data-pengeluaran-togel-japan/",
    "SGP | Singapore": "/data-pengeluaran-togel-singapore/",
    "Taiwan": "/data-pengeluaran-togel-taiwan/",
    "Hongkong Pools": "/data-pengeluaran-togel-hongkong-pools/",
    "Hongkong Lotto": "/data-pengeluaran-togel-hklotto/",
    "Toto Macau 00": "/data-pengeluaran-togel-toto-macau-5/",
    "Georgia Midday": "/data-pengeluaran-togel-georgia-midday/",
    "Morocco Quatro 23:59 Wib": "/data-pengeluaran-togel-morocco-quatro-23-59-wib/",
    "New Jersey Midday": "/data-pengeluaran-togel-new-jersey-midday/",
    "Germany Plus5": "/data-pengeluaran-togel-germany-plus5/",
    "Indiana Midday": "/data-pengeluaran-togel-indiana-midday/",
    "Tennesse Midday": "/data-pengeluaran-togel-tennesse-midday/",
    "Kentucky Midday": "/data-pengeluaran-togel-kentucky-midday/",
    "Texas Day": "/data-pengeluaran-togel-texas-day/",
    "Florida Midday": "/data-pengeluaran-togel-florida-midday/",
    "Illinois Midday": "/data-pengeluaran-togel-illinois-midday/",
    "Missouri Midday": "/data-pengeluaran-togel-missouri-midday/",
    "Washington Dc Midday": "/data-pengeluaran-togel-washington-dc-midday/",
    "Connecticut Day": "/data-pengeluaran-togel-connecticut-day/",
    "Virginia Day": "/data-pengeluaran-togel-virginia-day/",
    "New York Midday": "/data-pengeluaran-togel-new-york-midday/",
    "Morocco Quatro 03:00 Wib": "/data-pengeluaran-togel-morocco-quatro-03-00-wib/",
    "Oregon 04:00 Wib": "/data-pengeluaran-togel-oregon-04-00-wib/",
    "Georgia Evening": "/data-pengeluaran-togel-georgia-evening/",
    "Oregon 07:00 Wib": "/data-pengeluaran-togel-oregon-07-00-wib/",
    "Texas Evening": "/data-pengeluaran-togel-texas-evening/",
    "Tennesse Evening": "/data-pengeluaran-togel-tennesse-evening/",
    "Michigan Evening": "/data-pengeluaran-togel-michigan-evening/",
    "Maryland Evening": "/data-pengeluaran-togel-maryland-evening/",
    "Washington Dc Evening": "/data-pengeluaran-togel-washington-dc-evening/",
    "California": "/data-pengeluaran-togel-california/",
    "Florida Evening": "/data-pengeluaran-togel-florida-evening/",
    "Missouri Evening": "/data-pengeluaran-togel-missouri-evening/",
    "Oregon 10:00 Wib": "/data-pengeluaran-togel-oregon-10-00-wib/",
    "Wisconsin Evening": "/data-pengeluaran-togel-wisconsin-evening/",
    "Illinois Evening": "/data-pengeluaran-togel-illinois-evening/",
    "Connecticut Night": "/data-pengeluaran-togel-connecticut-night/",
    "New York Evening": "/data-pengeluaran-togel-new-york-evening/",
    "Indiana Evening": "/data-pengeluaran-togel-indiana-evening/",
    "New Jersey Evening": "/data-pengeluaran-togel-new-jersey-evening/",
    "Kentucky Evening": "/data-pengeluaran-togel-kentucky-evening/",
    "Virginia Night": "/data-pengeluaran-togel-virginia-night/",
    "Texas Night": "/data-pengeluaran-togel-texas-night/",
    "North Carolina Evening": "/data-pengeluaran-togel-north-carolina-evening/",
    "Georgia Night": "/data-pengeluaran-togel-georgia-night/",
    "Oregon 13:00 Wib": "/data-pengeluaran-togel-oregon-13-00-wib/",
    "Toto Macau 13": "/data-pengeluaran-togel-toto-macau-1/",
    "Toto Macau 16": "/data-pengeluaran-togel-toto-macau-2/",
    "Morocco Quatro 18:00 Wib": "/data-pengeluaran-togel-morocco-quatro-18-00-wib/",
    "Toto Macau 19": "/data-pengeluaran-togel-toto-macau-3/",
    "Pcso": "/data-pengeluaran-togel-pcso/",
    "Morocco Quatro 21:00 Wib": "/data-pengeluaran-togel-morocco-quatro-21-00-wib/",
    "Texas Morning": "/data-pengeluaran-togel-texas-morning/",
    "Toto Macau 22": "/data-pengeluaran-togel-toto-macau-4/",
    "Tennesse Morning": "/data-pengeluaran-togel-tennesse-morning/",
    "Toto Macau 23": "/data-pengeluaran-togel-toto-macau-6/",
    "Maryland Midday": "/data-pengeluaran-togel-maryland-midday/",
    "Michigan Midday": "/data-pengeluaran-togel-michigan-midday/",
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
                            print(f"🎯 [SMART TUNE] {market_id}: AI={tuning_info.get('status_ai')} | BBFS={tuning_info.get('status_bbfs')} (Result: {tuning_info.get('actual_result')})")

                    # 2. Simpan / update ke collection 'markets'
                    if tuning_info.get('next_prediction'):
                        doc_payload['next_prediction'] = tuning_info['next_prediction']
                        doc_payload['last_audit'] = {
                            'status_ai': tuning_info.get('status_ai'),
                            'status_bbfs': tuning_info.get('status_bbfs'),
                            'actual_result': tuning_info.get('actual_result'),
                            'actual_2d': tuning_info.get('actual_2d'),
                            'is_twin': tuning_info.get('is_twin'),
                            'previous_prediction': tuning_info.get('previous_prediction'),
                            'ai_tuning': tuning_info.get('ai_tuning'),
                            'bbfs_tuning': tuning_info.get('bbfs_tuning')
                        }
                    elif existing_data.get('next_prediction'):
                        # Pertahankan prediksi dan audit yang sudah ada agar tidak terhapus saat tidak ada draw baru
                        doc_payload['next_prediction'] = existing_data['next_prediction']
                        if existing_data.get('last_audit'):
                            doc_payload['last_audit'] = existing_data['last_audit']
                    elif len(new_history) >= 15:
                        # Cold-start fallback jika dokumen baru pertama kali dibuat
                        initial_tune = engine.audit_and_tune(new_history, None)
                        if initial_tune and initial_tune.get('next_prediction'):
                            doc_payload['next_prediction'] = initial_tune['next_prediction']
                            doc_payload['last_audit'] = {
                                'status_ai': initial_tune.get('status_ai'),
                                'status_bbfs': initial_tune.get('status_bbfs'),
                                'actual_result': initial_tune.get('actual_result'),
                                'actual_2d': initial_tune.get('actual_2d'),
                                'is_twin': initial_tune.get('is_twin'),
                                'previous_prediction': initial_tune.get('previous_prediction'),
                                'ai_tuning': initial_tune.get('ai_tuning'),
                                'bbfs_tuning': initial_tune.get('bbfs_tuning')
                            }

                    db.collection('markets').document(market_id).set(doc_payload, merge=True)
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
