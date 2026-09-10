import sys
import os
import requests
import re
import time
import random
import json
import base64
import urllib3
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import engine

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

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

RAJAPAITO_MARKETS = {
    "Macau P1": "https://w2.rajapaito1.net/data-togel-macau-p1/",
    "Macau P2": "https://w2.rajapaito1.net/data-togel-macau-p2/",
    "Macau P3": "https://w2.rajapaito1.net/data-togel-macau-p3/",
    "Macau P4": "https://w2.rajapaito1.net/data-togel-macau-p4/",
    "Macau P5": "https://w2.rajapaito1.net/data-togel-macau-p5/",
    "Macau P6": "https://w2.rajapaito1.net/data-togel-macau-p6/",
    "Pennsylvania Day": "https://w2.rajapaito1.net/data-togel-pennsylvania-day/",
    "Pennsylvania Evening": "https://w2.rajapaito1.net/data-togel-pennsylvania-evening/",
    "Delaware Day": "https://w2.rajapaito1.net/data-togel-delaware-day/",
    "Delaware Night": "https://w2.rajapaito1.net/data-togel-delaware-night/",
    "Ohio Midday": "https://w2.rajapaito1.net/data-togel-ohio-midday/",
    "Ohio Evening": "https://w2.rajapaito1.net/data-togel-ohio-evening/",
    "West Virginia": "https://w2.rajapaito1.net/data-togel-west-virginia/",
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
    "Macau P1": 11,
    "Macau P2": 12,
    "Macau P3": 13,
    "Macau P4": 14,
    "Macau P5": 15,
    "Macau P6": 16,
    "Pennsylvania Day": 27,
    "Pennsylvania Evening": 28,
    "Delaware Day": 29,
    "Delaware Night": 30,
    "Ohio Midday": 31,
    "Ohio Evening": 32,
    "West Virginia": 33,
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

def get_market_days_schema(market_id=""):
    """Mengembalikan pola urutan hari per baris mingguan untuk pasaran tertentu."""
    mid = market_id.lower()
    if 'sgp' in mid or 'singapore' in mid:
        return ["Senin", "Rabu", "Kamis", "Sabtu", "Minggu"]
    elif 'pcso' in mid:
        return ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]
    else:
        # Standar pasaran harian 7 hari (HK, Sydney, Cambodia, US pools, dll)
        return ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

def scrape_market(url, market_id=""):
    """Scrape data pengeluaran dan hari dari server paito standar."""
    try:
        res = requests.get(
            BASE + url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15,
            verify=False
        )
        html = res.text

        soup = BeautifulSoup(html, 'html.parser')
        container = soup.find(class_='paito-text-container')
        days_schema = get_market_days_schema(market_id)

        results = []
        days = []

        if container:
            lines = container.find_all(class_='paito-line')
            for line in lines:
                items = line.find_all(class_='paito-row-item')
                for col_idx, item in enumerate(items):
                    val = item.get_text().strip()
                    # Hanya ambil jika digit 4 angka valid (abaikan 'xxxx' untuk putaran belum buka)
                    if re.fullmatch(r'\d{4}', val):
                        results.append(val)
                        day_name = days_schema[col_idx % len(days_schema)]
                        days.append(day_name)
        else:
            # Fallback jika struktur container tidak ditemukan
            start_idx = html.find('Tema Terang')
            end_idx = html.find('RESET')
            if start_idx != -1 and end_idx != -1:
                section = html[start_idx:end_idx]
                digits = re.findall(r'class="paito-digit">(\d)</span>', section)
                for i in range(0, len(digits) - 3, 4):
                    d4 = digits[i] + digits[i+1] + digits[i+2] + digits[i+3]
                    results.append(d4)
                    days.append(days_schema[(len(results) - 1) % len(days_schema)])

        return ' '.join(results), ' '.join(days)
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return '', ''

def scrape_sejahtera_market(url, existing_history_str="", existing_days_str=""):
    """Scrape pasaran dari Sejahtera (sejahteramarah.com) secara incremental atau full dengan hari."""
    days_pattern = "Senin|Selasa|Rabu|Kamis|Jumat|Sabtu|Minggu"
    date_pat = r"\d{1,2}/\d{1,2}/\d{4}"
    pattern = rf"({days_pattern})\s+({date_pat})\s+(\d)\s+(\d)\s+(\d)\s+(\d)"
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
    all_days = []
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
            if matches:
                for day_str, date_str, d1, d2, d3, d4 in matches:
                    if date_str not in seen_dates:
                        seen_dates.add(date_str)
                        all_draws.append(d1 + d2 + d3 + d4)
                        all_days.append(day_str.capitalize())
            else:
                fallback_matches = re.findall(fallback, text, flags=re.IGNORECASE)
                if not fallback_matches:
                    break
                for date_str, d1, d2, d3, d4 in fallback_matches:
                    if date_str not in seen_dates:
                        seen_dates.add(date_str)
                        all_draws.append(d1 + d2 + d3 + d4)
                        all_days.append("Senin")
        except Exception as e:
            print(f"Error scraping Sejahtera page {page}: {e}")
            break

    new_draws_reversed = list(reversed(all_draws))
    new_days_reversed = list(reversed(all_days))

    if not existing_history_str:
        return " ".join(new_draws_reversed), " ".join(new_days_reversed)

    existing_draws = [x for x in existing_history_str.strip().split() if len(x) == 4 and x.isdigit()]
    existing_days = existing_days_str.strip().split() if existing_days_str else []

    merged_draws, merged_days = merge_histories_with_days(
        existing_draws, existing_days, new_draws_reversed, new_days_reversed
    )
    return " ".join(merged_draws), " ".join(merged_days)

def scrape_rajapaito_market(url):
    """Scrape data pengeluaran dari server Rajapaito secara penuh (tanpa limit pemotongan)."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        res = requests.get(url, headers=headers, timeout=25, verify=False)
        res.raise_for_status()

        soup = BeautifulSoup(res.text, "html.parser")
        table = soup.select_one("table.keluaran-table") or soup.find("table")
        if not table:
            return ""

        results = []
        for row in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
            if not cells:
                continue
            row_text = " ".join(cells).upper()
            if "TAHUN" in row_text or any(day in row_text for day in ["SENIN", "SELASA", "RABU", "KAMIS", "JUMAT", "SABTU", "MINGGU"]):
                continue
            for cell in cells:
                val = cell.strip()
                if re.fullmatch(r"\d{4}", val):
                    results.append(val)

        cleaned = []
        for item in results:
            if not cleaned or cleaned[-1] != item:
                cleaned.append(item)

        return " ".join(cleaned)
    except Exception as e:
        print(f"Error scraping Rajapaito {url}: {e}")
        return ""

def merge_histories_with_days(existing_draws, existing_days, scraped_draws, scraped_days, days_schema=None):
    """
    Menggabungkan riwayat angka dan hari secara dua arah (bidirectional)
    dengan sinkronisasi 1-to-1 yang presisi untuk paito.
    """
    if days_schema is None:
        days_schema = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

    valid_existing = [d for d in existing_draws if len(d) == 4 and d.isdigit()]
    valid_scraped = [d for d in scraped_draws if len(d) == 4 and d.isdigit()]

    # Pastikan existing_days selaras panjangnya dengan valid_existing
    aligned_existing_days = list(existing_days)
    while len(aligned_existing_days) < len(valid_existing):
        idx = len(aligned_existing_days)
        aligned_existing_days.append(days_schema[idx % len(days_schema)])

    aligned_scraped_days = list(scraped_days)
    while len(aligned_scraped_days) < len(valid_scraped):
        idx = len(aligned_scraped_days)
        aligned_scraped_days.append(days_schema[idx % len(days_schema)])

    if not valid_existing:
        return valid_scraped, aligned_scraped_days
    if not valid_scraped:
        return valid_existing, aligned_existing_days

    # 1. Cari titik temu awal (alignment start)
    window_size = min(len(valid_existing), 20)
    found_start_idx = -1
    for k in range(window_size, 4, -1):
        sample = valid_existing[:k]
        for i in range(len(valid_scraped) - k + 1):
            if valid_scraped[i:i+k] == sample:
                found_start_idx = i
                break
        if found_start_idx != -1:
            break

    if found_start_idx != -1:
        older_draws = valid_scraped[:found_start_idx]
        older_days = aligned_scraped_days[:found_start_idx]

        combined_draws = older_draws + valid_existing
        combined_days = older_days + aligned_existing_days

        last_known = combined_draws[-1]
        if last_known in valid_scraped:
            last_idx = len(valid_scraped) - 1 - valid_scraped[::-1].index(last_known)
            newer_draws = valid_scraped[last_idx + 1:]
            newer_days = aligned_scraped_days[last_idx + 1:]
            combined_draws = combined_draws + newer_draws
            combined_days = combined_days + newer_days
        return combined_draws, combined_days

    # 2. Cari titik temu akhir (alignment tail)
    for k in range(window_size, 4, -1):
        sample = valid_existing[-k:]
        for i in range(len(valid_scraped) - k + 1):
            if valid_scraped[i:i+k] == sample:
                newer_draws = valid_scraped[i+k:]
                newer_days = aligned_scraped_days[i+k:]
                return valid_existing + newer_draws, aligned_existing_days + newer_days

    # Fallback: jika scraped memuat overlap parsial
    for k in range(min(len(valid_existing), 10), 2, -1):
        sample = valid_existing[-k:]
        for i in range(len(valid_scraped) - k + 1):
            if valid_scraped[i:i+k] == sample:
                return valid_existing + valid_scraped[i+k:], aligned_existing_days + aligned_scraped_days[i+k:]

    # Fallback umum: jika scraped lebih lengkap
    if len(valid_scraped) > len(valid_existing):
        return valid_scraped, aligned_scraped_days
    return valid_existing, aligned_existing_days

def merge_histories(existing_draws, scraped_draws):
    """Fungsi pembungkus kompatibilitas backward lama."""
    draws, _ = merge_histories_with_days(existing_draws, [], scraped_draws, [])
    return draws

def sync_market_data(db, market_id, data, current_order, days_data=""):
    """Fungsi pembantu sinkronisasi, diffing, auto-tuning, dan penyimpanan akumulatif ke Firestore."""
    days_schema = get_market_days_schema(market_id)
    doc_payload = {
        'id': market_id,
        'name': market_id,
        'history_data': data,
        'history_days': days_data,
        'order': current_order,
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }

    if db is not None:
        try:
            existing_doc = db.collection('markets').document(market_id).get()
            existing_data = existing_doc.to_dict() if existing_doc.exists else {}
            existing_history = [x for x in existing_data.get('history_data', '').split() if len(x) == 4 and x.isdigit()]
            existing_days = existing_data.get('history_days', '').split() if existing_data.get('history_days') else []

            scraped_history = [x for x in data.split() if len(x) == 4 and x.isdigit()]
            scraped_days = days_data.split() if days_data else []

            merged_history, merged_days = merge_histories_with_days(
                existing_history, existing_days, scraped_history, scraped_days, days_schema
            )
            merged_history_str = " ".join(merged_history)
            merged_days_str = " ".join(merged_days)
            doc_payload['history_data'] = merged_history_str
            doc_payload['history_days'] = merged_days_str

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
                    print(f"[SMART TUNE] {market_id}: AI={tuning_info.get('status_ai')} | BBFS={tuning_info.get('status_bbfs')} (Result: {tuning_info.get('actual_result')} | Total: {len(merged_history)} draws)")

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
            print(f"OK (Saved to Firebase): {market_id} ({len(existing_history)} -> {len(merged_history)} draws with days)")
            return True
        except Exception as err:
            import traceback
            print(f"ERR (Firebase save failed for {market_id}): {err}")
            traceback.print_exc()
            return False
    else:
        print(f"OK (Dry-run, scraped {len(data.split())} numbers, {len(days_data.split())} days): {market_id}")
        return True

def main():
    db = init_firebase()
    next_order = 17
    success = 0
    errors = 0

    total_all = len(MARKETS) + len(SEJAHTERA_MARKETS) + len(RAJAPAITO_MARKETS)
    print(f"Memulai scraping {total_all} pasaran ({len(MARKETS)} standar + {len(SEJAHTERA_MARKETS)} Sejahtera + {len(RAJAPAITO_MARKETS)} Rajapaito)...\n")

    # 1. Scrape Pasaran Server Standar
    for market_id, url in MARKETS.items():
        data, days = scrape_market(url, market_id)
        if data:
            current_order = PRIORITY_ORDER.get(market_id, next_order)
            if market_id not in PRIORITY_ORDER:
                next_order += 1
            if sync_market_data(db, market_id, data, current_order, days):
                success += 1
            else:
                errors += 1
        else:
            print(f"SKIP: {market_id} (data kosong / gagal koneksi)")
            errors += 1

        delay = random.uniform(1.0, 2.5)
        time.sleep(delay)

    # 2. Scrape Pasaran Sejahtera (Mongolia, New Mexico Day, New Mexico Eve, Nusantara Pools)
    for market_id, url in SEJAHTERA_MARKETS.items():
        existing_history = ""
        existing_days = ""
        if db is not None:
            try:
                ed = db.collection('markets').document(market_id).get()
                if ed.exists:
                    d = ed.to_dict()
                    existing_history = d.get('history_data', '')
                    existing_days = d.get('history_days', '')
            except Exception:
                pass

        data, days = scrape_sejahtera_market(url, existing_history, existing_days)
        if data:
            current_order = PRIORITY_ORDER.get(market_id, next_order)
            if market_id not in PRIORITY_ORDER:
                next_order += 1
            if sync_market_data(db, market_id, data, current_order, days):
                success += 1
            else:
                errors += 1
        else:
            print(f"SKIP: {market_id} (data kosong Sejahtera)")
            errors += 1

        delay = random.uniform(1.0, 2.0)
        time.sleep(delay)

    # 3. Scrape Pasaran Rajapaito (Macau P1-P6, Pennsylvania, Delaware, Ohio)
    for market_id, url in RAJAPAITO_MARKETS.items():
        data = scrape_rajapaito_market(url)
        if data:
            current_order = PRIORITY_ORDER.get(market_id, next_order)
            if market_id not in PRIORITY_ORDER:
                next_order += 1
            if sync_market_data(db, market_id, data, current_order, ""):
                success += 1
            else:
                errors += 1
        else:
            print(f"SKIP: {market_id} (data kosong Rajapaito)")
            errors += 1

        delay = random.uniform(1.0, 2.0)
        time.sleep(delay)

    print(f"\nSelesai: {success} OK, {errors} skip/error")

if __name__ == "__main__":
    main()
