"""NewEra backend engine.

Correctness rules:
- AI weights are independent per tier.
- A method with zero signal abstains (no vote, reward, or penalty).
- BBFS sets are non-twin; twin results are losses unless an explicit twin line is bet.
- Persisted ``next_prediction`` is the state audited on the next draw.
- Probability-like fields are normalized distributions.
"""

import itertools
import math
from collections import defaultdict
from typing import Dict, List, Tuple

INDEX_MAP = {0: 5, 1: 6, 2: 7, 3: 8, 4: 9, 5: 0, 6: 1, 7: 2, 8: 3, 9: 4}
MISTIK_LAMA = {0: 1, 1: 0, 2: 5, 3: 8, 4: 7, 5: 2, 6: 9, 7: 4, 8: 3, 9: 6}
MISTIK_BARU = {0: 8, 1: 7, 2: 6, 3: 9, 4: 5, 5: 4, 6: 2, 7: 1, 8: 0, 9: 3}
AI_SIZES = (3, 4, 5, 6)
BBFS_SIZES = (6, 7, 8, 9)
ENGINE_VERSION = "2026.09.11-v2"


def _has_signal(scores: Dict[int, float]) -> bool:
    return any(math.isfinite(float(v)) and float(v) > 0 for v in scores.values())


def _normalize(raw: Dict) -> Dict:
    clean = {k: max(0.0, float(v)) for k, v in raw.items()}
    total = sum(clean.values())
    if not clean:
        return {}
    if total <= 0:
        p = 1.0 / len(clean)
        return {k: p for k in clean}
    return {k: v / total for k, v in clean.items()}


def _get_saved_tier(mapping: Dict, tier: int, default=None):
    if not isinstance(mapping, dict):
        return default
    return mapping.get(tier, mapping.get(str(tier), default))


def get_momentum_scores(history_2d: List[Tuple[int, int]], window_size: int = 20, decay: float = 0.08) -> Dict[int, float]:
    scores = {d: 0.0 for d in range(10)}
    sub = history_2d[-window_size:]
    n = len(sub)
    for idx, (k, e) in enumerate(sub):
        w = math.exp(decay * (idx - n + 1))
        scores[k] += w
        scores[e] += w
    return scores


def get_markov_scores(history_2d: List[Tuple[int, int]], lookback: int = 150) -> Dict[int, float]:
    scores = {d: 0.0 for d in range(10)}
    if len(history_2d) < 2:
        return scores
    sub = history_2d[-lookback:]
    last_k, last_e = sub[-1]
    for i in range(len(sub) - 1):
        pk, pe = sub[i]
        nk, ne = sub[i + 1]
        if pk == last_k:
            scores[nk] += 1.0
        if pe == last_e:
            scores[ne] += 1.0
    return scores


def get_delta_scores(history_2d: List[Tuple[int, int]], window_size: int = 15) -> Dict[int, float]:
    scores = {d: 0.0 for d in range(10)}
    if len(history_2d) < 2:
        return scores
    sub = history_2d[-window_size:]
    last_k, last_e = sub[-1]
    counts = defaultdict(int)
    for i in range(len(sub) - 1):
        pk, pe = sub[i]
        nk, ne = sub[i + 1]
        counts[(nk - pk) % 10] += 1
        counts[(ne - pe) % 10] += 1
    for delta, count in counts.items():
        scores[(last_k + delta) % 10] += float(count)
        scores[(last_e + delta) % 10] += float(count)
    return scores


def get_mistik_scores(history_2d: List[Tuple[int, int]], eval_window: int = 15) -> Dict[int, float]:
    scores = {d: 0.0 for d in range(10)}
    if len(history_2d) < 3:
        return scores
    sub = history_2d[-eval_window:]
    hits = {"asli": 1.0, "indeks": 1.0, "mistik_lama": 1.0, "mistik_baru": 1.0}
    for i in range(len(sub) - 1):
        pk, pe = sub[i]
        actual = set(sub[i + 1])
        for d in set((pk, pe)):
            if d in actual:
                hits["asli"] += 1
            if INDEX_MAP[d] in actual:
                hits["indeks"] += 1
            if MISTIK_LAMA[d] in actual:
                hits["mistik_lama"] += 1
            if MISTIK_BARU[d] in actual:
                hits["mistik_baru"] += 1
    last_k, last_e = sub[-1]
    for d in set((last_k, last_e)):
        scores[d] += hits["asli"]
        scores[INDEX_MAP[d]] += hits["indeks"]
        scores[MISTIK_LAMA[d]] += hits["mistik_lama"]
        scores[MISTIK_BARU[d]] += hits["mistik_baru"]
    return scores


def _method_functions():
    return {
        "Momentum": get_momentum_scores,
        "Markov": get_markov_scores,
        "Delta": get_delta_scores,
        "Mistik": get_mistik_scores,
    }


def rank_digits(
    history_2d: List[Tuple[int, int]],
    rolling_window: int = 20,
    tier_size: int = 4,
    custom_weights: Dict[str, float] = None,
) -> Tuple[List[int], Dict[str, float]]:
    methods = _method_functions()
    if custom_weights:
        weights = {name: max(0.0, float(custom_weights.get(name, 0.0))) for name in methods}
    else:
        weights = {name: 1.0 for name in methods}
        if len(history_2d) > rolling_window + 5:
            start = len(history_2d) - rolling_window
            for name, func in methods.items():
                hits = 0
                evaluated = 0
                for target_idx in range(start, len(history_2d)):
                    scores = func(history_2d[:target_idx])
                    if not _has_signal(scores):
                        continue
                    evaluated += 1
                    actual = set(history_2d[target_idx])
                    top = sorted(range(10), key=lambda d: (-scores[d], d))[:tier_size]
                    if any(d in actual for d in top):
                        hits += 1
                weights[name] = 0.0 if evaluated == 0 else max(0.5, float(hits + 1))

    combined = {d: 0.0 for d in range(10)}
    for name, func in methods.items():
        raw = func(history_2d)
        if not _has_signal(raw):
            continue
        weight = weights.get(name, 0.0)
        if weight <= 0:
            continue
        max_score = max(raw.values())
        for d in range(10):
            combined[d] += weight * raw[d] / max_score

    ranked = sorted(range(10), key=lambda d: (-combined[d], d))
    return ranked, weights


def compute_bbfs_tier_factor_weights(history_2d: List[Tuple[int, int]], eval_window: int = 15) -> Dict[int, Dict[str, float]]:
    base = {
        6: {"Densitas Pasangan": 10.0, "Transisi Markov": 8.0, "Momentum Posisi": 6.0, "Coverage Proteksi": 4.0},
        7: {"Densitas Pasangan": 8.0, "Transisi Markov": 8.0, "Momentum Posisi": 7.0, "Coverage Proteksi": 7.0},
        8: {"Densitas Pasangan": 7.0, "Transisi Markov": 6.0, "Momentum Posisi": 8.0, "Coverage Proteksi": 9.0},
        9: {"Densitas Pasangan": 5.0, "Transisi Markov": 5.0, "Momentum Posisi": 8.0, "Coverage Proteksi": 12.0},
    }
    weights = {sz: dict(base[sz]) for sz in BBFS_SIZES}
    sub = history_2d[-eval_window:]
    if len(sub) < 3:
        return weights

    for i in range(len(sub) - 1):
        prev_k, prev_e = sub[i]
        act_k, act_e = sub[i + 1]
        before = sub[: i + 1]
        direct = any((k == act_k and e == act_e) or (k == act_e and e == act_k) for k, e in before)
        markov = any(
            (sub[j][0] == prev_k and sub[j + 1][0] == act_k)
            or (sub[j][1] == prev_e and sub[j + 1][1] == act_e)
            for j in range(i)
        )
        recent5 = sub[max(0, i - 4): i + 1]
        momentum = any(k in (act_k, act_e) or e in (act_k, act_e) for k, e in recent5)
        recent_digits = {d for pair in recent5 for d in pair}
        coverage = act_k in recent_digits and act_e in recent_digits

        for sz in BBFS_SIZES:
            if direct:
                weights[sz]["Densitas Pasangan"] += 1.0 if sz == 6 else (0.8 if sz == 7 else 0.6)
            if markov:
                weights[sz]["Transisi Markov"] += 0.9 if sz == 6 else (0.8 if sz == 7 else 0.5)
            if momentum:
                weights[sz]["Momentum Posisi"] += 1.0 if sz >= 8 else 0.7
            if coverage:
                weights[sz]["Coverage Proteksi"] += 1.2 if sz == 9 else (0.9 if sz == 8 else 0.4)

    return {sz: {k: round(v, 2) for k, v in weights[sz].items()} for sz in BBFS_SIZES}


def compute_dedicated_bbfs(history_2d: List[Tuple[int, int]], lookback: int = 50, custom_tier_factor_weights: Dict = None):
    base_weights = compute_bbfs_tier_factor_weights(history_2d)
    tier_weights = {sz: dict(base_weights[sz]) for sz in BBFS_SIZES}
    if custom_tier_factor_weights:
        for sz in BBFS_SIZES:
            custom = _get_saved_tier(custom_tier_factor_weights, sz)
            if isinstance(custom, dict) and custom:
                tier_weights[sz] = {k: float(v) for k, v in custom.items()}

    sub = history_2d[-lookback:]
    n = len(sub)
    if n < 2:
        return {sz: list(range(sz)) for sz in BBFS_SIZES}, [8, 9], list(range(10)), tier_weights

    k_scores = defaultdict(float)
    e_scores = defaultdict(float)
    pair_matrix = [[0.0] * 10 for _ in range(10)]
    k_trans = defaultdict(float)
    e_trans = defaultdict(float)
    last_k, last_e = sub[-1]

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

    result = {}
    for size in BBFS_SIZES:
        w = tier_weights[size]
        total = sum(w.values()) or 1.0
        nw = {k: v / total * 4.0 for k, v in w.items()}
        joint = [[0.0] * 10 for _ in range(10)]
        for k in range(10):
            for e in range(10):
                pos = (k_scores[k] + 1.5 * k_trans[k]) * (e_scores[e] + 1.5 * e_trans[e])
                pair = pair_matrix[k][e] * 3.0
                trans = k_trans[k] * e_trans[e] * 2.0
                coverage = (k_scores[k] + e_scores[e]) * 0.8
                joint[k][e] = (
                    nw["Densitas Pasangan"] * pair
                    + nw["Transisi Markov"] * trans
                    + nw["Momentum Posisi"] * pos
                    + nw["Coverage Proteksi"] * coverage
                )

        best_score = -1.0
        best = tuple(range(size))
        for comb in itertools.combinations(range(10), size):
            score = sum(joint[a][b] for a in comb for b in comb if a != b)
            if score > best_score:
                best_score = score
                best = comb
        contrib = {d: sum(joint[d][x] + joint[x][d] for x in best if x != d) for d in best}
        result[size] = sorted(best, key=lambda d: (-contrib[d], d))

    base_joint = [
        [
            (k_scores[k] + 1.5 * k_trans[k]) * (e_scores[e] + 1.5 * e_trans[e])
            + pair_matrix[k][e] * 3.0
            for e in range(10)
        ]
        for k in range(10)
    ]
    digit_scores = {
        d: sum(base_joint[d][x] + base_joint[x][d] for x in range(10) if x != d)
        for d in range(10)
    }
    ranked = sorted(range(10), key=lambda d: (-digit_scores[d], d))
    return result, ranked[-2:], ranked, tier_weights


def _line_strength(line: str, ranked_digits: List[int]) -> int:
    n = len(ranked_digits)
    a, b = int(line[0]), int(line[1])
    try:
        sa = n - ranked_digits.index(a)
    except ValueError:
        sa = 0
    try:
        sb = n - ranked_digits.index(b)
    except ValueError:
        sb = 0
    return sa + sb


def generate_smart_trim(bbfs7_digits: List[int]) -> Dict[str, List[str]]:
    ranked = list(dict.fromkeys(bbfs7_digits))[:7]
    bom12 = [f"{a}{b}" for a in ranked[:4] for b in ranked[:4] if a != b]
    bom12.sort(key=lambda line: (-_line_strength(line, ranked), line))
    top10 = bom12[:10]
    invest20 = [f"{a}{b}" for a in ranked[:5] for b in ranked[:5] if a != b]
    invest20.sort(key=lambda line: (-_line_strength(line, ranked), line))
    full42 = [f"{a}{b}" for a in ranked for b in ranked if a != b]
    full42.sort(key=lambda line: (-_line_strength(line, ranked), line))
    top10_set = set(top10)
    medium15 = [line for line in full42 if line not in top10_set][:15]
    used = set(top10 + medium15)
    cadangan = [line for line in full42 if line not in used]
    return {"top10": top10, "medium15": medium15, "cadangan": cadangan, "bom12": bom12, "invest20": invest20, "full42": full42}


def generate_wheeling_system(digits: List[int]) -> Dict:
    unique = list(dict.fromkeys(digits))
    d = unique[:7]
    for value in range(10):
        if len(d) >= 7:
            break
        if value not in d:
            d.append(value)

    wheel3_idx = [
        [0, 1, 2], [0, 3, 4], [0, 5, 6], [1, 3, 5], [1, 4, 6],
        [2, 3, 6], [2, 4, 5], [0, 1, 4], [0, 2, 5], [0, 3, 6],
        [1, 2, 3], [1, 5, 6], [2, 4, 6], [3, 4, 5], [0, 1, 3],
    ]
    wheel4_idx = [
        [0, 1, 2, 3], [0, 1, 4, 5], [0, 2, 4, 6], [0, 3, 5, 6],
        [1, 2, 5, 6], [1, 3, 4, 6], [2, 3, 4, 5], [0, 1, 2, 4],
        [0, 1, 2, 5], [0, 1, 2, 6], [0, 1, 3, 4], [0, 1, 3, 5],
        [0, 2, 3, 6], [0, 4, 5, 6],
    ]
    wheel3 = ["".join(str(d[i]) for i in row) for row in wheel3_idx]
    wheel4 = ["".join(str(d[i]) for i in row) for row in wheel4_idx]
    full3 = ["".join(str(d[i]) for i in comb) for comb in itertools.combinations(range(7), 3)]
    full4 = ["".join(str(d[i]) for i in comb) for comb in itertools.combinations(range(7), 4)]
    return {
        "wheel_3d": wheel3,
        "wheel_3d_full": full3,
        "wheel_4d": wheel4,
        "wheel_4d_full": full4,
        "guarantee_3d": "Coverage subset: setiap pasangan digit tercakup; bukan jaminan urutan straight 3D",
        "guarantee_4d": "Coverage subset: setiap triplet digit tercakup; bukan jaminan urutan straight 4D",
    }


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
NUM_TO_SHIO_2026 = {num: item for item in SHIO_2026_DATA for num in item["numbers"]}


def get_shio_2026(val_2d) -> Dict:
    try:
        value = int(val_2d)
    except (TypeError, ValueError):
        return SHIO_2026_DATA[0]
    key = f"{value % 100:02d}"
    if key in NUM_TO_SHIO_2026:
        return NUM_TO_SHIO_2026[key]
    value = 100 if value == 0 else value
    rem = value % 12 or 12
    return SHIO_2026_DATA[rem - 1]


def compute_biji(k: int, e: int) -> int:
    if k == 0 and e == 0:
        return 0
    total = k + e
    while total >= 10:
        total = total // 10 + total % 10
    return total


def _get_parity(k: int, e: int) -> str:
    return f"{'Genap' if k % 2 == 0 else 'Ganjil'}-{'Genap' if e % 2 == 0 else 'Ganjil'}"


def generate_sniper_trim(digits: List[int], paito_pred: Dict, include_twins: bool = False) -> Dict:
    unique = list(dict.fromkeys(digits))
    lines = [f"{a}{b}" for a in unique for b in unique if include_twins or a != b]
    top_biji = set(paito_pred.get("top_biji", []))
    top_shio = set(paito_pred.get("top_shios", []))
    primary_parity = paito_pred.get("primary_parity", "")
    top, secondary, super_shio, reserve = [], [], [], []
    for line in lines:
        k, e = int(line[0]), int(line[1])
        hit_biji = compute_biji(k, e) in top_biji
        hit_parity = _get_parity(k, e) == primary_parity
        hit_shio = get_shio_2026(k * 10 + e)["no"] in top_shio
        if hit_biji and hit_parity:
            top.append(line)
            if hit_shio:
                super_shio.append(line)
        elif hit_biji:
            secondary.append(line)
        else:
            reserve.append(line)
    kept = len(top) + len(secondary)
    efficiency = round((len(lines) - kept) / len(lines) * 100) if lines else 0
    return {
        "sniper_top": top,
        "sniper_secondary": secondary,
        "super_sniper_shio": super_shio,
        "cadangan": reserve,
        "efficiency_pct": efficiency,
    }


def _circular_delta(prev: int, curr: int) -> int:
    delta = (curr - prev) % 10
    if delta > 5:
        delta -= 10
    return 0 if delta == 5 else delta


def analyze_pola_tarung(history_2d: List[Tuple[int, int]], lookback: int = 30) -> Dict:
    sub = history_2d[-lookback:]
    n = len(sub)
    k_scores = {d: 0.0 for d in range(10)}
    e_scores = {d: 0.0 for d in range(10)}
    if n < 2:
        ranked = list(range(10))
        return {
            "ranked_kepala": ranked,
            "ranked_ekor": ranked,
            "kepala_direction": "STABIL",
            "ekor_direction": "STABIL",
            "tarung_3x3": [f"{k}{e}" for k in ranked[:3] for e in ranked[:3]],
            "tarung_4x4": [f"{k}{e}" for k in ranked[:4] for e in ranked[:4]],
            "tarung_5x5": [f"{k}{e}" for k in ranked[:5] for e in ranked[:5]],
        }

    last_k, last_e = sub[-1]
    k_drift = e_drift = total_w = 0.0
    for i in range(1, n):
        w = math.exp(0.08 * (i - n + 1))
        k_drift += _circular_delta(sub[i - 1][0], sub[i][0]) * w
        e_drift += _circular_delta(sub[i - 1][1], sub[i][1]) * w
        total_w += w
        if sub[i - 1][0] == last_k:
            k_scores[sub[i][0]] += 3.5
        if sub[i - 1][1] == last_e:
            e_scores[sub[i][1]] += 3.5
    for idx, (k, e) in enumerate(sub):
        w = math.exp(0.08 * (idx - n + 1))
        k_scores[k] += 2.0 * w
        e_scores[e] += 2.0 * w

    k_step = (sub[-1][0] - sub[-2][0]) % 10
    e_step = (sub[-1][1] - sub[-2][1]) % 10
    k_scores[(last_k + k_step) % 10] += 2.5
    e_scores[(last_e + e_step) % 10] += 2.5
    ranked_k = sorted(range(10), key=lambda d: (-k_scores[d], d))
    ranked_e = sorted(range(10), key=lambda d: (-e_scores[d], d))
    k_avg = k_drift / total_w if total_w else 0.0
    e_avg = e_drift / total_w if total_w else 0.0
    k_dir = "NAIK" if k_avg > 0.6 else ("TURUN" if k_avg < -0.6 else "STABIL")
    e_dir = "NAIK" if e_avg > 0.6 else ("TURUN" if e_avg < -0.6 else "STABIL")
    return {
        "ranked_kepala": ranked_k,
        "ranked_ekor": ranked_e,
        "kepala_direction": k_dir,
        "ekor_direction": e_dir,
        "tarung_3x3": [f"{k}{e}" for k in ranked_k[:3] for e in ranked_e[:3]],
        "tarung_4x4": [f"{k}{e}" for k in ranked_k[:4] for e in ranked_e[:4]],
        "tarung_5x5": [f"{k}{e}" for k in ranked_k[:5] for e in ranked_e[:5]],
    }


def _top_biji_targets(history_2d: List[Tuple[int, int]]) -> Tuple[List[int], float]:
    seq = [compute_biji(k, e) for k, e in history_2d[-30:]]
    if len(seq) < 2:
        return [0, 1, 2], 0.0
    step_freq = {d: 0 for d in range(10)}
    freq = {d: 0 for d in range(10)}
    for b in seq:
        freq[b] += 1
    for i in range(1, len(seq)):
        step_freq[(seq[i] - seq[i - 1]) % 10] += 1
    best_step = max(range(10), key=lambda d: (step_freq[d], -d))
    last = seq[-1]
    targets = []
    for d in ((last + best_step) % 10, (last - best_step) % 10, (9 - last) % 10):
        if d not in targets:
            targets.append(d)
    for d in sorted(range(10), key=lambda x: (-freq[x], x)):
        if len(targets) >= 3:
            break
        if d not in targets:
            targets.append(d)
    dominance = step_freq[best_step] / max(1, len(seq) - 1)
    return targets[:3], dominance


def predict_paito_macro(history_2d: List[Tuple[int, int]], lookback: int = 50) -> Dict:
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
            "shio_probabilities": {str(s): 1.0 / 12 for s in range(1, 13)},
            "jalur_probabilities": {"1": 1.0 / 3, "2": 1.0 / 3, "3": 1.0 / 3},
            "overdue_shios": [],
            "overdue_alerts": [],
            "confidence_score": 50,
        }

    sub = history_2d[-lookback:]
    top_biji, biji_dom = _top_biji_targets(sub)
    biji_raw = {d: (0.01 if d == 0 else 0.11) * (2.0 if d in top_biji else 1.0) for d in range(10)}
    biji_probs = _normalize(biji_raw)

    parity_states = ["Genap-Genap", "Genap-Ganjil", "Ganjil-Genap", "Ganjil-Ganjil"]
    parity_hist = [_get_parity(k, e) for k, e in sub]
    parity_raw = {p: 1.0 for p in parity_states}
    for idx, p in enumerate(parity_hist):
        parity_raw[p] += math.exp(0.08 * (idx - len(parity_hist) + 1))
    parity_probs = _normalize(parity_raw)
    primary_parity = max(parity_states, key=lambda p: parity_probs[p])

    mag_hist = ["Besar" if 10 * k + e >= 50 else "Kecil" for k, e in sub]
    mag_raw = {"Besar": 1.0, "Kecil": 1.0}
    for idx, state in enumerate(mag_hist):
        mag_raw[state] += math.exp(0.08 * (idx - len(mag_hist) + 1))
    mag_probs = _normalize(mag_raw)
    primary_mag = max(mag_probs, key=mag_probs.get)

    shio_hist = [get_shio_2026(10 * k + e)["no"] for k, e in sub]
    shio_raw = {s: 1.0 for s in range(1, 13)}
    for idx, s in enumerate(shio_hist):
        shio_raw[s] += math.exp(0.06 * (idx - len(shio_hist) + 1))
    shio_probs = _normalize(shio_raw)
    top_shios = sorted(range(1, 13), key=lambda s: (-shio_probs[s], s))[:3]
    jalur_raw = {
        j: sum(shio_probs[s] for s in range(1, 13) if get_shio_2026(s)["jalur"] == j)
        for j in (1, 2, 3)
    }
    # Map shio number to jalur directly; get_shio_2026(s) is valid for 01..12.
    jalur_probs = _normalize(jalur_raw)
    primary_jalur = max((1, 2, 3), key=lambda j: jalur_probs[j])

    confidence = round(
        100 * (
            0.25 * max(parity_probs.values())
            + 0.25 * max(mag_probs.values())
            + 0.25 * max(jalur_probs.values())
            + 0.25 * min(1.0, biji_dom)
        )
    )
    confidence = max(30, min(90, confidence))

    return {
        "top_biji": top_biji,
        "biji_probabilities": {str(k): v for k, v in biji_probs.items()},
        "primary_parity": primary_parity,
        "parity_probabilities": parity_probs,
        "primary_magnitude": primary_mag,
        "magnitude_probabilities": mag_probs,
        "top_shios": top_shios,
        "primary_jalur": primary_jalur,
        "shio_probabilities": {str(k): v for k, v in shio_probs.items()},
        "jalur_probabilities": {str(k): v for k, v in jalur_probs.items()},
        "overdue_shios": [],
        "overdue_alerts": [],
        "confidence_score": confidence,
    }


def synthesize_paito_bbfs7(history_2d: List[Tuple[int, int]], paito_pred: Dict = None) -> Dict:
    paito_pred = paito_pred or predict_paito_macro(history_2d)
    sub = history_2d[-50:]
    top_biji = set(paito_pred.get("top_biji", []))
    top_shio = set(paito_pred.get("top_shios", []))
    primary_parity = paito_pred.get("primary_parity", "Genap-Ganjil")
    pair = [[0.0] * 10 for _ in range(10)]
    for k, e in sub:
        pair[k][e] += 1.0
        pair[e][k] += 0.5
    scores = {d: 0.0 for d in range(10)}
    n = len(sub)
    for d in range(10):
        for idx, (k, e) in enumerate(sub):
            w = math.exp(0.06 * (idx - n + 1)) if n else 1.0
            if k == d:
                scores[d] += 1.8 * w
            if e == d:
                scores[d] += 1.5 * w
        scores[d] += 1.4 * sum(1 for o in range(10) if o != d and compute_biji(d, o) in top_biji)
        scores[d] += 1.0 * sum(1 for o in range(10) if get_shio_2026(10 * d + o)["no"] in top_shio)
        expected_head = primary_parity.startswith("Genap")
        if (d % 2 == 0) == expected_head:
            scores[d] += 2.0

    best = tuple(range(7))
    best_score = -1e18
    for comb in itertools.combinations(range(10), 7):
        value = sum(scores[d] for d in comb)
        value += 0.8 * sum(pair[a][b] + pair[b][a] for a, b in itertools.combinations(comb, 2))
        besar = sum(d >= 5 for d in comb)
        genap = sum(d % 2 == 0 for d in comb)
        value -= max(0.0, abs(besar - 3.5) - 0.5) * 4.0
        value -= max(0.0, abs(genap - 3.5) - 0.5) * 4.0
        if value > best_score:
            best_score = value
            best = comb
    internal = {d: scores[d] + sum(pair[d][o] + pair[o][d] for o in best if o != d) for d in best}
    ranked = sorted(best, key=lambda d: (-internal[d], d))
    full42 = [f"{a}{b}" for a in ranked for b in ranked if a != b]
    bom12 = [f"{a}{b}" for a in ranked[:4] for b in ranked[:4] if a != b]
    invest20 = [f"{a}{b}" for a in ranked[:5] for b in ranked[:5] if a != b]

    def line_score(line: str):
        k, e = int(line[0]), int(line[1])
        score = 0
        if compute_biji(k, e) in top_biji:
            score += 4
        if _get_parity(k, e) == primary_parity:
            score += 3
        if get_shio_2026(10 * k + e)["no"] in top_shio:
            score += 2
        return score

    nuklir6 = sorted(full42, key=lambda line: (-line_score(line), line))[:6]
    return {
        "digits": ranked,
        "ranked7": ranked,
        "nuklir6": nuklir6,
        "bom12": bom12,
        "invest20": invest20,
        "full42": full42,
        "twin7": [f"{d}{d}" for d in ranked],
        "dead_digits": [d for d in range(10) if d not in ranked],
    }


def _tune_weight(prev: float, hit: bool) -> float:
    prev = float(prev) if prev and math.isfinite(float(prev)) else 1.0
    target = prev * math.exp(0.10 if hit else -0.10)
    value = 0.7 * prev + 0.3 * target
    return round(max(0.5, min(25.0, value)), 2)


def _tune_bbfs_weights(base: Dict[str, float], calibrate: bool) -> Dict[str, float]:
    out = {k: float(v) for k, v in (base or {}).items()}
    if not calibrate:
        return out
    if "Coverage Proteksi" in out:
        out["Coverage Proteksi"] *= 1.08
    if "Momentum Posisi" in out:
        out["Momentum Posisi"] *= 1.04
    if "Densitas Pasangan" in out:
        out["Densitas Pasangan"] *= 0.96
    if "Transisi Markov" in out:
        out["Transisi Markov"] *= 0.96
    return {k: round(max(2.0, min(24.0, v)), 2) for k, v in out.items()}


def audit_and_tune(results_4d: List[str], saved_prediction: Dict = None) -> Dict:
    valid = [r for r in results_4d if len(r) == 4 and r.isdigit()]
    if len(valid) < 15:
        return {}

    last_full = valid[-1]
    actual_k, actual_e = int(last_full[2]), int(last_full[3])
    is_twin = actual_k == actual_e
    history_before = [(int(r[2]), int(r[3])) for r in valid[:-1]]
    full_history = [(int(r[2]), int(r[3])) for r in valid]
    saved_prediction = saved_prediction if isinstance(saved_prediction, dict) else {}

    ranked_map, prior_weights = {}, {}
    saved_tier_weights = saved_prediction.get("tier_method_weights", {})
    for sz in AI_SIZES:
        custom = _get_saved_tier(saved_tier_weights, sz)
        ranked, weights = rank_digits(history_before, tier_size=sz, custom_weights=custom)
        ranked_map[sz] = ranked
        prior_weights[sz] = dict(custom or weights)

    current_bbfs, current_dead, _, current_bbfs_weights = compute_dedicated_bbfs(
        history_before,
        custom_tier_factor_weights=saved_prediction.get("bbfs_tier_weights"),
    )

    predicted_ai = {
        sz: list(saved_prediction.get(f"ai{sz}") or ranked_map[sz][:sz])
        for sz in AI_SIZES
    }
    predicted_bbfs = {
        sz: list(saved_prediction.get(f"bbfs{sz}") or current_bbfs[sz])
        for sz in BBFS_SIZES
    }

    ai_audits = {}
    for sz in AI_SIZES:
        hit = actual_k in predicted_ai[sz] or actual_e in predicted_ai[sz]
        ai_audits[f"ai{sz}"] = {
            "parameter": f"AI-{sz}",
            "status": "HIT" if hit else "LOSE",
            "action": "FREEZE" if hit else "CALIBRATED",
            "tuning_directive": "Freeze bobot tier" if hit else "Kalibrasi bobot tier",
            "digits": predicted_ai[sz],
        }

    ai4 = predicted_ai[4]
    hit_digits = []
    if actual_k in ai4:
        hit_digits.append(actual_k)
    if actual_e in ai4 and actual_e not in hit_digits:
        hit_digits.append(actual_e)
    status_ai = "HIT" if hit_digits else "LOSE"

    method_scores = {name: func(history_before) for name, func in _method_functions().items()}
    next_ai_weights = {}
    rewarded, penalized = set(), set()
    for sz in AI_SIZES:
        base = dict(prior_weights[sz])
        if ai_audits[f"ai{sz}"]["action"] == "CALIBRATED":
            for name, scores in method_scores.items():
                if not _has_signal(scores):
                    continue
                top = sorted(range(10), key=lambda d: (-scores[d], d))[:sz]
                hit = actual_k in top or actual_e in top
                base[name] = _tune_weight(base.get(name, 1.0), hit)
                (rewarded if hit else penalized).add(name)
        next_ai_weights[sz] = base

    bbfs_audits = {}
    next_bbfs_factor_weights = {}
    for sz in BBFS_SIZES:
        tier_set = set(predicted_bbfs[sz])
        hit = (not is_twin) and actual_k in tier_set and actual_e in tier_set
        bbfs_audits[f"bbfs{sz}"] = {
            "parameter": f"BBFS-{sz} ({sz * (sz - 1)} line non-twin)",
            "status": "HIT" if hit else "LOSE",
            "action": "FREEZE" if hit else "CALIBRATED",
            "tuning_directive": "Freeze faktor tier" if hit else "Kalibrasi faktor tier",
            "digits": predicted_bbfs[sz],
        }
        old = _get_saved_tier(saved_prediction.get("bbfs_tier_weights", {}), sz, current_bbfs_weights[sz])
        next_bbfs_factor_weights[sz] = _tune_bbfs_weights(old, not hit)

    bbfs7_set = set(predicted_bbfs[7])
    status_bbfs = "HIT" if ((not is_twin) and actual_k in bbfs7_set and actual_e in bbfs7_set) else "LOSE"

    next_ranked, final_ai_weights = {}, {}
    for sz in AI_SIZES:
        ranked, weights = rank_digits(full_history, tier_size=sz, custom_weights=next_ai_weights[sz])
        next_ranked[sz] = ranked
        final_ai_weights[sz] = weights

    next_bbfs, next_dead, _, final_bbfs_weights = compute_dedicated_bbfs(
        full_history,
        custom_tier_factor_weights=next_bbfs_factor_weights,
    )

    predicted_bbfs7 = predicted_bbfs[7]
    trimmer = generate_smart_trim(predicted_bbfs7)
    target_2d = f"{actual_k}{actual_e}"
    if (not is_twin) and target_2d in trimmer["top10"]:
        trimmer_zone = "BOM_10"
    elif (not is_twin) and target_2d in trimmer["medium15"]:
        trimmer_zone = "MEDIUM_15"
    elif (not is_twin) and target_2d in trimmer["cadangan"]:
        trimmer_zone = "CADANGAN"
    else:
        trimmer_zone = "MISSED"

    dead_from_saved = saved_prediction.get("dead_digits") or current_dead
    dead_clean = actual_k not in dead_from_saved and actual_e not in dead_from_saved

    previous_paito = saved_prediction.get("paito") or predict_paito_macro(history_before)
    actual_biji = compute_biji(actual_k, actual_e)
    actual_parity = _get_parity(actual_k, actual_e)
    actual_mag = "Besar" if 10 * actual_k + actual_e >= 50 else "Kecil"
    actual_shio = get_shio_2026(10 * actual_k + actual_e)
    sniper_prev = generate_sniper_trim(predicted_bbfs7, previous_paito, include_twins=False)
    paito_audit = {
        "actual_biji": actual_biji,
        "actual_parity": actual_parity,
        "actual_magnitude": actual_mag,
        "actual_shio": actual_shio["no"],
        "actual_shio_name": f"{actual_shio['emoji']} {actual_shio['name']}",
        "actual_jalur": actual_shio["jalur"],
        "hit_biji": actual_biji in previous_paito.get("top_biji", []),
        "hit_parity": actual_parity == previous_paito.get("primary_parity"),
        "hit_magnitude": actual_mag == previous_paito.get("primary_magnitude"),
        "hit_shio": actual_shio["no"] in previous_paito.get("top_shios", []),
        "hit_jalur": actual_shio["jalur"] == previous_paito.get("primary_jalur"),
        "sniper_status": (
            "SUPER_BOM_HIT" if (not is_twin and target_2d in sniper_prev.get("super_sniper_shio", []))
            else "BOM_HIT" if (not is_twin and target_2d in sniper_prev.get("sniper_top", []))
            else "SECONDARY_HIT" if (not is_twin and target_2d in sniper_prev.get("sniper_secondary", []))
            else "MISSED"
        ),
    }

    next_paito = predict_paito_macro(full_history)
    next_paito_bbfs7 = synthesize_paito_bbfs7(full_history, next_paito)
    next_wheel = generate_wheeling_system(next_paito_bbfs7["digits"])

    ai_calibrated = [f"AI-{sz}" for sz in AI_SIZES if ai_audits[f"ai{sz}"]["action"] == "CALIBRATED"]
    bbfs_calibrated = [f"BBFS-{sz}" for sz in BBFS_SIZES if bbfs_audits[f"bbfs{sz}"]["action"] == "CALIBRATED"]

    return {
        "actual_result": last_full,
        "actual_2d": target_2d,
        "is_twin": is_twin,
        "paito_audit": paito_audit,
        "previous_prediction": {
            "ai4": predicted_ai[4],
            "bbfs7": predicted_bbfs[7],
            "dead_digits": dead_from_saved,
        },
        "status_ai": status_ai,
        "status_bbfs": status_bbfs,
        "hit_digits": hit_digits,
        "ai_tuning": {
            "tier_audits": ai_audits,
            "status_ai4": status_ai,
            "hit_digits": hit_digits,
            "rewarded_methods": sorted(rewarded),
            "penalized_methods": sorted(penalized),
            "calibrated_weights": final_ai_weights[4],
            "tier_method_weights": {str(k): v for k, v in final_ai_weights.items()},
            "recommended_tier": "AI-3" if ai_audits["ai3"]["action"] == "FREEZE" else "AI-4",
            "action_summary": "Semua tier AI freeze" if not ai_calibrated else f"{', '.join(ai_calibrated)} dikalibrasi per-tier",
        },
        "bbfs_tuning": {
            "tier_audits": bbfs_audits,
            "status_bbfs7": status_bbfs,
            "dead_digits": dead_from_saved,
            "dead_digits_clean": dead_clean,
            "trimmer_zone": trimmer_zone,
            "is_twin": is_twin,
            "twin_status": "TWIN_UNPROTECTED" if is_twin else "NON_TWIN",
            "rewarded_factor": "Freeze faktor tier hit" if status_bbfs == "HIT" else "Coverage/Momentum diperkuat pada miss",
            "penalized_factor": "None" if status_bbfs == "HIT" else "Densitas/Transisi lama dikurangi pada miss",
            "recommended_tier": "Twin Guard" if is_twin else ("BBFS-6" if bbfs_audits["bbfs6"]["action"] == "FREEZE" else "BBFS-8" if status_bbfs == "LOSE" else "BBFS-7"),
            "action_summary": "Twin = LOSE pada BBFS non-twin; semua tier dikalibrasi" if is_twin else ("Semua tier BBFS freeze" if not bbfs_calibrated else f"{', '.join(bbfs_calibrated)} dikalibrasi"),
            "tier_factor_weights": {str(k): v for k, v in final_bbfs_weights.items()},
        },
        "penalized_methods": sorted(penalized),
        "rewarded_methods": sorted(rewarded),
        "calibrated_weights": final_ai_weights[4],
        "next_prediction": {
            "engine_version": ENGINE_VERSION,
            "basis_draw_count": len(full_history),
            "basis_last_draw": last_full,
            "ai3": next_ranked[3][:3],
            "ai4": next_ranked[4][:4],
            "ai5": next_ranked[5][:5],
            "ai6": next_ranked[6][:6],
            "tier_method_weights": {str(k): v for k, v in final_ai_weights.items()},
            "bbfs6": next_bbfs[6],
            "bbfs7": next_bbfs[7],
            "bbfs8": next_bbfs[8],
            "bbfs9": next_bbfs[9],
            "bbfs_tier_weights": {str(k): v for k, v in final_bbfs_weights.items()},
            "dead_digits": next_dead,
            "paito": next_paito,
            "pola_tarung": analyze_pola_tarung(full_history),
            "paito_bbfs7": next_paito_bbfs7,
            "wheeling7": next_wheel,
        },
    }
