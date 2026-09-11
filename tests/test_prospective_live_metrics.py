import unittest

import engine
import production_evaluator as pe


def make_history(n=70):
    out = []
    value = 2468
    for i in range(n):
        value = (value * 61 + 733 + i * 29) % 10000
        out.append(f"{value:04d}")
    return out


class ProspectiveLiveMetricTests(unittest.TestCase):
    def test_backfill_starts_with_zero_prospective_draws(self):
        history = make_history(70)
        state = pe.run_production_evaluation(history, warmup=50, max_draws=70)
        self.assertEqual(state["live_draws"], 0)
        self.assertIn("prospective", state)
        self.assertEqual(state["prospective"]["tested_draws"], 0)
        self.assertFalse(state["prospective"]["ready"])
        self.assertEqual(state["prospective"]["minimum_draws"], 30)

    def test_incremental_live_draw_isolated_from_replay(self):
        history = make_history(70)
        state = pe.run_production_evaluation(history, warmup=50, max_draws=70)
        replay_before = state["replay_draws"]
        tested_before = state["tested_draws"]
        saved = engine.audit_and_tune(history, None)["next_prediction"]
        actual = "1357"
        updated = pe.update_production_evaluation(
            state, saved, actual, len(history) + 1, actual
        )
        self.assertEqual(updated["replay_draws"], replay_before)
        self.assertEqual(updated["live_draws"], 1)
        self.assertEqual(updated["tested_draws"], tested_before + 1)
        prospective = updated["prospective"]
        self.assertEqual(prospective["tested_draws"], 1)
        self.assertFalse(prospective["ready"])
        for tier in engine.AI_SIZES:
            self.assertEqual(prospective["ai_stats"][str(tier)]["tested"], 1)
        for tier in engine.BBFS_SIZES:
            self.assertEqual(prospective["bbfs_stats"][str(tier)]["tested"], 1)
        for domain in ["biji", "parity", "magnitude", "shio", "jalur"]:
            self.assertEqual(prospective["paito_stats"][domain]["tested"], 1)

    def test_legacy_accumulator_without_live_bucket_upgrades_on_first_live_draw(self):
        history = make_history(70)
        state = pe.run_production_evaluation(history, warmup=50, max_draws=70)
        state["accumulators"].pop("live_only", None)
        state.pop("prospective", None)
        saved = engine.audit_and_tune(history, None)["next_prediction"]
        actual = "8642"
        updated = pe.update_production_evaluation(
            state, saved, actual, len(history) + 1, actual
        )
        self.assertEqual(updated["prospective"]["tested_draws"], 1)
        self.assertIn("live_only", updated["accumulators"])


if __name__ == "__main__":
    unittest.main()
