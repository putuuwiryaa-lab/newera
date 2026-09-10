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
    """Memilah kombinasi 2D BBFS-7 ke dalam Top 10 BOM, Medium 15, Cadangan, BOM 12, Invest 20, dan Full 42."""
    top4 = bbfs7_digits[:4]
    bom12 = [f"{a}{b}" for a in top4 for b in top4 if a != b]
    top10 = bom12[:10]
    top5 = bbfs7_digits[:5]
    invest20 = [f"{a}{b}" for a in top5 for b in top5 if a != b]
    top10_set = set(top10)
    medium15 = [l for l in invest20 if l not in top10_set][:15]
    top7 = bbfs7_digits[:7]
    full42 = [f"{a}{b}" for a in top7 for b in top7 if a != b]
    used = set(top10 + medium15)
    cadangan = [l for l in full42 if l not in used]
    return {
        "top10": top10,
        "medium15": medium15,
        "cadangan": cadangan,
        "bom12": bom12,
        "invest20": invest20,
        "full42": full42
    }


def generate_wheeling_system(digits: List[int]) -> Dict:
    """Wheeling System Covering Design C(7, 3, 2) dan C(7, 4, 3) untuk hemat modal 3D & 4D."""
    unique = list(dict.fromkeys(digits))
    d = unique[:7]
    for i in range(10):
        if len(d) >= 7:
            break
        if i not in d:
            d.append(i)

    # 1. 3D Wheel (15 Line) C(7, 3, 2)
    WHEEL_3D = [
        [0, 1, 2], [0, 3, 4], [0, 5, 6],
        [1, 3, 5], [1, 4, 6], [2, 3, 6], [2, 4, 5],
        [0, 1, 4], [0, 2, 5], [0, 3, 6],
        [1, 2, 3], [1, 5, 6], [2, 4, 6], [3, 4, 5],
        [0, 1, 3]
    ]
    wheel_3d = [f"{d[idx[0]]}{d[idx[1]]}{d[idx[2]]}" for idx in WHEEL_3D]
    wheel_3d_full = [f"{d[i]}{d[j]}{d[k]}" for i in range(7) for j in range(i + 1, 7) for k in range(j + 1, 7)]

    # 2. 4D Wheel (14 Line) C(7, 4, 3)
    WHEEL_4D = [
        [0, 1, 2, 3], [0, 1, 4, 5], [0, 2, 4, 6], [0, 3, 5, 6],
        [1, 2, 5, 6], [1, 3, 4, 6], [2, 3, 4, 5], [0, 1, 2, 4],
        [0, 1, 2, 5], [0, 1, 2, 6], [0, 1, 3, 4], [0, 1, 3, 5],
        [0, 2, 3, 6], [0, 4, 5, 6]
    ]
    wheel_4d = [f"{d[idx[0]]}{d[idx[1]]}{d[idx[2]]}{d[idx[3]]}" for idx in WHEEL_4D]
    wheel_4d_full = [
        f"{d[i]}{d[j]}{d[k]}{d[m]}"
        for i in range(7)
        for j in range(i + 1, 7)
        for k in range(j + 1, 7)
        for m in range(k + 1, 7)
    ]

    return {
        "wheel_3d": wheel_3d,
        "wheel_3d_full": wheel_3d_full,
        "wheel_4d": wheel_4d,
        "wheel_4d_full": wheel_4d_full,
        "guarantee_3d": "Jaminan 100% Pasangan 2D Tercover (Hemat 93% Modal)",
        "guarantee_4d": "Jaminan 100% Triplet 3-in-4 Tercover (Hemat 96% Modal)"
    }


def synthesize_paito_bbfs7(history_2d: List[Tuple[int, int]], paito_pred: Dict = None) -> Dict:
    """Mesin Sintesis BBFS-7 Paito Pro dengan Regularizer Entropi dan Isolasi 3 Kumat."""
    if paito_pred is None:
        paito_pred = predict_paito_macro(history_2d)

    sub = history_2d[-50:] if len(history_2d) >= 50 else history_2d
    top_biji = set(paito_pred.get("top_biji", [1, 2, 3]))
    top_shios = set(paito_pred.get("top_shios", [1, 2, 3]))
    prim_jalur = paito_pred.get("primary_jalur", 1)
    prim_parity = paito_pred.get("primary_parity", "Genap-Ganjil")

    pair_matrix = [[0.0] * 10 for _ in range(10)]
    for k, e in sub:
        pair_matrix[k][e] += 1.0
        pair_matrix[e][k] += 0.5

    single_scores = {d: 0.0 for d in range(10)}
    n = len(sub)
    for d in range(10):
        mom = 0.0
        for idx, (k, e) in enumerate(sub):
            w = math.exp(0.06 * (idx - n + 1))
            if k == d: mom += w * 1.2
            if e == d: mom += w * 1.0
        biji_compat = sum(1.2 for o in range(10) if o != d and compute_biji(d, o) in top_biji)
        par_compat = 2.0 if ((d % 2 == 0 and prim_parity.startswith("Genap")) or (d % 2 != 0 and prim_parity.startswith("Ganjil"))) else 0.0
        shio_compat = sum(1.0 for o in range(10) if get_shio_2026(d * 10 + o)["no"] in top_shios)

        single_scores[d] = mom * 1.5 + biji_compat * 1.4 + par_compat * 1.8 + shio_compat * 1.2

    best_score = -1e9
    best_comb = list(range(7))
    for comb in itertools.combinations(range(10), 7):
        comb_score = sum(single_scores[d] for d in comb)
        for i in range(7):
            for j in range(i + 1, 7):
                comb_score += (pair_matrix[comb[i]][comb[j]] + pair_matrix[comb[j]][comb[i]]) * 0.8
        n_besar = sum(1 for d in comb if d >= 5)
        n_genap = sum(1 for d in comb if d % 2 == 0)
        pen_b = max(0.0, abs(n_besar - 3.5) - 0.5) * 4.0
        pen_g = max(0.0, abs(n_genap - 3.5) - 0.5) * 4.0
        total_s = comb_score - pen_b - pen_g
        if total_s > best_score:
            best_score = total_s
            best_comb = comb

    internal_s = {d: single_scores[d] + sum(pair_matrix[d][o] + pair_matrix[o][d] for o in best_comb if o != d) for d in best_comb}
    ranked7 = sorted(best_comb, key=lambda d: internal_s[d], reverse=True)
    dead_digits = [d for d in range(10) if d not in best_comb]

    bom12 = [f"{a}{b}" for a in ranked7[:4] for b in ranked7[:4] if a != b]
    invest20 = [f"{a}{b}" for a in ranked7[:5] for b in ranked7[:5] if a != b]
    full42 = [f"{a}{b}" for a in ranked7 for b in ranked7 if a != b]

    def line_score(l: str) -> float:
        k_val, e_val = int(l[0]), int(l[1])
        sc = 0.0
        if compute_biji(k_val, e_val) in top_biji: sc += 4.0
        par_str = f"{'Genap' if k_val % 2 == 0 else 'Ganjil'}-{'Genap' if e_val % 2 == 0 else 'Ganjil'}"
        if par_str == prim_parity: sc += 3.0
        if get_shio_2026(k_val * 10 + e_val)["no"] in top_shios: sc += 2.0
        return sc

    scored_lines = sorted(full42, key=line_score, reverse=True)
    nuklir6 = scored_lines[:6]

    return {
        "digits": ranked7,
        "nuklir6": nuklir6,
        "bom12": bom12,
        "invest20": invest20,
        "full42": full42,
        "dead_digits": dead_digits
    }


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
        "confidence_score": conf,
        "movement": analyze_movement_patterns(history_2d)
    }


def analyze_movement_patterns(history_2d: List[Tuple[int, int]]) -> Dict:
    """
    Kalkulasi Pola Pergerakan Kinetik:
    1. Besar/Kecil: Deteksi Zig-Zag vs Streak Reversal vs Trend Follow
    2. Paritas: Osilasi Partikel Kepala & Ekor (Flip vs Sticky)
    3. Jalur: Rotasi Siklis Orbit Mod 3
    4. Biji: Langkah Selisih Modulo 10
    5. Jejak 5 Result Terakhir
    """
    if len(history_2d) < 5:
        return {}

    # 1. Magnitude movement
    vals = [k * 10 + e for k, e in history_2d[-25:]]
    mag_states = ["Besar" if v >= 50 else "Kecil" for v in vals]
    flips = sum(1 for i in range(1, len(mag_states)) if mag_states[i] != mag_states[i-1])
    flip_rate = flips / (len(mag_states) - 1) if len(mag_states) > 1 else 0.5

    current_streak = 1
    last_state = mag_states[-1]
    for i in range(len(mag_states) - 2, -1, -1):
        if mag_states[i] == last_state:
            current_streak += 1
        else:
            break

    recent_5_vals = vals[-5:]
    slope = (recent_5_vals[-1] - recent_5_vals[0]) / 4.0 if len(recent_5_vals) >= 5 else 0.0

    if flip_rate >= 0.58:
        mag_rhythm = "ZIG_ZAG"
        mag_label = f"Osilasi Zig-Zag (Flip {int(flip_rate*100)}%)"
        pred_mag = "Kecil" if last_state == "Besar" else "Besar"
    elif current_streak >= 3:
        mag_rhythm = "STREAK_REVERSAL"
        mag_label = f"Pembalikan Jenuh (Streak {current_streak}x {last_state})"
        pred_mag = "Kecil" if last_state == "Besar" else "Besar"
    else:
        mag_rhythm = "TREND_FOLLOW"
        mag_label = f"Aliran Tren ({'+' if slope >= 0 else ''}{round(slope, 1)})"
        pred_mag = "Besar" if slope > 0 else "Kecil"

    # 2. Parity movement
    kepalas = [k for k, e in history_2d[-20:]]
    ekors = [e for k, e in history_2d[-20:]]
    k_flips = sum(1 for i in range(1, len(kepalas)) if (kepalas[i] % 2) != (kepalas[i-1] % 2))
    e_flips = sum(1 for i in range(1, len(ekors)) if (ekors[i] % 2) != (ekors[i-1] % 2))
    k_osc = "FLIP" if (k_flips / max(1, len(kepalas) - 1)) >= 0.5 else "STICKY"
    e_osc = "FLIP" if (e_flips / max(1, len(ekors) - 1)) >= 0.5 else "STICKY"

    last_k_par = "Genap" if kepalas[-1] % 2 == 0 else "Ganjil"
    last_e_par = "Genap" if ekors[-1] % 2 == 0 else "Ganjil"
    next_k_par = ("Ganjil" if last_k_par == "Genap" else "Genap") if k_osc == "FLIP" else last_k_par
    next_e_par = ("Ganjil" if last_e_par == "Genap" else "Genap") if e_osc == "FLIP" else last_e_par
    pred_parity = f"{next_k_par}-{next_e_par}"

    # 3. Jalur Orbit
    jalurs = [get_shio_2026(k * 10 + e)["jalur"] for k, e in history_2d[-15:]]
    delta = (jalurs[-1] - jalurs[-2]) % 3 if len(jalurs) >= 2 else 1
    if delta == 1:
        orbit_dir = "PUTARAN_MAJU"
        orbit_lbl = "Putaran Maju (+1 Mod 3)"
        pred_jalur = ((jalurs[-1] - 1 + 1) % 3) + 1
    elif delta == 2:
        orbit_dir = "PUTARAN_MUNDUR"
        orbit_lbl = "Putaran Mundur (-1 Mod 3)"
        pred_jalur = ((jalurs[-1] - 1 + 2) % 3) + 1
    else:
        orbit_dir = "BERTAHAN"
        orbit_lbl = "Orbit Bertahan"
        pred_jalur = jalurs[-1]

    # 4. Biji Step Modular
    bijis = [compute_biji(k, e) for k, e in history_2d[-15:]]
    biji_delta = (bijis[-1] - bijis[-2]) % 10 if len(bijis) >= 2 else 1
    pred_biji = (bijis[-1] + biji_delta) % 10

    # 5. Last 5 draws
    last_5 = []
    for k, e in history_2d[-5:]:
        c2d = f"{k}{e}"
        v = k * 10 + e
        shio_obj = get_shio_2026(v)
        last_5.append({
            "comb2d": c2d,
            "kepala": k,
            "ekor": e,
            "magnitude": "Besar" if v >= 50 else "Kecil",
            "parity": f"{'Genap' if k % 2 == 0 else 'Ganjil'}-{'Genap' if e % 2 == 0 else 'Ganjil'}",
            "biji": compute_biji(k, e),
            "jalur": shio_obj["jalur"],
            "shio_number": shio_obj["no"],
            "shio_name": shio_obj["name"]
        })

    return {
        "magnitude": {
            "rhythm": mag_rhythm,
            "rhythm_label": mag_label,
            "flip_rate": round(flip_rate, 3),
            "current_streak": current_streak,
            "current_streak_state": last_state,
            "prediction": pred_mag
        },
        "parity": {
            "kepala_oscillation": k_osc,
            "ekor_oscillation": e_osc,
            "primary_parity": pred_parity,
            "trajectory_flow": f"{mag_states[-3] if len(mag_states)>=3 else ''} -> {mag_states[-2] if len(mag_states)>=2 else ''} -> {mag_states[-1]}"
        },
        "jalur": {
            "orbit_direction": orbit_dir,
            "orbit_label": orbit_lbl,
            "predicted_jalur": pred_jalur
        },
        "biji": {
            "dominant_step_delta": biji_delta,
            "step_label": f"Langkah Δ{biji_delta:+d} mod 10",
            "target_biji": [pred_biji, (pred_biji + 1) % 10, (pred_biji + 9) % 10]
        },
        "last_5_draws": last_5
    }


def analyze_pola_tarung(history_2d: List[Tuple[int, int]], lookback: int = 50) -> Dict:
    """
    Pola Tarung 2D (Kepala vs Ekor Terpisah No BB):
    Menghitung afinitas posisional Kepala dan Ekor serta menghasilkan formasi:
    - 3x3 BOM (9 line)
    - 4x4 Utama (16 line)
    - 5x5 Invest (25 line)
    """
    sub_hist = history_2d[-lookback:] if len(history_2d) >= lookback else history_2d
    n = len(sub_hist)
    k_scores = {d: 0.0 for d in range(10)}
    e_scores = {d: 0.0 for d in range(10)}

    for idx, (k, e) in enumerate(sub_hist):
        w = math.exp(0.06 * (idx - n + 1))
        k_scores[k] += w * 2.0
        e_scores[e] += w * 2.0

    ranked_k = sorted(range(10), key=lambda d: k_scores[d], reverse=True)
    ranked_e = sorted(range(10), key=lambda d: e_scores[d], reverse=True)

    def gen_lines(ks: List[int], es: List[int]) -> List[str]:
        res = []
        for k in ks:
            for e in es:
                res.append(f"{k}{e}")
        return res

    return {
        "ranked_kepala": ranked_k,
        "ranked_ekor": ranked_e,
        "tarung_3x3": gen_lines(ranked_k[:3], ranked_e[:3]),
        "tarung_4x4": gen_lines(ranked_k[:4], ranked_e[:4]),
        "tarung_5x5": gen_lines(ranked_k[:5], ranked_e[:5])
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

    next_paito_bbfs7 = synthesize_paito_bbfs7(full_history_2d, next_paito)
    next_wheeling7 = generate_wheeling_system(next_paito_bbfs7["digits"])

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
            "paito": next_paito,
            "pola_tarung": analyze_pola_tarung(full_history_2d),
            "paito_bbfs7": next_paito_bbfs7,
            "wheeling7": next_wheeling7
        }
    }
