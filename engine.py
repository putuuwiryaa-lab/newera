"""
Modul Engine Adaptif & Auto-Tuning untuk Scraper Backend (Python)
Menjalankan audit tebakan, penalti/reward, dan prediksi periode berikutnya.
"""

import math
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


def rank_digits(history_2d: List[Tuple[int, int]], rolling_window: int = 20) -> Tuple[List[int], Dict[str, float]]:
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
                top3 = sorted(m_scores.keys(), key=lambda d: m_scores[d], reverse=True)[:3]
                if any(d in actual_next for d in top3):
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


def audit_and_tune(results_4d: List[str]) -> Dict:
    """
    Menjalankan audit tebakan kemarin dan kalibrasi cerdas.
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
    ranked_t_minus_1, weights_t_minus_1 = rank_digits(history_before)

    predicted_ai4 = ranked_t_minus_1[:4]
    predicted_bbfs7 = ranked_t_minus_1[:7]

    hit_digits = []
    if actual_k in predicted_ai4:
        hit_digits.append(actual_k)
    if actual_e in predicted_ai4 and actual_e not in hit_digits:
        hit_digits.append(actual_e)

    status_ai = "HIT" if hit_digits else "LOSE"
    status_bbfs = "HIT" if (actual_k in predicted_bbfs7 and actual_e in predicted_bbfs7 and not is_twin) else "LOSE"

    # Penyesuaian Penalti & Reward
    penalized = []
    rewarded = []
    calibrated_weights = dict(weights_t_minus_1)

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

    # Prediksi untuk putaran BERIKUTNYA (setelah result T masuk)
    full_history_2d = [
        (int(r[2]), int(r[3]))
        for r in results_4d
        if len(r) == 4 and r.isdigit()
    ]
    next_ranked, next_weights = rank_digits(full_history_2d)

    return {
        "actual_result": last_full,
        "actual_2d": f"{actual_k}{actual_e}",
        "is_twin": is_twin,
        "previous_prediction": {
            "ai4": predicted_ai4,
            "bbfs7": predicted_bbfs7
        },
        "status_ai": status_ai,
        "status_bbfs": status_bbfs,
        "hit_digits": hit_digits,
        "penalized_methods": penalized,
        "rewarded_methods": rewarded,
        "calibrated_weights": calibrated_weights,
        "next_prediction": {
            "ai3": next_ranked[:3],
            "ai4": next_ranked[:4],
            "ai5": next_ranked[:5],
            "ai6": next_ranked[:6],
            "bbfs6": next_ranked[:6],
            "bbfs7": next_ranked[:7],
            "bbfs8": next_ranked[:8],
            "bbfs9": next_ranked[:9]
        }
    }
