import sys
import os
import requests
import re
import time
import random
import json
import base64
import urllib3
from datetime import datetime
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
import engine

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

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
    "Magnum Cambodia": 1, "Sydneypools": 2, "Sydney Lotto": 3, "Chinapools": 4,
    "Japan": 5, "SGP | Singapore": 6, "Pcso": 7, "Taiwan": 8,
    "Hongkong Pools": 9, "Hongkong Lotto": 10,
    "Macau P1": 11, "Macau P2": 12, "Macau P3": 13, "Macau P4": 14,
    "Macau P5": 15, "Macau P6": 16,
    "Pennsylvania Day": 27, "Pennsylvania Evening": 28,
    "Delaware Day": 29, "Delaware Night": 30,
    "Ohio Midday": 31, "Ohio Evening": 32, "West Virginia": 33,
    "Mongolia": 65, "New Mexico Day": 66, "New Mexico Eve": 67, "Nusantara Pools": 68,
}


def stringify_keys(obj):
    if isinstance(obj, dict):
        return {str(k): stringify_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [stringify_keys(item) for item in obj]
    return obj


def prediction_state_matches_history(prediction, history):
    """True hanya untuk state engine aktif yang dibangun dari history saat ini."""
    if not isinstance(prediction, dict) or not history:
        return False
    try:
        basis_count = int(prediction.get('basis_draw_count', -1))
    except (TypeError, ValueError):
        return False
    return (
        prediction.get('engine_version') == engine.ENGINE_VERSION
        and basis_count == len(history)
        and prediction.get('basis_last_draw') == history[-1]
    )


def init_firebase():
    sa_env = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if sa_env:
        try:
            cred = credentials.Certificate(json.loads(sa_env))
            firebase_admin.initialize_app(cred)
            return firestore.client()
        except Exception:
            try:
                decoded = base64.b64decode(sa_env).decode("utf-8")
                cred = credentials.Certificate(json.loads(decoded))
                firebase_admin.initialize_app(cred)
                return firestore.client()
            except Exception as e:
                print(f"Gagal memuat kredensial dari FIREBASE_SERVICE_ACCOUNT: {e}")

    for key_file in ("firebase-key.json", "serviceAccountKey.json"):
        if os.path.exists(key_file):
            cred = credentials.Certificate(key_file)
            firebase_admin.initialize_app(cred)
            return firestore.client()

    print("PERINGATAN: Kredensial Firebase tidak ditemukan. Mode DRY-RUN.")
    return None


DAY_NAMES_ID = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")


def _weekday_from_ddmmyyyy(date_str):
    """Ubah tanggal dd/mm/yyyy menjadi nama hari Indonesia."""
    try:
        weekday = datetime.strptime(date_str, "%d/%m/%Y").weekday()
        return DAY_NAMES_ID[weekday]
    except (TypeError, ValueError):
        return ""


def _is_valid_day(value):
    return value in DAY_NAMES_ID


def get_market_days_schema(market_id=""):
    mid = market_id.lower()
    if 'sgp' in mid or 'singapore' in mid:
        return ["Senin", "Rabu", "Kamis", "Sabtu", "Minggu"]
    if 'pcso' in mid:
        return ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]
    return ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def scrape_market(url, market_id=""):
    try:
        res = requests.get(
            BASE + url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15,
            verify=False,
        )
        soup = BeautifulSoup(res.text, 'html.parser')
        container = soup.find(class_='paito-text-container')
        schema = get_market_days_schema(market_id)
        results, days = [], []

        if container:
            for line in container.find_all(class_='paito-line'):
                for col_idx, item in enumerate(line.find_all(class_='paito-row-item')):
                    val = item.get_text().strip()
                    if re.fullmatch(r'\d{4}', val):
                        results.append(val)
                        days.append(schema[col_idx % len(schema)])
        else:
            html = res.text
            start_idx, end_idx = html.find('Tema Terang'), html.find('RESET')
            if start_idx != -1 and end_idx != -1:
                digits = re.findall(r'class="paito-digit">(\d)</span>', html[start_idx:end_idx])
                for i in range(0, len(digits) - 3, 4):
                    results.append(''.join(digits[i:i + 4]))
                    days.append(schema[(len(results) - 1) % len(schema)])
        return ' '.join(results), ' '.join(days)
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return '', ''


def scrape_sejahtera_market(url, existing_history_str="", existing_days_str=""):
    days_pattern = "Senin|Selasa|Rabu|Kamis|Jumat|Sabtu|Minggu"
    date_pat = r"\d{1,2}/\d{1,2}/\d{4}"
    pattern = rf"({days_pattern})\s+({date_pat})\s+(\d)\s+(\d)\s+(\d)\s+(\d)"
    fallback = rf"({date_pat})\s+(\d)\s+(\d)\s+(\d)\s+(\d)"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 Chrome/121.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://sejahteramarah.com/",
    }
    pages_to_fetch = 3 if existing_history_str else 35
    all_draws, all_days, seen_dates = [], [], set()

    for page in range(1, pages_to_fetch + 1):
        page_url = url if page <= 1 else f"{url}?page={page}"
        try:
            r = requests.get(page_url, headers=headers, timeout=20, verify=False)
            if not r.ok:
                break
            text = re.sub(r"\s+", " ", BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True))
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
                        all_days.append(_weekday_from_ddmmyyyy(date_str))
        except Exception as e:
            print(f"Error scraping Sejahtera page {page}: {e}")
            break

    new_draws = list(reversed(all_draws))
    new_days = list(reversed(all_days))
    if not existing_history_str:
        return " ".join(new_draws), " ".join(new_days)

    existing = [x for x in existing_history_str.strip().split() if len(x) == 4 and x.isdigit()]
    existing_days = existing_days_str.strip().split() if existing_days_str else []
    merged, merged_days = merge_histories_with_days(existing, existing_days, new_draws, new_days)
    return " ".join(merged), " ".join(merged_days)


def scrape_rajapaito_market(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
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
                    # Jangan dedup berdasarkan nilai. Dua draw berturut-turut boleh identik.
                    results.append(val)
        return " ".join(results)
    except Exception as e:
        print(f"Error scraping Rajapaito {url}: {e}")
        return ""


def _align_days(days, draws, schema):
    aligned = list(days[:len(draws)])
    while len(aligned) < len(draws):
        aligned.append(schema[len(aligned) % len(schema)])
    return aligned


def _best_sequence_alignment(existing, scraped, min_overlap=3):
    """Cari offset chronology dengan exact match, lalu fuzzy match ber-confidence tinggi.

    Fuzzy alignment hanya dipakai untuk menerima koreksi historis kecil pada offset yang
    didukung banyak draw identik. Tanpa anchor kuat, caller wajib mempertahankan existing.
    """
    best_exact = None
    best_fuzzy = None
    for offset in range(-len(scraped) + 1, len(existing)):
        s_start = max(0, -offset)
        s_end = min(len(scraped), len(existing) - offset)
        overlap = s_end - s_start
        if overlap < min_overlap:
            continue

        matches = sum(
            1 for idx in range(s_start, s_end)
            if existing[idx + offset] == scraped[idx]
        )
        mismatches = overlap - matches
        if mismatches == 0:
            candidate = (overlap, offset, 'exact')
            if best_exact is None or overlap > best_exact[0]:
                best_exact = candidate
            continue

        # Koreksi kecil: minimal 5 anchor cocok dan mismatch sangat terbatas.
        max_mismatches = max(1, overlap // 40)
        ratio = matches / overlap
        if overlap >= 6 and matches >= 5 and ratio >= 0.90 and mismatches <= max_mismatches:
            candidate = (matches, overlap, offset, 'fuzzy')
            if best_fuzzy is None or candidate[:2] > best_fuzzy[:2]:
                best_fuzzy = candidate

    exact_overlap = best_exact[0] if best_exact is not None else -1
    fuzzy_overlap = best_fuzzy[1] if best_fuzzy is not None else -1

    # Pilih alignment dengan bukti chronology terluas. Exact menang saat coverage
    # setara, tetapi exact tail pendek tidak boleh menutupi fuzzy alignment panjang
    # yang hanya berbeda pada koreksi historis kecil.
    if best_exact is not None and exact_overlap >= fuzzy_overlap:
        return best_exact
    if best_fuzzy is not None:
        _, overlap, offset, mode = best_fuzzy
        return overlap, offset, mode
    return None


def merge_histories_with_days(existing_draws, existing_days, scraped_draws, scraped_days, days_schema=None):
    """Gabung chronology tanpa menganggap nilai 4D unik.

    Alignment dipilih berdasarkan seluruh urutan yang overlap. Ini aman ketika draw
    yang sama (mis. 1234) muncul dua kali atau bahkan berturut-turut.
    """
    schema = days_schema or ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    existing = [d for d in existing_draws if len(d) == 4 and d.isdigit()]
    scraped = [d for d in scraped_draws if len(d) == 4 and d.isdigit()]
    e_days = _align_days(existing_days, existing, schema)
    s_days = _align_days(scraped_days, scraped, schema)
    raw_scraped_days = list(scraped_days[:len(scraped)])

    if not existing:
        return scraped, s_days
    if not scraped:
        return existing, e_days

    alignment = _best_sequence_alignment(existing, scraped, min_overlap=3)
    if alignment:
        _, offset, mode = alignment
        start = min(0, offset)
        end = max(len(existing), offset + len(scraped))
        merged, merged_days = [], []
        for coord in range(start, end):
            e_idx = coord
            s_idx = coord - offset
            has_existing = 0 <= e_idx < len(existing)
            has_scraped = 0 <= s_idx < len(scraped)
            if has_existing and has_scraped:
                # Pada fuzzy alignment, perbedaan kecil dianggap koreksi dari source terbaru.
                if mode == 'fuzzy' and existing[e_idx] != scraped[s_idx]:
                    merged.append(scraped[s_idx])
                else:
                    merged.append(existing[e_idx])
                # Hari dari source scrape terbaru lebih otoritatif pada area overlap.
                # Jika source tidak menyediakan hari valid (mis. Rajapaito), pertahankan existing.
                scraped_day = raw_scraped_days[s_idx] if s_idx < len(raw_scraped_days) else ""
                merged_days.append(scraped_day if _is_valid_day(scraped_day) else e_days[e_idx])
            elif has_existing:
                merged.append(existing[e_idx])
                merged_days.append(e_days[e_idx])
            elif has_scraped:
                merged.append(scraped[s_idx])
                merged_days.append(s_days[s_idx])
        return merged, merged_days

    # Tidak ada anchor sequence yang cukup kuat. Mempertahankan existing lebih aman
    # daripada mengganti seluruh chronology hanya karena scraped kebetulan lebih panjang.
    return existing, e_days


def merge_histories(existing_draws, scraped_draws):
    draws, _ = merge_histories_with_days(existing_draws, [], scraped_draws, [])
    return draws


def sync_market_data(db, market_id, data, current_order, days_data=""):
    days_schema = get_market_days_schema(market_id)
    doc_payload = {
        'id': market_id,
        'name': market_id,
        'history_data': data,
        'history_days': days_data,
        'order': current_order,
        'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }

    if db is None:
        print(f"OK (Dry-run, scraped {len(data.split())} numbers, {len(days_data.split())} days): {market_id}")
        return True

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
        doc_payload['history_data'] = " ".join(merged_history)
        doc_payload['history_days'] = " ".join(merged_days)

        # Hanya history yang sudah pernah tersimpan boleh menghasilkan event new-draw.
        # Initial import adalah warm-start, bukan audit periode production.
        had_prior_history = bool(existing_history)
        is_new_draw = had_prior_history and len(merged_history) > len(existing_history)
        history_corrected = (had_prior_history and not is_new_draw and merged_history != existing_history)
        correction_prediction = None
        if history_corrected:
            # Correction/re-alignment is not a new period, so do not create a tuning log.
            # Rebuild only the forward prediction from corrected history so stale state
            # is never carried into the next real draw.
            print(f"[MERGE] {market_id}: history corrected/re-aligned; rebuilding prediction state")
            if len(merged_history) >= 15:
                rebuilt_state = engine.audit_and_tune(merged_history, None)
                if rebuilt_state:
                    correction_prediction = rebuilt_state.get('next_prediction')

        existing_prediction = existing_data.get('next_prediction')
        needs_state_migration = (
            len(merged_history) >= 15
            and not is_new_draw
            and not history_corrected
            and not prediction_state_matches_history(existing_prediction, merged_history)
        )
        migration_prediction = None
        if needs_state_migration:
            print(
                f"[MIGRATE] {market_id}: rebuilding prediction state for "
                f"engine {engine.ENGINE_VERSION}"
            )
            rebuilt_state = engine.audit_and_tune(merged_history, None)
            if rebuilt_state:
                migration_prediction = rebuilt_state.get('next_prediction')

        tuning_info = {}
        if is_new_draw and len(merged_history) >= 15:
            tuning_info = engine.audit_and_tune(merged_history, existing_data.get('next_prediction'))
            if tuning_info:
                log_payload = {
                    'market_id': market_id,
                    'market_name': market_id,
                    'date': time.strftime('%Y-%m-%d', time.gmtime()),
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    **tuning_info,
                }
                db.collection('tuning_logs').add(stringify_keys(log_payload))
                print(
                    f"[SMART TUNE] {market_id}: AI={tuning_info.get('status_ai')} | "
                    f"BBFS={tuning_info.get('status_bbfs')} "
                    f"(Result: {tuning_info.get('actual_result')} | Total: {len(merged_history)} draws)"
                )

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
                'bbfs_tuning': tuning_info.get('bbfs_tuning'),
            }
        elif history_corrected:
            if correction_prediction:
                doc_payload['next_prediction'] = correction_prediction
            else:
                doc_payload['next_prediction'] = firestore.DELETE_FIELD
            # Audit lama tidak lagi dapat dianggap cocok dengan history yang dikoreksi.
            doc_payload['last_audit'] = firestore.DELETE_FIELD
        elif needs_state_migration:
            if migration_prediction:
                doc_payload['next_prediction'] = migration_prediction
            else:
                doc_payload['next_prediction'] = firestore.DELETE_FIELD
            # Audit dari engine/schema lama tidak boleh ditampilkan sebagai audit engine aktif.
            doc_payload['last_audit'] = firestore.DELETE_FIELD
        elif existing_prediction:
            doc_payload['next_prediction'] = existing_prediction
            if existing_data.get('last_audit'):
                doc_payload['last_audit'] = existing_data['last_audit']
        elif len(merged_history) >= 15:
            # Warm-start hanya membentuk state ke depan. Rekonstruksi historis bukan audit production.
            initial_tune = engine.audit_and_tune(merged_history, None)
            if initial_tune and initial_tune.get('next_prediction'):
                doc_payload['next_prediction'] = initial_tune['next_prediction']
                doc_payload['last_audit'] = firestore.DELETE_FIELD

        db.collection('markets').document(market_id).set(stringify_keys(doc_payload), merge=True)
        print(f"OK (Saved to Firebase): {market_id} ({len(existing_history)} -> {len(merged_history)} draws with days)")
        return True
    except Exception as err:
        import traceback
        print(f"ERR (Firebase save failed for {market_id}): {err}")
        traceback.print_exc()
        return False


def main():
    db = init_firebase()
    next_order = 17
    success = errors = 0
    total_all = len(MARKETS) + len(SEJAHTERA_MARKETS) + len(RAJAPAITO_MARKETS)
    print(f"Memulai scraping {total_all} pasaran ({len(MARKETS)} standar + {len(SEJAHTERA_MARKETS)} Sejahtera + {len(RAJAPAITO_MARKETS)} Rajapaito)...\n")

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
        time.sleep(random.uniform(1.0, 2.5))

    for market_id, url in SEJAHTERA_MARKETS.items():
        existing_history = existing_days = ""
        if db is not None:
            try:
                ed = db.collection('markets').document(market_id).get()
                if ed.exists:
                    old = ed.to_dict()
                    existing_history = old.get('history_data', '')
                    existing_days = old.get('history_days', '')
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
        time.sleep(random.uniform(1.0, 2.0))

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
        time.sleep(random.uniform(1.0, 2.0))

    print(f"\nSelesai: {success} OK, {errors} skip/error")


if __name__ == "__main__":
    main()
