import math
import unittest

import engine
import production_evaluator as pe


def make_history(n=80):
    # Deterministic non-random fixture with repeated states and enough transitions.
    out = []
    value = 1379
    for i in range(n):
        value = (value * 73 + 941 + i * 17) % 10000
        out.append(f"{value:04d}")
    return out


class ProductionEvaluatorTests(unittest.TestCase):
    def test_backfill_metadata_and_metrics_are_valid(self):
        history = make_history(70)
        state = pe.run_production_evaluation(history, warmup=50, max_draws=70)
        self.assertTrue(state)
        self.assertEqual(state["evaluator_version"], pe.EVALUATOR_VERSION)
        self.assertEqual(state["engine_version"], engine.ENGINE_VERSION)
        self.assertEqual(state["basis_draw_count"], len(history))
        self.assertEqual(state["basis_last_draw"], history[-1])
        self.assertEqual(state["tested_draws"], 20)
        self.assertEqual(state["replay_draws"], 20)
        self.assertEqual(state["live_draws"], 0)
        self.assertTrue(pe.state_matches_history(state, history))

        for family in (state["ai_stats"], state["bbfs_stats"]):
            for metric in family.values():
                self.assertGreaterEqual(metric["hit_rate_pct"], 0.0)
                self.assertLessEqual(metric["hit_rate_pct"], 100.0)
                self.assertGreaterEqual(metric["baseline_pct"], 0.0)
                self.assertLessEqual(metric["baseline_pct"], 100.0)
                lo, hi = metric["ci95_pct"]
                self.assertGreaterEqual(lo, 0.0)
                self.assertLessEqual(hi, 100.0)
                self.assertLessEqual(lo, hi)

        for metric in state["paito_stats"].values():
            self.assertTrue(math.isfinite(metric["brier_score"]))
            self.assertGreaterEqual(metric["brier_score"], 0.0)

    def test_incremental_update_adds_exactly_one_live_draw(self):
        history = make_history(70)
        state = pe.run_production_evaluation(history, warmup=50, max_draws=70)
        saved = engine.audit_and_tune(history, None)["next_prediction"]
        new_result = "2468"
        updated = pe.update_production_evaluation(
            state,
            saved,
            new_result,
            len(history) + 1,
            new_result,
        )
        self.assertEqual(updated["tested_draws"], state["tested_draws"] + 1)
        self.assertEqual(updated["replay_draws"], state["replay_draws"])
        self.assertEqual(updated["live_draws"], 1)
        self.assertEqual(updated["basis_draw_count"], len(history) + 1)
        self.assertEqual(updated["basis_last_draw"], new_result)
        self.assertTrue(pe.state_matches_history(updated, history + [new_result]))

    def test_twin_is_never_bbfs_non_twin_hit(self):
        history = make_history(55)
        paito = engine.predict_paito_macro([(int(x[2]), int(x[3])) for x in history])
        prediction = {
            "ai3": [1, 2, 3],
            "ai4": [1, 2, 3, 4],
            "ai5": [1, 2, 3, 4, 5],
            "ai6": [1, 2, 3, 4, 5, 6],
            "bbfs6": [0, 1, 2, 3, 4, 5],
            "bbfs7": [0, 1, 2, 3, 4, 5, 6],
            "bbfs8": [0, 1, 2, 3, 4, 5, 6, 7],
            "bbfs9": [0, 1, 2, 3, 4, 5, 6, 7, 8],
            "paito": paito,
        }
        acc = pe._new_accumulator()
        pe._accumulate(acc, prediction, "9911", "replay")
        self.assertEqual(acc["twins"], 1)
        for sz in engine.BBFS_SIZES:
            self.assertEqual(acc["bbfs"][str(sz)]["hits"], 0)

    def test_stale_evaluator_state_is_rejected(self):
        history = make_history(70)
        state = pe.run_production_evaluation(history, warmup=50, max_draws=70)
        stale = dict(state)
        stale["engine_version"] = "old-engine"
        self.assertFalse(pe.state_matches_history(stale, history))
        stale = dict(state)
        stale["basis_draw_count"] -= 1
        self.assertFalse(pe.state_matches_history(stale, history))


if __name__ == "__main__":
    unittest.main()
