import requests
import re
import time
import random
import os
import json
import base64
import urllib3
from bs4 import BeautifulSoup
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
    "Morocco Quatro 18:00 Wib": "/data-pengeluaran-togel-morocco-quatro-18-00-wib/",
    "Pcso": "/data-pengeluaran-togel-pcso/",
    "Morocco Quatro 21:00 Wib": "/data-pengeluaran-togel-morocco-quatro-21-00-wib/",
    "Texas Morning": "/data-pengeluaran-togel-texas-morning/",
    "Tennesse Morning": "/data-pengeluaran-togel-tennesse-morning/",
    "Maryland Midday": "/data-pengeluaran-togel-maryland-midday/",
    "Michigan Midday": "/data-pengeluaran-togel-michigan-midday/",
}

SEJAHTERA_MARKETS = {
    "Mongolia": "https://sejahteramarah.com/mobile/togel/pasaran-18",
    "New Mexico Day": "https://sejahteramarah.com/mobile/togel/pasaran-78",
    "New Mexico Eve": "https://sejahteramarah.com/mobile/togel/pasaran-79",
    "Nusantara Pools": "https://sejahteramarah.com/mobile/togel/pasaran-22",
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
    "Mongolia": 65,
    "New Mexico Day": 66,
    "New Mexico Eve": 67,
    "Nusantara Pools": 68,
}

def stringify_keys(obj):
    """Memastikan seluruh key dalam dict adalah string murni (wajib untuk Firestore document paths)."""
    if isinstance(obj, dict):
        return {str(k): stringify_keys(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [stringify_keys(item) for item in obj]
    return obj

def init_firebase():
    """Inisialisasi koneksi Firebase Firestore dari Secrets atau File lokal."""
    sa_env = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_env:
        try:
            cred_dict = json.loads(sa_env)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            return firestore.client()
        except Exception:
            try:
                decoded = base64.b64decode(sa_env).decode("utf-8")
                cred_dict = json.loads(decoded)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                return firestore.client()
            except Exception as e:
                print(f"Gagal memuat kredensial dari FIREBASE_SERVICE_ACCOUNT: {e}")

    local_keys = ["firebase-key.json", "serviceAccountKey.json"]
    for key_file in local_keys:
        if os.path.exists(key_file):
            cred = credentials.Certificate(key_file)
            firebase_admin.initialize_app(cred)
            return firestore.client()

    print("PERINGATAN: Kredensial Firebase tidak ditemukan. Berjalan dalam mode DRY-RUN (tidak menyimpan ke DB).")
    return None

def scrape_market(url):
    """Scrape data pengeluaran dari server paito standar."""
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

        return ' '.join(results)
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ''

def scrape_sejahtera_market(url, existing_history_str=""):
    """Scrape pasaran dari Sejahtera (sejahteramarah.com) secara incremental atau full."""
    days = "Senin|Selasa|Rabu|Kamis|Jumat|Sabtu|Minggu"
    date_pat = r"\d{1,2}/\d{1,2}/\d{4}"
    pattern = rf"(?:{days})\s+({date_pat})\s+(\d)\s+(\d)\s+(\d)\s+(\d)"
    fallback = rf"({date_pat})\s+(\d)\s+(\d)\s+(\d)\s+(\d)"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; Mobile) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://sejahteramarah.com/",
    }

    # Jika sudah ada existing_history, scrape 3 halaman terdepan saja untuk update harian
    pages_to_fetch = 3 if existing_history_str else 35
    all_draws = []
    seen_dates = set()

    for page in range(1, pages_to_fetch + 1):
        page_url = url if page <= 1 else f"{url}?page={page}"
        try:
            r = requests.get(page_url, headers=headers, timeout=20, verify=False)
            if not r.ok:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            if not matches:
                matches = re.findall(fallback, text, flags=re.IGNORECASE)
            if not matches:
                break

            for date_str, d1, d2, d3, d4 in matches:
                if date_str not in seen_dates:
                    seen_dates.add(date_str)
                    all_draws.append(d1 + d2 + d3 + d4)
        except Exception as e:
            print(f"Error scraping Sejahtera page {page}: {e}")
            break

    new_reversed = list(reversed(all_draws))
    if not existing_history_str:
        return " ".join(new_reversed)

    existing = [x for x in existing_history_str.strip().split() if len(x) == 4 and x.isdigit()]
    if not existing:
        return " ".join(new_reversed)

    merged = merge_histories(existing, new_reversed)
    return " ".join(merged)

def merge_histories(existing_draws, scraped_draws):
    """
    Menggabungkan riwayat yang sudah ada di database dengan hasil scrap terbaru secara akumulatif.
    Data historis lama tidak pernah dihapus/dipotong (riwayat terus bertambah > 500 putaran).
    """
    valid_existing = [d for d in existing_draws if len(d) == 4 and d.isdigit()]
    valid_scraped = [d for d in scraped_draws if len(d) == 4 and d.isdigit()]

    if not valid_existing:
        return valid_scraped
    if not valid_scraped:
        return valid_existing

    last_known = valid_existing[-1]
    if last_known in valid_scraped:
        last_idx = len(valid_scraped) - 1 - valid_scraped[::-1].index(last_known)
        fresh = valid_scraped[last_idx + 1:]
        if fresh:
            return valid_existing + fresh
        return valid_existing

    # Cek overlap sub-sequence jika website hanya memuat potongan parsial
    for k in range(min(len(valid_existing), 30), 0, -1):
        suffix = valid_existing[-k:]
        for j in range(len(valid_scraped) - k + 1):
            if valid_scraped[j:j+k] == suffix:
                fresh = valid_scraped[j+k:]
                if fresh:
                    return valid_existing + fresh
                return valid_existing

    # Fallback: jika draw terbaru di website berbeda dengan draw terakhir yang tersimpan
    if valid_scraped[-1] != valid_existing[-1]:
        return valid_existing + [valid_scraped[-1]]

    return valid_existing

def sync_market_data(db, market_id, data, current_order):
    """Fungsi pembantu sinkronisasi, diffing, auto-tuning, dan penyimpanan akumulatif ke Firestore."""
    doc_payload = {
        'id': market_id,
        'name': market_id,
        'history_data': data,
        'order': current_order,
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }

    if db is not None:
        try:
            existing_doc = db.collection('markets').document(market_id).get()
            existing_data = existing_doc.to_dict() if existing_doc.exists else {}
            existing_history = [x for x in existing_data.get('history_data', '').split() if len(x) == 4 and x.isdigit()]
            scraped_history = [x for x in data.split() if len(x) == 4 and x.isdigit()]

            merged_history = merge_histories(existing_history, scraped_history)
            merged_history_str = " ".join(merged_history)
            doc_payload['history_data'] = merged_history_str

            is_new_draw = (
                len(merged_history) > 0 and
                (len(existing_history) == 0 or merged_history[-1] != existing_history[-1])
            )

            tuning_info = {}
            if is_new_draw and len(merged_history) >= 15:
                tuning_info = engine.audit_and_tune(merged_history, existing_data.get('next_prediction'))
                if tuning_info:
                    log_payload = {
                        'market_id': market_id,
                        'market_name': market_id,
                        'date': time.strftime('%Y-%m-%d', time.gmtime()),
                        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                        **tuning_info
                    }
                    db.collection('tuning_logs').add(stringify_keys(log_payload))
                    print(f"🎯 [SMART TUNE] {market_id}: AI={tuning_info.get('status_ai')} | BBFS={tuning_info.get('status_bbfs')} (Result: {tuning_info.get('actual_result')} | Total: {len(merged_history)} draws)")

            if tuning_info.get('next_prediction'):
                doc_payload['next_prediction'] = tuning_info['next_prediction']
                doc_payload['last_audit'] = {
                    'status_ai': tuning_info.get('status_ai'),
                    'status_bbfs': tuning_info.get('status_bbfs'),
                    'actual_result': tuning_info.get('actual_result'),
                    'actual_2d': tuning_info.get('actual_2d'),
                    'is_twin': tuning_info.get('is_twin'),
                    'paito_audit': tuning_info.get('paito_audit'),
                    'previous_prediction': tuning_info.get('previous_prediction'),
                    'ai_tuning': tuning_info.get('ai_tuning'),
                    'bbfs_tuning': tuning_info.get('bbfs_tuning')
                }
            elif existing_data.get('next_prediction'):
                doc_payload['next_prediction'] = existing_data['next_prediction']
                if existing_data.get('last_audit'):
                    doc_payload['last_audit'] = existing_data['last_audit']
            elif len(merged_history) >= 15:
                initial_tune = engine.audit_and_tune(merged_history, None)
                if initial_tune and initial_tune.get('next_prediction'):
                    doc_payload['next_prediction'] = initial_tune['next_prediction']
                    doc_payload['last_audit'] = {
                        'status_ai': initial_tune.get('status_ai'),
                        'status_bbfs': initial_tune.get('status_bbfs'),
                        'actual_result': initial_tune.get('actual_result'),
                        'actual_2d': initial_tune.get('actual_2d'),
                        'is_twin': initial_tune.get('is_twin'),
                        'paito_audit': initial_tune.get('paito_audit'),
                        'previous_prediction': initial_tune.get('previous_prediction'),
                        'ai_tuning': initial_tune.get('ai_tuning'),
                        'bbfs_tuning': initial_tune.get('bbfs_tuning')
                    }

            clean_doc = stringify_keys(doc_payload)
            db.collection('markets').document(market_id).set(clean_doc, merge=True)
            print(f"OK (Saved to Firebase): {market_id}")
            return True
        except Exception as err:
            import traceback
            print(f"ERR (Firebase save failed for {market_id}): {err}")
            traceback.print_exc()
            return False
    else:
        print(f"OK (Dry-run, scraped {len(data.split())} numbers): {market_id}")
        return True

def main():
    db = init_firebase()
    next_order = 11
    success = 0
    errors = 0

    total_all = len(MARKETS) + len(SEJAHTERA_MARKETS)
    print(f"Memulai scraping {total_all} pasaran ({len(MARKETS)} standar + {len(SEJAHTERA_MARKETS)} Sejahtera)...\n")

    # 1. Scrape Pasaran Server Standar
    for market_id, url in MARKETS.items():
        data = scrape_market(url)
        if data:
            current_order = PRIORITY_ORDER.get(market_id, next_order)
            if market_id not in PRIORITY_ORDER:
                next_order += 1
            if sync_market_data(db, market_id, data, current_order):
                success += 1
            else:
                errors += 1
        else:
            print(f"SKIP: {market_id} (data kosong / gagal koneksi)")
            errors += 1

        delay = random.uniform(1.0, 2.5)
        time.sleep(delay)

    # 2. Scrape Pasaran Sejahtera (Mongolia, New Mexico Day, New Mexico Eve)
    for market_id, url in SEJAHTERA_MARKETS.items():
        existing_history = ""
        if db is not None:
            try:
                ed = db.collection('markets').document(market_id).get()
                if ed.exists:
                    existing_history = ed.to_dict().get('history_data', '')
            except Exception:
                pass

        data = scrape_sejahtera_market(url, existing_history)
        if data:
            current_order = PRIORITY_ORDER.get(market_id, next_order)
            if market_id not in PRIORITY_ORDER:
                next_order += 1
            if sync_market_data(db, market_id, data, current_order):
                success += 1
            else:
                errors += 1
        else:
            print(f"SKIP: {market_id} (data kosong Sejahtera)")
            errors += 1

        delay = random.uniform(1.0, 2.0)
        time.sleep(delay)

    print(f"\nSelesai: {success} OK, {errors} skip/error")

if __name__ == "__main__":
    main()
