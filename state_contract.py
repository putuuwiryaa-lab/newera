"""Structural validation of persisted production predictions (no prediction tuning)."""

import math

AI_SIZES = (3, 4, 5, 6)
BBFS_SIZES = (6, 7, 8, 9)
METHODS = ("Momentum", "Markov", "Delta", "Mistik")
FACTORS = ("Densitas Pasangan", "Transisi Markov", "Momentum Posisi", "Coverage Proteksi")
PARITIES = ("Genap-Genap", "Genap-Ganjil", "Ganjil-Genap", "Ganjil-Ganjil")


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def count(value):
    return finite_number(value) and value >= 0 and int(value) == value


def digits(value, length, low=0, high=9):
    return (isinstance(value, list) and len(value) == length
            and all(count(d) and low <= d <= high for d in value)
            and len(set(value)) == length)


def prediction_integrity_errors(prediction):
    if not isinstance(prediction, dict):
        return ["prediction.missing"]
    errors = []
    for family, sizes in (("ai", AI_SIZES), ("bbfs", BBFS_SIZES)):
        for size in sizes:
            if not digits(prediction.get(f"{family}{size}"), size):
                errors.append(f"prediction.{family}{size}")
    if not digits(prediction.get("dead_digits"), 2):
        errors.append("prediction.dead_digits")
    for name, sizes, keys in (("tier_method_weights", AI_SIZES, METHODS), ("bbfs_tier_weights", BBFS_SIZES, FACTORS)):
        weights = prediction.get(name)
        for size in sizes:
            row = weights.get(str(size), weights.get(size)) if isinstance(weights, dict) else None
            if (not isinstance(row, dict) or set(row) != set(keys)
                    or not all(finite_number(v) and v >= 0 for v in row.values())
                    or sum(row.values()) <= 0):
                errors.append(f"prediction.{name}.{size}")
    paito = prediction.get("paito")
    if not isinstance(paito, dict):
        errors.append("prediction.paito")
    else:
        for name, length, low, high in (("top_biji", 3, 0, 9), ("top_shios", 3, 1, 12)):
            if not digits(paito.get(name), length, low, high):
                errors.append(f"prediction.paito.{name}")
        for name, choices in (("primary_parity", PARITIES), ("primary_magnitude", ("Besar", "Kecil")), ("primary_jalur", (1, 2, 3))):
            if paito.get(name) not in choices:
                errors.append(f"prediction.paito.{name}")
        for name, keys in (("biji", range(10)), ("parity", PARITIES), ("magnitude", ("Besar", "Kecil")), ("shio", range(1, 13)), ("jalur", range(1, 4))):
            row = paito.get(f"{name}_probabilities")
            if (not isinstance(row, dict) or set(map(str, row)) != set(map(str, keys))
                    or not all(finite_number(v) and 0 <= v <= 1 for v in row.values())
                    or abs(sum(row.values()) - 1) > 1e-8):
                errors.append(f"prediction.paito.{name}_probabilities")
        if not finite_number(paito.get("confidence_score")) or not 0 <= paito["confidence_score"] <= 100:
            errors.append("prediction.paito.confidence_score")
    # Rankings are additive metadata; older v2 documents remain readable.
    rankings = prediction.get("tier_ranked_digits")
    if rankings is not None:
        for size in AI_SIZES:
            row = rankings.get(str(size), rankings.get(size)) if isinstance(rankings, dict) else None
            if not digits(row, 10) or row[:size] != prediction.get(f"ai{size}"):
                errors.append(f"prediction.tier_ranked_digits.{size}")
    def lines(container, name, size, width=2):
        value = container.get(name) if isinstance(container, dict) else None
        if (not isinstance(value, list) or len(value) != size
                or not all(isinstance(v, str) and len(v) == width and v.isascii() and v.isdigit() for v in value)
                or len(set(value)) != size):
            errors.append(f"prediction.lines.{name}")
    tarung = prediction.get("pola_tarung", {})
    for name in ("ranked_kepala", "ranked_ekor"):
        if not isinstance(tarung, dict) or not digits(tarung.get(name), 10):
            errors.append(f"prediction.pola_tarung.{name}")
    for size in (3, 4, 5):
        lines(tarung, f"tarung_{size}x{size}", size * size)
    bbfs = prediction.get("paito_bbfs7", {})
    if not isinstance(bbfs, dict) or not digits(bbfs.get("digits"), 7):
        errors.append("prediction.paito_bbfs7.digits")
    for name, size in (("nuklir6", 6), ("bom12", 12), ("invest20", 20), ("full42", 42), ("twin7", 7)):
        lines(bbfs, name, size)
    wheel = prediction.get("wheeling7", {})
    for name, size, width in (("wheel_3d", 15, 3), ("wheel_3d_full", 35, 3), ("wheel_4d", 14, 4), ("wheel_4d_full", 35, 4)):
        lines(wheel, name, size, width)
    return errors


def prediction_matches_basis(prediction, engine_version, basis_count, last_draw):
    return (isinstance(prediction, dict)
            and prediction.get("engine_version") == engine_version
            and count(prediction.get("basis_draw_count"))
            and prediction["basis_draw_count"] == basis_count
            and prediction.get("basis_last_draw") == last_draw
            and not prediction_integrity_errors(prediction))
