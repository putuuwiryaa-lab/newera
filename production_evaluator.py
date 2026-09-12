"""Production-engine evaluation for NewEra.

This module replays the same Python production lifecycle used by ``engine.audit_and_tune``
and can then continue incrementally from persisted prediction state. Metrics are diagnostic:
hit rate, uniform baseline, lift, Wilson 95% interval, and multiclass Brier score for Paito.
"""

from __future__ import annotations

import copy
import math
from typing import Dict, Iterable, List

import engine
from state_contract import count, finite_number, prediction_matches_basis

EVALUATOR_VERSION = f"{engine.ENGINE_VERSION}-prod-eval-v1"
DEFAULT_WARMUP = 50
DEFAULT_MAX_DRAWS = 180


def _valid_results(results_4d: Iterable[str]) -> List[str]:
    return [r for r in results_4d if isinstance(r, str) and len(r) == 4 and r.isdigit()]


def _prob(mapping: Dict, key) -> float:
    if not isinstance(mapping, dict):
        return 0.0
    raw = mapping.get(key, mapping.get(str(key), 0.0))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) and value >= 0 else 0.0


def _wilson_pct(hits: int, total: int, z: float = 1.96):
    if total <= 0:
        return [0.0, 0.0]
    p = hits / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (p + z2 / (2.0 * total)) / denom
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * total)) / total) / denom
    return [round(max(0.0, center - margin) * 100.0, 2), round(min(1.0, center + margin) * 100.0, 2)]


def _metric(hits: int, total: int, baseline_sum: float) -> Dict:
    rate = hits / total if total else 0.0
    baseline = baseline_sum / total if total else 0.0
    return {
        "hits": hits,
        "tested": total,
        "hit_rate_pct": round(rate * 100.0, 2),
        "baseline_pct": round(baseline * 100.0, 2),
        "lift_pp": round((rate - baseline) * 100.0, 2),
        "ci95_pct": _wilson_pct(hits, total),
    }


def _uniform_rate(predicate) -> float:
    hits = 0
    for k in range(10):
        for e in range(10):
            if predicate(k, e):
                hits += 1
    return hits / 100.0


def _brier(probs: Dict, actual, classes) -> float:
    total = 0.0
    for cls in classes:
        p = _prob(probs, cls)
        y = 1.0 if cls == actual else 0.0
        total += (p - y) ** 2
    return total


def _new_accumulator(include_live_only: bool = True) -> Dict:
    acc = {
        "tested": 0,
        "twins": 0,
        "replay_draws": 0,
        "live_draws": 0,
        "ai": {str(sz): {"hits": 0} for sz in engine.AI_SIZES},
        "bbfs": {str(sz): {"hits": 0} for sz in engine.BBFS_SIZES},
        "paito": {
            "biji": {"hits": 0, "baseline_sum": 0.0, "brier_sum": 0.0},
            "parity": {"hits": 0, "baseline_sum": 0.0, "brier_sum": 0.0},
            "magnitude": {"hits": 0, "baseline_sum": 0.0, "brier_sum": 0.0},
            "shio": {"hits": 0, "baseline_sum": 0.0, "brier_sum": 0.0},
            "jalur": {"hits": 0, "baseline_sum": 0.0, "brier_sum": 0.0},
        },
        "trimmer": {"bom10": 0, "medium15": 0, "cadangan": 0, "missed": 0},
        "sniper": {
            "active_draws": 0,
            "any_hits": 0,
            "top_hits": 0,
            "secondary_hits": 0,
            "super_hits": 0,
            "baseline_sum": 0.0,
        },
    }
    if include_live_only:
        acc["live_only"] = _new_accumulator(False)
    return acc


def _accumulate(acc: Dict, prediction: Dict, actual_result: str, source: str) -> None:
    if not isinstance(prediction, dict) or len(actual_result) != 4 or not actual_result.isdigit():
        return

    # True prospective performance must remain separable from reconstructed replay.
    if source == "live":
        live_only = acc.get("live_only")
        if not isinstance(live_only, dict):
            live_only = _new_accumulator(False)
            acc["live_only"] = live_only
        _accumulate(live_only, prediction, actual_result, "isolated")

    k, e = int(actual_result[2]), int(actual_result[3])
    is_twin = k == e
    target = f"{k}{e}"
    acc["tested"] += 1
    acc["twins"] += int(is_twin)
    if source == "live":
        acc["live_draws"] += 1
    elif source == "replay":
        acc["replay_draws"] += 1

    for sz in engine.AI_SIZES:
        digits = set(prediction.get(f"ai{sz}", []))
        if k in digits or e in digits:
            acc["ai"][str(sz)]["hits"] += 1

    for sz in engine.BBFS_SIZES:
        digits = set(prediction.get(f"bbfs{sz}", []))
        if (not is_twin) and k in digits and e in digits:
            acc["bbfs"][str(sz)]["hits"] += 1

    paito = prediction.get("paito") if isinstance(prediction.get("paito"), dict) else {}
    actual_biji = engine.compute_biji(k, e)
    actual_parity = engine._get_parity(k, e)
    actual_magnitude = "Besar" if (10 * k + e) >= 50 else "Kecil"
    shio = engine.get_shio_2026(10 * k + e)
    actual_shio = shio["no"]
    actual_jalur = shio["jalur"]

    top_biji = set(paito.get("top_biji", []))
    top_shios = set(paito.get("top_shios", []))
    primary_parity = paito.get("primary_parity")
    primary_magnitude = paito.get("primary_magnitude")
    primary_jalur = paito.get("primary_jalur")

    pacc = acc["paito"]
    pacc["biji"]["hits"] += int(actual_biji in top_biji)
    pacc["biji"]["baseline_sum"] += _uniform_rate(lambda x, y: engine.compute_biji(x, y) in top_biji)
    pacc["biji"]["brier_sum"] += _brier(paito.get("biji_probabilities", {}), actual_biji, range(10))

    pacc["parity"]["hits"] += int(actual_parity == primary_parity)
    pacc["parity"]["baseline_sum"] += _uniform_rate(lambda x, y: engine._get_parity(x, y) == primary_parity)
    parity_classes = ["Genap-Genap", "Genap-Ganjil", "Ganjil-Genap", "Ganjil-Ganjil"]
    pacc["parity"]["brier_sum"] += _brier(paito.get("parity_probabilities", {}), actual_parity, parity_classes)

    pacc["magnitude"]["hits"] += int(actual_magnitude == primary_magnitude)
    pacc["magnitude"]["baseline_sum"] += _uniform_rate(
        lambda x, y: ("Besar" if (10 * x + y) >= 50 else "Kecil") == primary_magnitude
    )
    pacc["magnitude"]["brier_sum"] += _brier(
        paito.get("magnitude_probabilities", {}), actual_magnitude, ["Besar", "Kecil"]
    )

    pacc["shio"]["hits"] += int(actual_shio in top_shios)
    pacc["shio"]["baseline_sum"] += _uniform_rate(
        lambda x, y: engine.get_shio_2026(10 * x + y)["no"] in top_shios
    )
    pacc["shio"]["brier_sum"] += _brier(paito.get("shio_probabilities", {}), actual_shio, range(1, 13))

    pacc["jalur"]["hits"] += int(actual_jalur == primary_jalur)
    pacc["jalur"]["baseline_sum"] += _uniform_rate(
        lambda x, y: engine.get_shio_2026(10 * x + y)["jalur"] == primary_jalur
    )
    pacc["jalur"]["brier_sum"] += _brier(paito.get("jalur_probabilities", {}), actual_jalur, [1, 2, 3])

    bbfs7 = list(prediction.get("bbfs7", []))
    if len(set(bbfs7)) >= 7:
        trim = engine.generate_smart_trim(bbfs7)
        if (not is_twin) and target in trim["top10"]:
            acc["trimmer"]["bom10"] += 1
        elif (not is_twin) and target in trim["medium15"]:
            acc["trimmer"]["medium15"] += 1
        elif (not is_twin) and target in trim["cadangan"]:
            acc["trimmer"]["cadangan"] += 1
        else:
            acc["trimmer"]["missed"] += 1

        sniper = engine.generate_sniper_trim(bbfs7, paito, include_twins=False)
        top = set(sniper.get("sniper_top", []))
        secondary = set(sniper.get("sniper_secondary", []))
        super_lines = set(sniper.get("super_sniper_shio", []))
        active_lines = top | secondary
        if active_lines:
            sacc = acc["sniper"]
            sacc["active_draws"] += 1
            sacc["baseline_sum"] += len(active_lines) / 100.0
            if (not is_twin) and target in active_lines:
                sacc["any_hits"] += 1
            if (not is_twin) and target in top:
                sacc["top_hits"] += 1
            if (not is_twin) and target in secondary:
                sacc["secondary_hits"] += 1
            if (not is_twin) and target in super_lines:
                sacc["super_hits"] += 1


def _build_output(acc: Dict, basis_draw_count: int, basis_last_draw: str, replay_window: int) -> Dict:
    tested = int(acc.get("tested", 0))
    ai_stats = {}
    for sz in engine.AI_SIZES:
        baseline = 1.0 - ((10 - sz) / 10.0) ** 2
        ai_stats[str(sz)] = _metric(acc["ai"][str(sz)]["hits"], tested, baseline * tested)

    bbfs_stats = {}
    for sz in engine.BBFS_SIZES:
        baseline = sz * (sz - 1) / 100.0
        bbfs_stats[str(sz)] = _metric(acc["bbfs"][str(sz)]["hits"], tested, baseline * tested)

    paito_stats = {}
    for name, raw in acc["paito"].items():
        metric = _metric(raw["hits"], tested, raw["baseline_sum"])
        metric["brier_score"] = round(raw["brier_sum"] / tested, 6) if tested else 0.0
        paito_stats[name] = metric

    sniper = acc["sniper"]
    active = int(sniper["active_draws"])
    sniper_metric = _metric(sniper["any_hits"], active, sniper["baseline_sum"])
    sniper_metric.update({
        "active_draws": active,
        "participation_rate_pct": round((active / tested) * 100.0, 2) if tested else 0.0,
        "top_hits": sniper["top_hits"],
        "secondary_hits": sniper["secondary_hits"],
        "super_hits": sniper["super_hits"],
    })

    live_acc = acc.get("live_only") if isinstance(acc.get("live_only"), dict) else None
    live_tested = int(live_acc.get("tested", 0)) if live_acc else 0
    prospective = {
        "tested_draws": live_tested,
        "minimum_draws": 30,
        "ready": live_tested >= 30,
        "twin_count": int(live_acc.get("twins", 0)) if live_acc else 0,
        "ai_stats": {},
        "bbfs_stats": {},
        "paito_stats": {},
        "trimmer_stats": {},
        "sniper_stats": {},
    }
    if live_acc and live_tested > 0:
        live_output = _build_output(live_acc, basis_draw_count, basis_last_draw, 0)
        prospective.update({
            "ai_stats": live_output["ai_stats"],
            "bbfs_stats": live_output["bbfs_stats"],
            "paito_stats": live_output["paito_stats"],
            "trimmer_stats": live_output["trimmer_stats"],
            "sniper_stats": live_output["sniper_stats"],
        })

    return {
        "evaluator_version": EVALUATOR_VERSION,
        "engine_version": engine.ENGINE_VERSION,
        "basis_draw_count": int(basis_draw_count),
        "basis_last_draw": basis_last_draw,
        "tested_draws": tested,
        "replay_draws": int(acc.get("replay_draws", 0)),
        "live_draws": int(acc.get("live_draws", 0)),
        "replay_window_draws": int(replay_window),
        "twin_count": int(acc.get("twins", 0)),
        "twin_rate_pct": round((acc.get("twins", 0) / tested) * 100.0, 2) if tested else 0.0,
        "ai_stats": ai_stats,
        "bbfs_stats": bbfs_stats,
        "paito_stats": paito_stats,
        "trimmer_stats": dict(acc["trimmer"]),
        "sniper_stats": sniper_metric,
        "prospective": prospective,
        "accumulators": acc,
    }


def evaluation_integrity_errors(state: Dict, allow_legacy_empty_live: bool = False) -> List[str]:
    """Validate counters and their published projection before trusting live evidence."""
    if not isinstance(state, dict) or not isinstance(state.get("accumulators"), dict):
        return ["evaluation.accumulators.missing"]
    errors = []
    acc = state["accumulators"]

    def validate_bucket(bucket, path, isolated=False):
        if not isinstance(bucket, dict):
            errors.append(path)
            return
        template = _new_accumulator(False)
        if set(bucket) - (set(template) | (set() if isolated else {"live_only"})):
            errors.append(f"{path}.schema")
        def shape(value, expected, key):
            if isinstance(expected, dict):
                if not isinstance(value, dict):
                    errors.append(key)
                    return
                if set(value) != set(expected):
                    errors.append(f"{key}.schema")
                for child, prototype in expected.items():
                    shape(value.get(child), prototype, f"{key}.{child}")
            elif not finite_number(value) or value < 0 or (isinstance(expected, int) and not count(value)):
                errors.append(key)
        before = len(errors)
        shape({k: v for k, v in bucket.items() if k != "live_only"}, template, path)
        if len(errors) != before:
            return
        n = bucket["tested"]
        if bucket["twins"] > n or (not isolated and n != bucket["replay_draws"] + bucket["live_draws"]):
            errors.append(f"{path}.counts")
        if isolated and (bucket["replay_draws"] != 0 or bucket["live_draws"] != 0 or "live_only" in bucket):
            errors.append(f"{path}.isolation")
        for family in ("ai", "bbfs", "paito"):
            for key, row in bucket[family].items():
                if not isinstance(row, dict) or not count(row.get("hits")) or row["hits"] > n:
                    errors.append(f"{path}.{family}.{key}.hits")
                if family == "bbfs" and isinstance(row, dict) and count(row.get("hits")) and row["hits"] > n - bucket["twins"]:
                    errors.append(f"{path}.{family}.{key}.twin")
                if family == "paito" and (row.get("baseline_sum", 0) > n + 1e-8 or row.get("brier_sum", 0) > 2 * n + 1e-8):
                    errors.append(f"{path}.{family}.{key}.sums")
        if sum(bucket["trimmer"].values()) != n:
            errors.append(f"{path}.trimmer.total")
        sniper = bucket["sniper"]
        if not (sniper["super_hits"] <= sniper["top_hits"] <= sniper["any_hits"] <= sniper["active_draws"] <= n
                and sniper["top_hits"] + sniper["secondary_hits"] == sniper["any_hits"]
                and sniper["baseline_sum"] <= sniper["active_draws"] + 1e-8):
            errors.append(f"{path}.sniper.counts")

    validate_bucket(acc, "evaluation.accumulators")
    live = acc.get("live_only")
    legacy_empty = allow_legacy_empty_live and live is None and acc.get("live_draws") == 0 and "prospective" not in state
    if not legacy_empty:
        validate_bucket(live, "evaluation.prospective", True)
        if isinstance(live, dict) and live.get("tested") != acc.get("live_draws"):
            errors.append("evaluation.prospective.live_count")
    if not count(state.get("basis_draw_count")) or not count(state.get("replay_window_draws")):
        errors.append("evaluation.basis_count")
    if not count(state.get("unscored_draws", 0)):
        errors.append("evaluation.unscored_draws")
    if count(acc.get('tested')) and count(state.get('basis_draw_count')) and acc['tested'] > state['basis_draw_count']:
        errors.append('evaluation.tested_exceeds_basis')
    last = state.get("basis_last_draw")
    if not isinstance(last, str) or len(last) != 4 or not last.isascii() or not last.isdigit():
        errors.append("evaluation.basis_last_draw")
    if errors:
        return errors
    if live:
        def subset(child, parent):
            for key, value in child.items():
                if key in ("tested", "replay_draws", "live_draws"):
                    continue
                if isinstance(value, dict):
                    subset(value, parent[key])
                elif value > parent[key] + 1e-8:
                    errors.append("evaluation.prospective.subset")
        subset(live, acc)
    expected = _build_output(acc, state["basis_draw_count"], last, state["replay_window_draws"])
    for key in ("tested_draws", "replay_draws", "live_draws", "twin_count", "twin_rate_pct", "ai_stats", "bbfs_stats", "paito_stats", "trimmer_stats", "sniper_stats", "prospective"):
        if key == "prospective" and legacy_empty:
            continue
        if state.get(key) != expected[key]:
            errors.append(f"evaluation.{key}.projection")
    return sorted(set(errors))


def state_matches_history(state: Dict, history: Iterable[str]) -> bool:
    valid = _valid_results(history)
    if not valid or not isinstance(state, dict):
        return False
    return (
        state.get("evaluator_version") == EVALUATOR_VERSION
        and state.get("engine_version") == engine.ENGINE_VERSION
        and count(state.get("basis_draw_count"))
        and state["basis_draw_count"] == len(valid)
        and state.get("basis_last_draw") == valid[-1]
        and not evaluation_integrity_errors(state, allow_legacy_empty_live=True)
    )


def run_production_evaluation(
    results_4d: Iterable[str], warmup: int = DEFAULT_WARMUP, max_draws: int = DEFAULT_MAX_DRAWS
) -> Dict:
    valid_all = _valid_results(results_4d)
    if len(valid_all) < max(15, warmup + 1):
        return {}
    sample = valid_all[-max_draws:] if max_draws and len(valid_all) > max_draws else valid_all[:]
    warmup = max(15, min(warmup, len(sample) - 1))
    seeded = engine.audit_and_tune(sample[:warmup], None)
    prediction = seeded.get("next_prediction") if isinstance(seeded, dict) else None
    if not isinstance(prediction, dict):
        return {}

    acc = _new_accumulator()
    for idx in range(warmup, len(sample)):
        actual = sample[idx]
        _accumulate(acc, prediction, actual, "replay")
        tuned = engine.audit_and_tune(sample[: idx + 1], prediction)
        next_prediction = tuned.get("next_prediction") if isinstance(tuned, dict) else None
        if not isinstance(next_prediction, dict):
            break
        prediction = next_prediction

    return _build_output(acc, len(valid_all), valid_all[-1], len(sample))


def update_production_evaluation(
    previous_state: Dict,
    saved_prediction: Dict,
    actual_result: str,
    basis_draw_count: int,
    basis_last_draw: str,
) -> Dict:
    if (
        not isinstance(previous_state, dict)
        or previous_state.get("evaluator_version") != EVALUATOR_VERSION
        or previous_state.get("engine_version") != engine.ENGINE_VERSION
        or evaluation_integrity_errors(previous_state, allow_legacy_empty_live=True)
        or not prediction_matches_basis(saved_prediction, engine.ENGINE_VERSION,
                                        previous_state.get("basis_draw_count"), previous_state.get("basis_last_draw"))
        or not count(basis_draw_count)
        or basis_draw_count != previous_state["basis_draw_count"] + 1
        or not isinstance(actual_result, str)
        or len(actual_result) != 4 or not actual_result.isascii() or not actual_result.isdigit()
        or basis_last_draw != actual_result
    ):
        return {}
    acc = copy.deepcopy(previous_state["accumulators"])
    _accumulate(acc, saved_prediction, actual_result, "live")
    result = _build_output(
        acc,
        basis_draw_count,
        basis_last_draw,
        int(previous_state.get("replay_window_draws", 0)),
    )
    result["unscored_draws"] = previous_state.get("unscored_draws", 0)
    return result


def advance_without_observation(previous_state, history):
    """Keep existing replay/live evidence across missed draws; never fabricate live bets."""
    if evaluation_integrity_errors(previous_state):
        return {}
    skipped = len(history) - previous_state["basis_draw_count"]
    if skipped <= 0:
        return {}
    result = _build_output(copy.deepcopy(previous_state["accumulators"]), len(history), history[-1], previous_state["replay_window_draws"])
    result["unscored_draws"] = previous_state.get("unscored_draws", 0) + skipped
    return result


def upgrade_empty_live_state(state):
    """Only zero-live legacy states can gain an empty holdout without inventing evidence."""
    if (not isinstance(state, dict) or state.get('live_draws') != 0
            or state.get('engine_version') != engine.ENGINE_VERSION
            or state.get('evaluator_version') != EVALUATOR_VERSION
            or not isinstance(state.get('accumulators'), dict)
            or 'live_only' in state['accumulators'] or 'prospective' in state
            or evaluation_integrity_errors(state, allow_legacy_empty_live=True)):
        return state
    acc = copy.deepcopy(state['accumulators'])
    acc['live_only'] = _new_accumulator(False)
    return {**state, **_build_output(acc, state['basis_draw_count'], state['basis_last_draw'], state['replay_window_draws'])}
