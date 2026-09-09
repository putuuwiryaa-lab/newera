"""
Modul Engine Adaptif & Auto-Tuning untuk Scraper Backend (Python)
Menjalankan audit tebakan, penalti/reward, dan prediksi periode berikutnya.
"""

import math
import itertools
from collections import defaultdict
from typing import List, Dict, Tuple

INDEX_MAP = {0: 5, 1: 6, 2: 7, 3: 8, 4: 9, 5: 0, 6: 1, 7: 2, 8: 3, 9: 4}
MISTIK_LAMA = {0: 1, 1: 0, 2: 5, 3: 8, 4: 7, 5: 2, 6: 9, 7: 4, 8: 3, 9: 6}
MISTIK_BARU = {0: 8, 1: 7, 2: 6, 3: 9, 4: 5, 5: 4, 6: 2, 7: 1, 8: 0, 9: 3}


def get_momentum_scores(history_2d: List[Tuple[int, int]], window_size: int = 20, decay: float = 0.08) -> Dict[int, float]:
    scores = {d: 0.0 for d in range(10)}
    sub_hist = history_2d[-window_size:]
    n = len(sub_hist)
    for idx, (k, e) in enumerate(sub_hist):
        weight = math.exp(decay * (idx - n + 1))
        scores[k] += weight
        scores[e] += weight
    return scores


def get_markov_scores(history_2d: List[Tuple[int, int]], lookback: int = 150) -> Dict[int, float]:
    scores = {d: 0.0 for d in range(10)}
    if len(history_2d) < 2:
        return scores

    sub_hist = history_2d[-lookback:]
    last_k, last_e = sub_hist[-1]
    trans_k = defaultdict(int)
    trans_e = defaultdict(int)

    for i in range(len(sub_hist) - 1):
        pk, pe = sub_hist[i]
        nk, ne = sub_hist[i + 1]
        if pk == last_k:
            trans_k[nk] += 1
        if pe == last_e:
            trans_e[ne] += 1

    for d in range(10):
        scores[d] = float(trans_k[d] + trans_e[d])
    return scores


def get_delta_scores(history_2d: List[Tuple[int, int]], window_size: int = 15) -> Dict[int, float]:
    scores = {d: 0.0 for d in range(10)}
    if len(history_2d) < 2:
        return scores

    sub_hist = history_2d[-window_size:]
    last_k, last_e = sub_hist[-1]
    delta_counts = defaultdict(int)

    for i in range(len(sub_hist) - 1):
        pk, pe = sub_hist[i]
        nk, ne = sub_hist[i + 1]
        dk = (nk - pk) % 10
        de = (ne - pe) % 10
        delta_counts[dk] += 1
        delta_counts[de] += 1

    for delta, count in delta_counts.items():
        proj_k = (last_k + delta) % 10
        proj_e = (last_e + delta) % 10
        scores[proj_k] += count * 1.0
        scores[proj_e] += count * 1.0

    return scores


def get_mistik_scores(history_2d: List[Tuple[int, int]], eval_window: int = 15) -> Dict[int, float]:
    scores = {d: 0.0 for d in range(10)}
    if len(history_2d) < 3:
        return scores

    sub_hist = history_2d[-eval_window:]
    branch_hits = {"asli": 1, "indeks": 1, "mistik_lama": 1, "mistik_baru": 1}

    for i in range(len(sub_hist) - 1):
        pk, pe = sub_hist[i]
        actual_set = set(sub_hist[i + 1])
        for d in set([pk, pe]):
            if d in actual_set:
                branch_hits["asli"] += 1
            if INDEX_MAP.get(d) in actual_set:
                branch_hits["indeks"] += 1
            if MISTIK_LAMA.get(d) in actual_set:
                branch_hits["mistik_lama"] += 1
            if MISTIK_BARU.get(d) in actual_set:
                branch_hits["mistik_baru"] += 1

    last_k, last_e = sub_hist[-1]
    for d in set([last_k, last_e]):
        scores[d] += branch_hits["asli"]
        scores[INDEX_MAP[d]] += branch_hits["indeks"]
        scores[MISTIK_LAMA[d]] += branch_hits["mistik_lama"]
        scores[MISTIK_BARU[d]] += branch_hits["mistik_baru"]

    return scores


def rank_digits(history_2d: List[Tuple[int, int]], rolling_window: int = 20, tier_size: int = 4, custom_weights: Dict[str, float] = None) -> Tuple[List[int], Dict[str, float]]:
    methods = {
        "Momentum": lambda h: get_momentum_scores(h),
        "Markov": lambda h: get_markov_scores(h),
        "Delta": lambda h: get_delta_scores(h),
        "Mistik": lambda h: get_mistik_scores(h)
    }

    if custom_weights and len(custom_weights) > 0:
        # ATURAN ENGINE: Jika prediksi masuk (FREEZE) atau sudah dikalibrasi,
        # TIDAK PERLU hitung bobot dari awal! Langsung pertahankan bobot pemenang.
        weights = {k: float(v) for k, v in custom_weights.items()}
    else:
        # HANYA 1x dihitung saat inisialisasi awal (cold-start / pertama kali)
        weights = {"Momentum": 1.0, "Markov": 1.0, "Delta": 1.0, "Mistik": 1.0}

        if len(history_2d) > rolling_window + 5:
            total_len = len(history_2d)
            start_idx = total_len - rolling_window
            for m_name, m_func in methods.items():
                hit_count = 0
                for target_idx in range(start_idx, total_len):
                    hist_until = history_2d[:target_idx]
                    actual_next = set(history_2d[target_idx])
                    m_scores = m_func(hist_until)
                    top_candidates = sorted(m_scores.keys(), key=lambda d: m_scores[d], reverse=True)[:tier_size]
                    if any(d in actual_next for d in top_candidates):
                        hit_count += 1
                weights[m_name] = max(0.5, float(hit_count + 1))

    combined = {d: 0.0 for d in range(10)}
    for m_name, m_func in methods.items():
        w = weights[m_name]
        raw = m_func(history_2d)
        max_s = max(raw.values()) if raw.values() and max(raw.values()) > 0 else 1.0
        for d in range(10):
            combined[d] += w * (raw[d] / max_s)

    ranked = sorted(combined.keys(), key=lambda d: combined[d], reverse=True)
    return ranked, weights


def compute_bbfs_tier_factor_weights(history_2d: List[Tuple[int, int]], eval_window: int = 15) -> Dict[int, Dict[str, float]]:
    """Menghitung bobot empiris 4 faktor BBFS spesifik per-tier (6, 7, 8, 9)."""
    sub = history_2d[-eval_window:]
    base_priors = {
        6: {'Densitas Pasangan': 10.0, 'Transisi Markov': 8.0, 'Momentum Posisi': 6.0, 'Coverage Proteksi': 4.0},
        7: {'Densitas Pasangan': 8.0, 'Transisi Markov': 8.0, 'Momentum Posisi': 7.0, 'Coverage Proteksi': 7.0},
        8: {'Densitas Pasangan': 7.0, 'Transisi Markov': 6.0, 'Momentum Posisi': 8.0, 'Coverage Proteksi': 9.0},
        9: {'Densitas Pasangan': 5.0, 'Transisi Markov': 5.0, 'Momentum Posisi': 8.0, 'Coverage Proteksi': 12.0}
    }
    tier_weights = {sz: dict(base_priors[sz]) for sz in [6, 7, 8, 9]}
    if len(sub) < 3:
        return tier_weights

    for i in range(len(sub) - 1):
        prev_k, prev_e = sub[i]
        act_k, act_e = sub[i + 1]

        hist_so_far = sub[:i + 1]
        had_direct_pair = any((k == act_k and e == act_e) or (k == act_e and e == act_k) for k, e in hist_so_far)
        had_markov = any((sub[j][0] == prev_k and sub[j + 1][0] == act_k) or (sub[j][1] == prev_e and sub[j + 1][1] == act_e) for j in range(i))
        recent5 = sub[max(0, i - 4):i + 1]
        had_momentum = any(k in (act_k, act_e) or e in (act_k, act_e) for k, e in recent5)

        for sz in [6, 7, 8, 9]:
            if had_direct_pair:
                tier_weights[sz]['Densitas Pasangan'] += 1.0 if sz == 6 else (0.8 if sz == 7 else 0.6)
            if had_markov:
                tier_weights[sz]['Transisi Markov'] += 0.9 if sz == 6 else (0.8 if sz == 7 else 0.5)
            if had_momentum:
                tier_weights[sz]['Momentum Posisi'] += 1.0 if sz >= 8 else 0.7
            tier_weights[sz]['Coverage Proteksi'] += 1.2 if sz == 9 else (0.9 if sz == 8 else 0.4)

    for sz in [6, 7, 8, 9]:
        tier_weights[sz] = {k: round(v, 1) for k, v in tier_weights[sz].items()}
    return tier_weights


def compute_dedicated_bbfs(history_2d: List[Tuple[int, int]], lookback: int = 50, custom_tier_factor_weights: Dict = None):
    """
    ENGINE KHUSUS BBFS 2D BELAKANG:
    Menghitung optimasi joint-pair coverage dengan bobot 4 komponen yang independen per-tier (6, 7, 8, 9).
    """
    base_weights = compute_bbfs_tier_factor_weights(history_2d)
    tier_factor_weights = dict(base_weights)
    if custom_tier_factor_weights:
        tier_factor_weights.update(custom_tier_factor_weights)

    sub = history_2d[-lookback:]
    n = len(sub)
    if n < 2:
        return {
            6: list(range(6)),
            7: list(range(7)),
            8: list(range(8)),
            9: list(range(9))
        }, [8, 9], list(range(10)), tier_factor_weights

    k_scores = defaultdict(float)
    e_scores = defaultdict(float)
    pair_matrix = [[0.0 for _ in range(10)] for _ in range(10)]
    last_k, last_e = sub[-1]
    k_trans = defaultdict(float)
    e_trans = defaultdict(float)

    for i in range(n - 1):
        pk, pe = sub[i]
        nk, ne = sub[i + 1]
        if pk == last_k:
            k_trans[nk] += 1.0
        if pe == last_e:
            e_trans[ne] += 1.0

    for idx, (k, e) in enumerate(sub):
        decay = math.exp(0.05 * (idx - n + 1))
        k_scores[k] += decay
        e_scores[e] += decay
        pair_matrix[k][e] += 2.0 * decay
        pair_matrix[e][k] += 1.2 * decay

    res = {}
    for size in [6, 7, 8, 9]:
        w = tier_factor_weights[size]
        total_w = sum(w.values()) or 1.0
        norm_w = {k: (v / total_w) * 4.0 for k, v in w.items()}

        joint_size = [[0.0 for _ in range(10)] for _ in range(10)]
        for k in range(10):
            for e in range(10):
                pos_pot = (k_scores[k] + k_trans[k] * 1.5) * (e_scores[e] + e_trans[e] * 1.5)
                pair_pot = pair_matrix[k][e] * 3.0
                cov_pot = (k_scores[k] + e_scores[e]) * 0.8
                trans_pot = (k_trans[k] * e_trans[e] * 2.0)
                joint_size[k][e] = (
                    norm_w['Densitas Pasangan'] * pair_pot +
                    norm_w['Transisi Markov'] * trans_pot +
                    norm_w['Momentum Posisi'] * pos_pot +
                    norm_w['Coverage Proteksi'] * cov_pot
                )

        best_score = -1.0
        best_comb = None
        for comb in itertools.combinations(range(10), size):
            s = set(comb)
            score = sum(joint_size[k][e] for k in s for e in s if k != e)
            if score > best_score:
                best_score = score
                best_comb = comb
        s = set(best_comb)
        digit_contrib = {d: sum(joint_size[d][x] + joint_size[x][d] for x in s if x != d) for d in s}
        res[size] = sorted(best_comb, key=lambda d: digit_contrib[d], reverse=True)

    base_joint = [[(k_scores[k] + k_trans[k] * 1.5) * (e_scores[e] + e_trans[e] * 1.5) + (pair_matrix[k][e] * 3.0) for e in range(10)] for k in range(10)]
    bbfs_digit_scores = {d: sum(base_joint[d][x] + base_joint[x][d] for x in range(10) if x != d) for d in range(10)}
    bbfs_ranked = sorted(bbfs_digit_scores.keys(), key=lambda d: bbfs_digit_scores[d], reverse=True)
    dead_digits = bbfs_ranked[-2:]

    return res, dead_digits, bbfs_ranked, tier_factor_weights


def generate_smart_trim(bbfs7_digits: List[int]) -> Dict[str, List[str]]:
    """Memilah kombinasi 2D BBFS-7 ke dalam Top 10 BOM, Medium 15, dan Cadangan."""
    top4 = bbfs7_digits[:4]
    top10 = [f"{a}{b}" for a in top4 for b in top4 if a != b][:10]
    top5 = bbfs7_digits[:5]
    all_top5 = [f"{a}{b}" for a in top5 for b in top5 if a != b]
    medium15 = [l for l in all_top5 if l not in top10][:15]
    top7 = bbfs7_digits[:7]
    all_top7 = [f"{a}{b}" for a in top7 for b in top7 if a != b]
    used = set(top10 + medium15)
    cadangan = [l for l in all_top7 if l not in used]
    return {"top10": top10, "medium15": medium15, "cadangan": cadangan}


# ==============================================================================
# 5. SHIO 2026 (TAHUN KUDA API / FIRE HORSE) & BIJI
# ==============================================================================
SHIO_2026_DATA = [
    {"no": 1, "name": "Kuda", "emoji": "🐴", "jalur": 1, "numbers": ["01", "13", "25", "37", "49", "61", "73", "85", "97"]},
    {"no": 2, "name": "Ular", "emoji": "🐍", "jalur": 2, "numbers": ["02", "14", "26", "38", "50", "62", "74", "86", "98"]},
    {"no": 3, "name": "Naga", "emoji": "🐲", "jalur": 3, "numbers": ["03", "15", "27", "39", "51", "63", "75", "87", "99"]},
    {"no": 4, "name": "Kelinci", "emoji": "🐇", "jalur": 1, "numbers": ["00", "04", "16", "28", "40", "52", "64", "76", "88"]},
    {"no": 5, "name": "Harimau", "emoji": "🐯", "jalur": 2, "numbers": ["05", "17", "29", "41", "53", "65", "77", "89"]},
    {"no": 6, "name": "Kerbau", "emoji": "🐂", "jalur": 3, "numbers": ["06", "18", "30", "42", "54", "66", "78", "90"]},
    {"no": 7, "name": "Tikus", "emoji": "🐀", "jalur": 1, "numbers": ["07", "19", "31", "43", "55", "67", "79", "91"]},
    {"no": 8, "name": "Babi", "emoji": "🐷", "jalur": 2, "numbers": ["08", "20", "32", "44", "56", "68", "80", "92"]},
    {"no": 9, "name": "Anjing", "emoji": "🐶", "jalur": 3, "numbers": ["09", "21", "33", "45", "57", "69", "81", "93"]},
    {"no": 10, "name": "Ayam", "emoji": "🐔", "jalur": 1, "numbers": ["10", "22", "34", "46", "58", "70", "82", "94"]},
    {"no": 11, "name": "Monyet", "emoji": "🐵", "jalur": 2, "numbers": ["11", "23", "35", "47", "59", "71", "83", "95"]},
    {"no": 12, "name": "Kambing", "emoji": "🐐", "jalur": 3, "numbers": ["12", "24", "36", "48", "60", "72", "84", "96"]},
]

NUM_TO_SHIO_2026 = {}
for s_item in SHIO_2026_DATA:
    for n_str in s_item["numbers"]:
        NUM_TO_SHIO_2026[n_str] = s_item

def get_shio_2026(val_2d) -> Dict:
    if isinstance(val_2d, int):
        val_str = f"{val_2d:02d}"
    else:
        val_str = str(val_2d).zfill(2)

    if val_str in NUM_TO_SHIO_2026:
        return NUM_TO_SHIO_2026[val_str]

    try:
        val = int(val_str)
    except:
        return SHIO_2026_DATA[0]

    if val == 0:
        val = 100
    rem = val % 12
    if rem == 0:
        rem = 12
    return SHIO_2026_DATA[rem - 1]


def compute_biji(k: int, e: int) -> int:
    """Hitung Biji 2D (Digital Root): penjumlahan berulang Kepala + Ekor hingga 1 digit (0-9)."""
    if k == 0 and e == 0:
        return 0
    s = k + e
    while s >= 10:
        s = (s // 10) + (s % 10)
    return s


def generate_sniper_trim(digits: List[int], paito_pred: Dict, include_twins: bool = False) -> Dict:
    """
    Pemangkas Sniper 2D Berbasis Paito:
    Menyaring baris BBFS menggunakan irisan Top 3 Biji, Pola Paritas Utama, dan Shio 2026.
    """
    lines = []
    unique_digits = list(dict.fromkeys(digits))
    for i in range(len(unique_digits)):
        for j in range(len(unique_digits)):
            if i == j:
                if include_twins:
                    lines.append(f"{unique_digits[i]}{unique_digits[j]}")
            else:
                lines.append(f"{unique_digits[i]}{unique_digits[j]}")

    top_biji_set = set(paito_pred.get("top_biji", []))
    top_shio_set = set(paito_pred.get("top_shios", []))
    primary_parity = paito_pred.get("primary_parity", "")

    def get_parity(k: int, e: int) -> str:
        kp = "Genap" if k % 2 == 0 else "Ganjil"
        ep = "Genap" if e % 2 == 0 else "Ganjil"
        return f"{kp}-{ep}"

    sniper_top = []
    sniper_secondary = []
    super_sniper_shio = []
    cadangan = []

    for l in lines:
        k = int(l[0])
        e = int(l[1])
        biji = compute_biji(k, e)
        parity = get_parity(k, e)
        shio_obj = get_shio_2026(k * 10 + e)

        hit_biji = biji in top_biji_set
        hit_parity = (parity == primary_parity)
        hit_shio = shio_obj["no"] in top_shio_set

        if hit_biji and hit_parity:
            sniper_top.append(l)
            if hit_shio:
                super_sniper_shio.append(l)
        elif hit_biji:
            sniper_secondary.append(l)
        else:
            cadangan.append(l)

    kept_count = len(super_sniper_shio) if len(super_sniper_shio) > 0 else (len(sniper_top) if len(sniper_top) > 0 else len(sniper_secondary))
    efficiency_pct = round(((len(lines) - kept_count) / len(lines)) * 100) if lines else 0

    return {
        "sniper_top": sniper_top,
        "sniper_secondary": sniper_secondary,
        "super_sniper_shio": super_sniper_shio,
        "cadangan": cadangan,
        "efficiency_pct": efficiency_pct
    }


def predict_paito_macro(history_2d: List[Tuple[int, int]], lookback: int = 50) -> Dict:
    """
    Prediksi Makro Paito:
    1. Biji 2D (Markov transition, recency momentum, overdue gap tracker)
    2. Pola Ganjil-Genap (4-state Markov, streak & overdue alert)
    3. Kategori Besar-Kecil (2-state Markov & rolling bias)
    4. Shio 2026 (Tahun Kuda Api: 12 Shio Markov, Recency Decay, 3 Jalur & Overdue Gap Tracker)
    """
    if not history_2d:
        return {
            "top_biji": [1, 2, 3],
            "biji_probabilities": {str(d): 0.1 for d in range(10)},
            "primary_parity": "Genap-Ganjil",
            "parity_probabilities": {"Genap-Genap": 0.25, "Genap-Ganjil": 0.25, "Ganjil-Genap": 0.25, "Ganjil-Ganjil": 0.25},
            "primary_magnitude": "Kecil",
            "magnitude_probabilities": {"Besar": 0.5, "Kecil": 0.5},
            "top_shios": [1, 2, 3],
            "primary_jalur": 1,
            "shio_probabilities": {str(s): 0.083 for s in range(1, 13)},
            "jalur_probabilities": {"1": 0.334, "2": 0.333, "3": 0.333},
            "overdue_shios": [],
            "overdue_alerts": [],
            "confidence_score": 60
        }

    sub = history_2d[-lookback:]

    # 1. Analisis Biji 2D
    biji_history = [compute_biji(k, e) for k, e in sub]
    last_biji = biji_history[-1]

    # Transisi Markov Biji
    biji_trans = defaultdict(float)
    for i in range(len(biji_history) - 1):
        if biji_history[i] == last_biji:
            biji_trans[biji_history[i + 1]] += 1.0

    # Recency Decay Momentum
    biji_momentum = defaultdict(float)
    for idx, b in enumerate(biji_history):
        decay = math.exp(0.06 * (idx - len(biji_history) + 1))
        biji_momentum[b] += decay

    # Gap / Overdue Tracker Biji
    biji_gap = {d: 0 for d in range(10)}
    for d in range(10):
        found = False
        for step, b in enumerate(reversed(biji_history)):
            if b == d:
                biji_gap[d] = step
                found = True
                break
        if not found:
            biji_gap[d] = len(biji_history)

    # Skor gabungan Biji (Momentum + Markov + Mean Reversion jika gap >= 12)
    biji_scores = {}
    for d in range(10):
        m_score = biji_momentum[d]
        t_score = biji_trans[d] * 1.5
        gap_bonus = 1.2 if biji_gap[d] >= 12 else 0.0
        biji_scores[d] = m_score + t_score + gap_bonus

    tot_biji_score = sum(biji_scores.values()) or 1.0
    biji_probs = {d: round(biji_scores[d] / tot_biji_score, 3) for d in range(10)}
    ranked_biji = sorted(range(10), key=lambda d: biji_scores[d], reverse=True)
    top_biji = ranked_biji[:3]

    # 2. Analisis Ganjil-Genap (4 Kuadran: GG, GJ, JG, JJ)
    PARITY_STATES = ["Genap-Genap", "Genap-Ganjil", "Ganjil-Genap", "Ganjil-Ganjil"]
    def get_parity(k: int, e: int) -> str:
        kp = "Genap" if k % 2 == 0 else "Ganjil"
        ep = "Genap" if e % 2 == 0 else "Ganjil"
        return f"{kp}-{ep}"

    parity_history = [get_parity(k, e) for k, e in sub]
    last_parity = parity_history[-1]

    parity_trans = defaultdict(float)
    for i in range(len(parity_history) - 1):
        if parity_history[i] == last_parity:
            parity_trans[parity_history[i + 1]] += 1.0

    parity_momentum = defaultdict(float)
    for idx, p in enumerate(parity_history):
        decay = math.exp(0.08 * (idx - len(parity_history) + 1))
        parity_momentum[p] += decay

    # Gap Tracker Parity
    parity_gap = {p: 0 for p in PARITY_STATES}
    for p in PARITY_STATES:
        found = False
        for step, val in enumerate(reversed(parity_history)):
            if val == p:
                parity_gap[p] = step
                found = True
                break
        if not found:
            parity_gap[p] = len(parity_history)

    parity_scores = {}
    for p in PARITY_STATES:
        reversion = 1.5 if parity_gap[p] >= 8 else 0.0
        parity_scores[p] = parity_momentum[p] + parity_trans[p] * 2.0 + reversion

    tot_parity = sum(parity_scores.values()) or 1.0
    parity_probs = {p: round(parity_scores[p] / tot_parity, 3) for p in PARITY_STATES}
    primary_parity = max(PARITY_STATES, key=lambda p: parity_scores[p])

    # 3. Analisis Kategori Besar-Kecil (2D: >= 50 Besar, < 50 Kecil)
    magnitude_history = ["Besar" if (k * 10 + e) >= 50 else "Kecil" for k, e in sub]
    last_mag = magnitude_history[-1]

    mag_trans = defaultdict(float)
    for i in range(len(magnitude_history) - 1):
        if magnitude_history[i] == last_mag:
            mag_trans[magnitude_history[i + 1]] += 1.0

    mag_momentum = defaultdict(float)
    for idx, m in enumerate(magnitude_history):
        decay = math.exp(0.08 * (idx - len(magnitude_history) + 1))
        mag_momentum[m] += decay

    mag_scores = {
        "Besar": mag_momentum["Besar"] + mag_trans["Besar"] * 1.5,
        "Kecil": mag_momentum["Kecil"] + mag_trans["Kecil"] * 1.5
    }
    tot_mag = sum(mag_scores.values()) or 1.0
    mag_probs = {m: round(mag_scores[m] / tot_mag, 3) for m in ["Besar", "Kecil"]}
    primary_magnitude = "Besar" if mag_scores["Besar"] >= mag_scores["Kecil"] else "Kecil"

    # 4. Analisis Shio 2026 (Tahun Kuda Api)
    shio_history = [get_shio_2026(k * 10 + e)["no"] for k, e in sub]
    last_shio = shio_history[-1]

    shio_trans = defaultdict(float)
    for i in range(len(shio_history) - 1):
        if shio_history[i] == last_shio:
            shio_trans[shio_history[i + 1]] += 1.0

    shio_momentum = defaultdict(float)
    for idx, s in enumerate(shio_history):
        decay = math.exp(0.06 * (idx - len(shio_history) + 1))
        shio_momentum[s] += decay

    shio_gap = {s: len(shio_history) for s in range(1, 13)}
    for s in range(1, 13):
        for step, val in enumerate(reversed(shio_history)):
            if val == s:
                shio_gap[s] = step
                break

    shio_scores = {}
    for s in range(1, 13):
        m_score = shio_momentum[s]
        t_score = shio_trans[s] * 1.5
        gap_bonus = 1.5 if shio_gap[s] >= 14 else 0.0
        shio_scores[s] = m_score + t_score + gap_bonus

    tot_shio = sum(shio_scores.values()) or 1.0
    shio_probs = {s: round(shio_scores[s] / tot_shio, 3) for s in range(1, 13)}
    top_shios = sorted(range(1, 13), key=lambda s: shio_scores[s], reverse=True)[:3]

    # Jalur Shio (Jalur 1: 1, 4, 7, 10 | Jalur 2: 2, 5, 8, 11 | Jalur 3: 3, 6, 9, 12)
    jalur_map = {
        1: [1, 4, 7, 10],
        2: [2, 5, 8, 11],
        3: [3, 6, 9, 12]
    }
    jalur_scores = {j: sum(shio_probs[s] for s in shios) for j, shios in jalur_map.items()}
    tot_jalur = sum(jalur_scores.values()) or 1.0
    jalur_probs = {j: round(jalur_scores[j] / tot_jalur, 3) for j in [1, 2, 3]}
    primary_jalur = max([1, 2, 3], key=lambda j: jalur_probs[j])

    # 5. Deteksi Overdue Alerts (Anomali Gap)
    overdue_alerts = []
    for p, g in parity_gap.items():
        if g >= 8:
            overdue_alerts.append({
                "type": "parity",
                "label": f"Pola {p}",
                "gap": g,
                "alert_level": "EKSTREM" if g >= 12 else "WASPADA"
            })

    for d, g in biji_gap.items():
        if g >= 14:
            overdue_alerts.append({
                "type": "biji",
                "label": f"Biji {d}",
                "gap": g,
                "alert_level": "EKSTREM" if g >= 20 else "WASPADA"
            })

    # Overdue Shios Tracker
    overdue_shios = []
    for s_item in SHIO_2026_DATA:
        s_no = s_item["no"]
        g = shio_gap[s_no]
        if g >= 14:
            alert_lvl = "EKSTREM" if g >= 20 else "WASPADA"
            overdue_shios.append({
                "number": s_no,
                "name": s_item["name"],
                "emoji": s_item["emoji"],
                "jalur": s_item["jalur"],
                "gap": g,
                "alert_level": alert_lvl
            })
            overdue_alerts.append({
                "type": "shio",
                "label": f"Shio {s_item['emoji']} {s_item['name']} ({s_no:02d})",
                "gap": g,
                "alert_level": alert_lvl
            })

    # Confidence score 60 - 92%
    conf = int(min(92, max(60, 60 + (parity_probs[primary_parity] * 40) + (mag_probs[primary_magnitude] * 20))))

    return {
        "top_biji": top_biji,
        "biji_probabilities": {str(k): v for k, v in biji_probs.items()},
        "primary_parity": primary_parity,
        "parity_probabilities": parity_probs,
        "primary_magnitude": primary_magnitude,
        "magnitude_probabilities": mag_probs,
        "top_shios": top_shios,
        "primary_jalur": primary_jalur,
        "shio_probabilities": {str(k): v for k, v in shio_probs.items()},
        "jalur_probabilities": {str(k): v for k, v in jalur_probs.items()},
        "overdue_shios": overdue_shios,
        "overdue_alerts": overdue_alerts,
        "confidence_score": conf
    }


def audit_and_tune(results_4d: List[str], saved_prediction: Dict = None) -> Dict:
    """
    Menjalankan audit tebakan kemarin dan kalibrasi cerdas.
    Memisahkan secara total audit AI (4 metode adaptif) dan BBFS (densitas pasangan & dead digits)
    dengan aturan per-tier: ZONK -> Dikalibrasi, WIN -> Freeze.
    """
    if len(results_4d) < 15:
        return {}

    # Result terakhir (periode T)
    last_full = results_4d[-1]
    actual_k = int(last_full[2])
    actual_e = int(last_full[3])
    is_twin = (actual_k == actual_e)

    # Tebakan periode T-1
    history_before = [
        (int(r[2]), int(r[3]))
        for r in results_4d[:-1]
        if len(r) == 4 and r.isdigit()
    ]
    ranked_3, _ = rank_digits(history_before, tier_size=3)
    ranked_4, weights_t_minus_1 = rank_digits(history_before, tier_size=4)
    ranked_5, _ = rank_digits(history_before, tier_size=5)
    ranked_6, _ = rank_digits(history_before, tier_size=6)
    ranked_map = {3: ranked_3, 4: ranked_4, 5: ranked_5, 6: ranked_6}
    bbfs_t_minus_1, dead_digits_t_minus_1, _, bbfs_weights_t_minus_1 = compute_dedicated_bbfs(history_before)

    if saved_prediction and "ai4" in saved_prediction and "bbfs7" in saved_prediction:
        predicted_ai4 = saved_prediction["ai4"]
        predicted_bbfs7 = saved_prediction["bbfs7"]
    else:
        predicted_ai4 = ranked_4[:4]
        predicted_bbfs7 = bbfs_t_minus_1[7]

    # 1. AUDIT PER-TIER AI (AI-3, 4, 5, 6): WIN -> FREEZE, LOSE -> CALIBRATED
    ai_tier_audits = {}
    for sz in [3, 4, 5, 6]:
        tier_digits = saved_prediction.get(f"ai{sz}") if saved_prediction else None
        if not tier_digits:
            tier_digits = ranked_map[sz][:sz]
        is_hit = (actual_k in tier_digits or actual_e in tier_digits)
        p_label = "3 Digit Ketat" if sz == 3 else ("4 Digit Utama" if sz == 4 else ("5 Digit Moderat" if sz == 5 else "6 Digit Proteksi"))
        ai_tier_audits[f"ai{sz}"] = {
            "parameter": f"Parameter AI-{sz} ({p_label})",
            "status": "HIT" if is_hit else "LOSE",
            "action": "FREEZE" if is_hit else "CALIBRATED",
            "tuning_directive": f"🔒 FREEZE: Parameter AI-{sz} dipertahankan stabil" if is_hit else f"⚡ KALIBRASI: Parameter AI-{sz} dikalibrasi ulang (Zonk)",
            "digits": tier_digits
        }

    hit_digits = []
    if actual_k in predicted_ai4:
        hit_digits.append(actual_k)
    if actual_e in predicted_ai4 and actual_e not in hit_digits:
        hit_digits.append(actual_e)
    status_ai = "HIT" if hit_digits else "LOSE"

    # Penyesuaian Penalti & Reward 4 Metode AI (Hanya jika ada tier yang Zonk)
    penalized = []
    rewarded = []
    calibrated_weights = dict(weights_t_minus_1)
    if saved_prediction and "tier_method_weights" in saved_prediction:
        old_w4 = saved_prediction["tier_method_weights"].get(4) or saved_prediction["tier_method_weights"].get("4")
        if old_w4:
            calibrated_weights = dict(old_w4)

    all_ai_frozen = all(audit["action"] == "FREEZE" for audit in ai_tier_audits.values())

    if not all_ai_frozen:
        methods = {
            "Momentum": get_momentum_scores(history_before),
            "Markov": get_markov_scores(history_before),
            "Delta": get_delta_scores(history_before),
            "Mistik": get_mistik_scores(history_before)
        }

        # SMART BOBOT (ANTI-OSILASI): Streak-Aware, Symmetric Multiplier & EMA Smoothing
        method_streaks = {"Momentum": 0, "Markov": 0, "Delta": 0, "Mistik": 0}
        for m_name in methods.keys():
            m_streak = 0
            for i in range(len(results_4d) - 2, max(0, len(results_4d) - 8), -1):
                h_sub = [(int(r[2]), int(r[3])) for r in results_4d[:i + 1] if len(r) == 4 and r.isdigit()]
                next_k = int(results_4d[i + 1][2])
                next_e = int(results_4d[i + 1][3])
                if m_name == "Momentum":
                    s_map = get_momentum_scores(h_sub)
                elif m_name == "Markov":
                    s_map = get_markov_scores(h_sub)
                elif m_name == "Delta":
                    s_map = get_delta_scores(h_sub)
                else:
                    s_map = get_mistik_scores(h_sub)

                t3 = sorted(s_map.keys(), key=lambda d: s_map[d], reverse=True)[:3]
                was_hit = (next_k in t3 or next_e in t3)
                if i == len(results_4d) - 2:
                    m_streak = 1 if was_hit else -1
                else:
                    if m_streak > 0 and was_hit:
                        m_streak += 1
                    elif m_streak < 0 and not was_hit:
                        m_streak -= 1
                    else:
                        break
            method_streaks[m_name] = m_streak

        for m_name, scores in methods.items():
            top3 = sorted(scores.keys(), key=lambda d: scores[d], reverse=True)[:3]
            hit_method = (actual_k in top3 or actual_e in top3)
            prev_w = float(calibrated_weights.get(m_name, 10.0))
            # method_streaks[m_name] sudah mencakup evaluasi draw T (aktual)
            streak_val = method_streaks.get(m_name, 1 if hit_method else -1)
            current_streak_len = max(1, abs(streak_val))

            # 1. Streak-Aware Learning Rate (η):
            # Streak 1 (fluktuasi harian / noise): η = 0.08 (±8%)
            # Streak 2 (mulai konsisten): η = 0.16 (±16%)
            # Streak >= 3 (tren kuat): η = 0.25 (±25%)
            eta = 0.08
            if current_streak_len >= 3:
                eta = 0.25
            elif current_streak_len == 2:
                eta = 0.16

            # 2. Symmetric Multiplier (e^+η vs e^-η):
            multiplier = math.exp(eta) if hit_method else math.exp(-eta)
            target_weight = prev_w * multiplier

            # 3. EMA Smoothing (Filter Inersia 70:30):
            beta = 0.70
            smoothed_weight = beta * prev_w + (1.0 - beta) * target_weight

            # 4. Safety Bounds Clamping [4.0x - 16.0x]:
            clamped = max(4.0, min(16.0, smoothed_weight))
            calibrated_weights[m_name] = round(clamped, 1)

            if hit_method:
                rewarded.append(m_name)
            else:
                penalized.append(m_name)

    # 2. AUDIT PER-TIER BBFS (BBFS-6, 7, 8, 9): WIN -> FREEZE, LOSE -> CALIBRATED
    bbfs_tier_audits = {}
    for sz in [6, 7, 8, 9]:
        tier_digits = saved_prediction.get(f"bbfs{sz}") if saved_prediction else None
        if not tier_digits:
            tier_digits = bbfs_t_minus_1[sz]
        if is_twin:
            is_hit = (actual_k in tier_digits)
        else:
            is_hit = (actual_k in tier_digits and actual_e in tier_digits)
        bbfs_param_label = f"{sz} Digit / {30 if sz == 6 else (42 if sz == 7 else (56 if sz == 8 else 72))} Line"
        bbfs_tier_audits[f"bbfs{sz}"] = {
            "parameter": f"Parameter BBFS-{sz} ({bbfs_param_label})",
            "status": "HIT" if is_hit else "LOSE",
            "action": "FREEZE" if is_hit else "CALIBRATED",
            "tuning_directive": f"🔒 FREEZE: Parameter BBFS-{sz} dipertahankan stabil" if is_hit else f"⚡ KALIBRASI: Parameter BBFS-{sz} dikalibrasi ulang (Zonk)",
            "digits": tier_digits
        }

    bbfs7_set = set(predicted_bbfs7)
    status_bbfs = "HIT" if (actual_k in bbfs7_set if is_twin else (actual_k in bbfs7_set and actual_e in bbfs7_set)) else "LOSE"

    # Dead Digits Audit
    dead_digits_clean = (actual_k not in dead_digits_t_minus_1 and actual_e not in dead_digits_t_minus_1)

    # Smart Trimmer Zone Audit
    trimmer = generate_smart_trim(predicted_bbfs7)
    target_2d = f"{actual_k}{actual_e}"
    if target_2d in trimmer["top10"]:
        trimmer_zone = "BOM_10"
    elif target_2d in trimmer["medium15"]:
        trimmer_zone = "MEDIUM_15"
    elif target_2d in trimmer["cadangan"]:
        trimmer_zone = "CADANGAN"
    elif is_twin and actual_k in predicted_bbfs7:
        trimmer_zone = "CADANGAN"
    else:
        trimmer_zone = "MISSED"

    # Prediksi untuk putaran BERIKUTNYA (setelah result T masuk) - Dihitung independen per-tier
    full_history_2d = [
        (int(r[2]), int(r[3]))
        for r in results_4d
        if len(r) == 4 and r.isdigit()
    ]

    # ATURAN ENGINE: Jika prediksi masuk (FREEZE), TIDAK PERLU hitung bobot dari awal!
    # Pertahankan bobot pemenang langsung tanpa recalculate. Hanya hitung saat cold-start.
    next_ranked = {}
    next_weights = {}
    for sz in [3, 4, 5, 6]:
        audit_tier = ai_tier_audits.get(f"ai{sz}", {})
        if audit_tier.get("action") == "FREEZE":
            # PREDIKSI MASUK: Freeze bobot pemenang tanpa hitung ulang dari awal
            frozen_w = None
            if saved_prediction and "tier_method_weights" in saved_prediction:
                frozen_w = saved_prediction["tier_method_weights"].get(sz) or saved_prediction["tier_method_weights"].get(str(sz))
            if not frozen_w:
                frozen_w = calibrated_weights
            r_sz, w_sz = rank_digits(full_history_2d, tier_size=sz, custom_weights=frozen_w)
        else:
            # PREDIKSI ZONK: Gunakan bobot terkalibrasi hasil tuning
            r_sz, w_sz = rank_digits(full_history_2d, tier_size=sz, custom_weights=calibrated_weights)
        next_ranked[sz] = r_sz
        next_weights[sz] = w_sz

    next_3 = next_ranked[3]
    next_weights_3 = next_weights[3]
    next_4 = next_ranked[4]
    next_weights_4 = next_weights[4]
    next_5 = next_ranked[5]
    next_weights_5 = next_weights[5]
    next_6 = next_ranked[6]
    next_weights_6 = next_weights[6]

    # BBFS: Jika tier WIN -> FREEZE bobot faktor tier tersebut tanpa hitung ulang dari awal
    bbfs_custom_weights = {}
    for sz in [6, 7, 8, 9]:
        b_audit = bbfs_tier_audits.get(f"bbfs{sz}", {})
        if b_audit.get("action") == "FREEZE":
            old_bw = None
            if saved_prediction and "bbfs_tier_weights" in saved_prediction:
                old_bw = saved_prediction["bbfs_tier_weights"].get(sz) or saved_prediction["bbfs_tier_weights"].get(str(sz))
            if not old_bw and bbfs_weights_t_minus_1:
                old_bw = bbfs_weights_t_minus_1.get(sz)
            if old_bw:
                bbfs_custom_weights[sz] = old_bw

    next_bbfs, next_dead_digits, _, next_bbfs_weights = compute_dedicated_bbfs(
        full_history_2d,
        custom_tier_factor_weights=bbfs_custom_weights if bbfs_custom_weights else None
    )

    all_bbfs_frozen = all(audit["action"] == "FREEZE" for audit in bbfs_tier_audits.values())

    next_paito = predict_paito_macro(full_history_2d)

    # Audit Makro Paito & Sniper BOM periode kemarin
    paito_pred_t_minus_1 = saved_prediction.get("paito") if (saved_prediction and "paito" in saved_prediction) else predict_paito_macro(history_before)
    actual_biji = compute_biji(actual_k, actual_e)
    actual_parity = f"{'Genap' if actual_k % 2 == 0 else 'Ganjil'}-{'Genap' if actual_e % 2 == 0 else 'Ganjil'}"
    actual_magnitude = "Besar" if (actual_k * 10 + actual_e >= 50) else "Kecil"
    actual_shio_obj = get_shio_2026(actual_k * 10 + actual_e)
    actual_shio = actual_shio_obj["no"]
    actual_shio_name = f"{actual_shio_obj['emoji']} {actual_shio_obj['name']}"
    actual_jalur = actual_shio_obj["jalur"]

    hit_biji = actual_biji in paito_pred_t_minus_1.get("top_biji", [])
    hit_parity = (actual_parity == paito_pred_t_minus_1.get("primary_parity"))
    hit_magnitude = (actual_magnitude == paito_pred_t_minus_1.get("primary_magnitude"))
    hit_shio = actual_shio in paito_pred_t_minus_1.get("top_shios", [])
    hit_jalur = (actual_jalur == paito_pred_t_minus_1.get("primary_jalur"))

    sniper_res_t_minus_1 = generate_sniper_trim(predicted_bbfs7, paito_pred_t_minus_1, include_twins=False)
    actual_2d_str = f"{actual_k}{actual_e}"
    hit_super_sniper = (not is_twin) and (actual_2d_str in sniper_res_t_minus_1.get("super_sniper_shio", []))
    hit_sniper_bom = (not is_twin) and (actual_2d_str in sniper_res_t_minus_1.get("sniper_top", []))
    hit_sniper_sec = (not is_twin) and (actual_2d_str in sniper_res_t_minus_1.get("sniper_secondary", []))

    total_hits = sum([hit_biji, hit_parity, hit_magnitude, hit_shio])
    strike_status = "PERFECT_STRIKE" if total_hits == 4 else f"{total_hits}/4_HIT"

    paito_audit = {
        "actual_biji": actual_biji,
        "actual_parity": actual_parity,
        "actual_magnitude": actual_magnitude,
        "actual_shio": actual_shio,
        "actual_shio_name": actual_shio_name,
        "actual_jalur": actual_jalur,
        "hit_biji": hit_biji,
        "hit_parity": hit_parity,
        "hit_magnitude": hit_magnitude,
        "hit_shio": hit_shio,
        "hit_jalur": hit_jalur,
        "sniper_status": "SUPER_BOM_HIT" if hit_super_sniper else ("BOM_HIT" if hit_sniper_bom else ("SECONDARY_HIT" if hit_sniper_sec else "MISSED")),
        "strike_status": strike_status
    }

    return {
        "actual_result": last_full,
        "actual_2d": f"{actual_k}{actual_e}",
        "is_twin": is_twin,
        "paito_audit": paito_audit,
        "previous_prediction": {
            "ai4": predicted_ai4,
            "bbfs7": predicted_bbfs7,
            "dead_digits": dead_digits_t_minus_1
        },
        "status_ai": status_ai,
        "status_bbfs": status_bbfs,
        "hit_digits": hit_digits,
        "ai_tuning": {
            "tier_audits": ai_tier_audits,
            "status_ai4": status_ai,
            "hit_digits": hit_digits,
            "rewarded_methods": rewarded,
            "penalized_methods": penalized,
            "calibrated_weights": calibrated_weights,
            "recommended_tier": "AI-3" if ai_tier_audits.get("ai3", {}).get("action") == "FREEZE" else "AI-4",
            "action_summary": "Semua tier AI stabil (Freeze Total)" if all_ai_frozen else ("AI-3 dikalibrasi; AI-4..6 di-freeze" if ai_tier_audits.get("ai3", {}).get("action") == "CALIBRATED" else "Audit AI Selesai")
        },
        "bbfs_tuning": {
            "tier_audits": bbfs_tier_audits,
            "status_bbfs7": status_bbfs,
            "dead_digits": dead_digits_t_minus_1,
            "dead_digits_clean": dead_digits_clean,
            "trimmer_zone": trimmer_zone,
            "is_twin": is_twin,
            "twin_status": "TWIN_PROTECTED" if (is_twin and actual_k in bbfs7_set) else ("TWIN_UNPROTECTED" if is_twin else "NON_TWIN"),
            "rewarded_factor": "Semua Tier Tembus (Freeze Total)" if all_bbfs_frozen else ("Top 10 BOM Hit" if trimmer_zone == "BOM_10" else ("Dead Digits 100% Bersih" if dead_digits_clean else "Densitas Pasangan")),
            "penalized_factor": "None (Freeze Total)" if all_bbfs_frozen else ("Kebocoran Dead Digit" if not dead_digits_clean else ("Dispersi Pasangan" if status_bbfs == "LOSE" else "None")),
            "recommended_tier": "BBFS-6" if bbfs_tier_audits.get("bbfs6", {}).get("action") == "FREEZE" else "BBFS-7",
            "action_summary": "Semua tier BBFS stabil (Freeze Total)" if all_bbfs_frozen else ("BBFS-6 dikalibrasi; BBFS-7..9 di-freeze" if bbfs_tier_audits.get("bbfs6", {}).get("action") == "CALIBRATED" else "Audit BBFS Selesai")
        },
        "penalized_methods": penalized,
        "rewarded_methods": rewarded,
        "calibrated_weights": calibrated_weights,
        "next_prediction": {
            "ai3": next_3[:3],
            "ai4": next_4[:4],
            "ai5": next_5[:5],
            "ai6": next_6[:6],
            "tier_method_weights": {
                "3": next_weights_3,
                "4": next_weights_4,
                "5": next_weights_5,
                "6": next_weights_6
            },
            "bbfs6": next_bbfs[6],
            "bbfs7": next_bbfs[7],
            "bbfs8": next_bbfs[8],
            "bbfs9": next_bbfs[9],
            "bbfs_tier_weights": {str(k): v for k, v in next_bbfs_weights.items()},
            "dead_digits": next_dead_digits,
            "paito": next_paito
        }
    }
