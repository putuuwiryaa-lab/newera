"""Read-only market health. Python remains the production authority."""

from datetime import datetime, timezone

import engine
import production_evaluator as pe
from state_contract import count, prediction_integrity_errors

HEALTH_VERSION = "2026.09.11-health-v1"
MAX_CHECK_AGE_SECONDS = 26 * 60 * 60  # scraper runs every 12 hours; allow two runs + grace
SEVERITY = {"HEALTHY": 0, "STALE": 1, "DRIFT": 2, "ERROR": 3}


def assess_market_health(market, now=None):
    now = now or datetime.now(timezone.utc)
    checks = []

    def add(code, status, detail):
        checks.append({"code": code, "status": status, "detail": detail})

    history = str(market.get("history_data", "")).split()
    valid = bool(history) and all(len(r) == 4 and r.isascii() and r.isdigit() for r in history)
    add("history", "HEALTHY" if valid else "ERROR", f"{len(history)} draws")
    for name, obj in (("prediction", market.get("next_prediction")), ("evaluation", market.get("production_evaluation"))):
        if not isinstance(obj, dict):
            add(f"{name}.persisted_state", "STALE", "State belum tersedia")
            continue
        add(f"{name}.engine_version", "HEALTHY" if obj.get("engine_version") == engine.ENGINE_VERSION else "DRIFT", str(obj.get("engine_version", "missing")))
        if name == "evaluation":
            add("evaluation.evaluator_version", "HEALTHY" if obj.get("evaluator_version") == pe.EVALUATOR_VERSION else "DRIFT", str(obj.get("evaluator_version", "missing")))
        n = obj.get("basis_draw_count")
        status = "ERROR" if not count(n) else "HEALTHY" if n == len(history) else "STALE" if n < len(history) else "DRIFT"
        add(f"{name}.basis_draw_count", status, f"{n}/{len(history)}")
        add(f"{name}.basis_last_draw", "HEALTHY" if valid and obj.get("basis_last_draw") == history[-1] else "STALE" if count(n) and n < len(history) else "DRIFT", str(obj.get("basis_last_draw", "missing")))
        errors = prediction_integrity_errors(obj) if name == "prediction" else pe.evaluation_integrity_errors(obj)
        legacy_empty = name == "evaluation" and bool(errors) and not pe.evaluation_integrity_errors(obj, allow_legacy_empty_live=True)
        integrity_status = "STALE" if legacy_empty else "ERROR" if errors else "HEALTHY"
        add(f"{name}.integrity", integrity_status, "Zero-live legacy state: empty holdout migration pending" if legacy_empty else ", ".join(errors) or "Valid")
        if name == "evaluation":
            add("prospective.accumulator_integrity", integrity_status, "Counter live-only dan proyeksi evaluator diperiksa")
    blocked = market.get("evaluation_blocked_reason")
    if blocked:
        add("evaluation.quarantine", "DRIFT", str(blocked))
    if market.get("health_error"):
        add("pipeline", "ERROR", str(market["health_error"]))
    checked = market.get("last_checked_at") or market.get("updated_at")
    try:
        stamp = datetime.fromisoformat(str(checked).replace("Z", "+00:00"))
        age = (now - stamp).total_seconds()
        status = "DRIFT" if age < -300 else "STALE" if age > MAX_CHECK_AGE_SECONDS else "HEALTHY"
    except (ValueError, TypeError):
        age, status = None, "STALE"
    add("pipeline.last_check", status, f"{age}s; max {MAX_CHECK_AGE_SECONDS}s")
    return {
        "health_version": HEALTH_VERSION,
        "status": max((c["status"] for c in checks), key=SEVERITY.get),
        "production_source": "python",
        "checked_at": now.isoformat(),
        "engine_version": engine.ENGINE_VERSION,
        "evaluator_version": pe.EVALUATOR_VERSION,
        "basis_draw_count": len(history),
        "basis_last_draw": history[-1] if history else "",
        "checks": checks,
    }
