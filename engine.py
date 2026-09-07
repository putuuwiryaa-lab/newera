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
        for d in [pk, pe]:
            if d in actual_set:
                branch_hits["asli"] += 1
            if INDEX_MAP.get(d) in actual_set:
                branch_hits["indeks"] += 1
            if MISTIK_LAMA.get(d) in actual_set:
                branch_hits["mistik_lama"] += 1
            if MISTIK_BARU.get(d) in actual_set:
                branch_hits["mistik_baru"] += 1

    last_k, last_e = sub_hist[-1]
    for d in [last_k, last_e]:
        scores[d] += branch_hits["asli"]
        scores[INDEX_MAP[d]] += branch_hits["indeks"]
        scores[MISTIK_LAMA[d]] += branch_hits["mistik_lama"]
        scores[MISTIK_BARU[d]] += branch_hits["mistik_baru"]

    return scores


def rank_digits(history_2d: List[Tuple[int, int]], rolling_window: int = 20, tier_size: int = 4) -> Tuple[List[int], Dict[str, float]]:
    methods = {
        "Momentum": lambda h: get_momentum_scores(h),
        "Markov": lambda h: get_markov_scores(h),
        "Delta": lambda h: get_delta_scores(h),
        "Mistik": lambda h: get_mistik_scores(h)
    }

    weights = {"Momentum": 1.0, "Markov": 1.0, "Delta": 1.0, "Mistik": 1.0}

    if len(history_2d) > rolling_window + 5:
        eval_slice = history_2d[-rolling_window:]
        for m_name, m_func in methods.items():
            hit_count = 0
            for step in range(len(eval_slice) - 1):
                hist_until = history_2d[:-(rolling_window - step)]
                actual_next = set(eval_slice[step + 1])
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


def compute_dedicated_bbfs(history_2d: List[Tuple[int, int]], lookback: int = 50) -> Dict[int, List[int]]:
    """
    ENGINE KHUSUS BBFS 2D BELAKANG:
    Menghitung optimasi joint-pair coverage (independen dari rumus 1 digit AI).
    1. Memisahkan model posisi Kepala dan posisi Ekor (Markov & Recency)
    2. Matriks afinitas pasangan 2D (co-occurrence & bolak-balik)
    3. Evaluasi kombinatorika untuk memilih K digit yang memaksimalkan total pasangan ter-cover
    """
    sub = history_2d[-lookback:]
    n = len(sub)
    if n < 2:
        return {
            6: list(range(6)),
            7: list(range(7)),
            8: list(range(8)),
            9: list(range(9))
        }, [8, 9], list(range(10))

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

    joint = [[0.0 for _ in range(10)] for _ in range(10)]
    for k in range(10):
        for e in range(10):
            pos_pot = (k_scores[k] + k_trans[k] * 1.5) * (e_scores[e] + e_trans[e] * 1.5)
            joint[k][e] = pos_pot + (pair_matrix[k][e] * 3.0)

    res = {}
    for size in [6, 7, 8, 9]:
        best_score = -1.0
        best_comb = None
        for comb in itertools.combinations(range(10), size):
            s = set(comb)
            score = sum(joint[k][e] for k in s for e in s)
            if score > best_score:
                best_score = score
                best_comb = comb
        s = set(best_comb)
        digit_contrib = {d: sum(joint[d][x] + joint[x][d] for x in s) for d in s}
        res[size] = sorted(best_comb, key=lambda d: digit_contrib[d], reverse=True)

    # Hitung Skor Afinitas Total 2D per Digit (0-9)
    bbfs_digit_scores = {d: sum(joint[d][x] + joint[x][d] for x in range(10)) for d in range(10)}
    bbfs_ranked = sorted(bbfs_digit_scores.keys(), key=lambda d: bbfs_digit_scores[d], reverse=True)
    dead_digits = bbfs_ranked[-2:]

    return res, dead_digits, bbfs_ranked


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
    bbfs_t_minus_1, dead_digits_t_minus_1, _ = compute_dedicated_bbfs(history_before)

    if saved_prediction and "ai4" in saved_prediction and "bbfs7" in saved_prediction:
        predicted_ai4 = saved_prediction["ai4"]
        predicted_bbfs7 = saved_prediction["bbfs7"]
    else:
        predicted_ai4 = ranked_4[:4]
        predicted_bbfs7 = bbfs_t_minus_1[7]

    # 1. AUDIT PER-TIER AI (AI-3, 4, 5, 6): WIN -> FREEZE, LOSE -> CALIBRATED
    ai_tier_audits = {}
    for sz in [3, 4, 5, 6]:
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

    all_ai_frozen = all(audit["action"] == "FREEZE" for audit in ai_tier_audits.values())

    if not all_ai_frozen:
        methods = {
            "Momentum": get_momentum_scores(history_before),
            "Markov": get_markov_scores(history_before),
            "Delta": get_delta_scores(history_before),
            "Mistik": get_mistik_scores(history_before)
        }

        for m_name, scores in methods.items():
            top3 = sorted(scores.keys(), key=lambda d: scores[d], reverse=True)[:3]
            if actual_k in top3 or actual_e in top3:
                rewarded.append(m_name)
                calibrated_weights[m_name] = round(calibrated_weights[m_name] * 1.35, 2)
            else:
                penalized.append(m_name)
                calibrated_weights[m_name] = round(max(0.4, calibrated_weights[m_name] * 0.65), 2)

    # 2. AUDIT PER-TIER BBFS (BBFS-6, 7, 8, 9): WIN -> FREEZE, LOSE -> CALIBRATED
    bbfs_tier_audits = {}
    for sz in [6, 7, 8, 9]:
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

    # Prediksi untuk putaran BERIKUTNYA (setelah result T masuk)
    # Prediksi untuk putaran BERIKUTNYA (setelah result T masuk) - Dihitung independen per-tier
    full_history_2d = [
        (int(r[2]), int(r[3]))
        for r in results_4d
        if len(r) == 4 and r.isdigit()
    ]
    next_3, next_weights_3 = rank_digits(full_history_2d, tier_size=3)
    next_4, next_weights_4 = rank_digits(full_history_2d, tier_size=4)
    next_5, next_weights_5 = rank_digits(full_history_2d, tier_size=5)
    next_6, next_weights_6 = rank_digits(full_history_2d, tier_size=6)
    next_bbfs, next_dead_digits, _ = compute_dedicated_bbfs(full_history_2d)

    all_bbfs_frozen = all(audit["action"] == "FREEZE" for audit in bbfs_tier_audits.values())

    return {
        "actual_result": last_full,
        "actual_2d": f"{actual_k}{actual_e}",
        "is_twin": is_twin,
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
                3: next_weights_3,
                4: next_weights_4,
                5: next_weights_5,
                6: next_weights_6
            },
            "bbfs6": next_bbfs[6],
            "bbfs7": next_bbfs[7],
            "bbfs8": next_bbfs[8],
            "bbfs9": next_bbfs[9],
            "dead_digits": next_dead_digits
        }
    }
