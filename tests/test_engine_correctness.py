import unittest

import engine
import scraper


class EngineCorrectnessTests(unittest.TestCase):
    def test_markov_abstains_without_transition(self):
        scores = engine.get_markov_scores([(0, 1), (2, 3)])
        self.assertTrue(all(v == 0 for v in scores.values()))

    def test_smart_trim_bucket_sizes(self):
        trim = engine.generate_smart_trim([0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(len(trim["top10"]), 10)
        self.assertEqual(len(trim["medium15"]), 15)
        self.assertEqual(len(trim["full42"]), 42)
        self.assertEqual(len(trim["cadangan"]), 17)
        self.assertFalse(set(trim["top10"]) & set(trim["medium15"]))

    def test_paito_probabilities_are_normalized(self):
        history = [(i % 10, (i * 3) % 10) for i in range(60)]
        p = engine.predict_paito_macro(history)
        self.assertAlmostEqual(sum(p["biji_probabilities"].values()), 1.0, places=9)
        self.assertAlmostEqual(sum(p["parity_probabilities"].values()), 1.0, places=9)
        self.assertAlmostEqual(sum(p["magnitude_probabilities"].values()), 1.0, places=9)
        self.assertAlmostEqual(sum(p["shio_probabilities"].values()), 1.0, places=9)
        self.assertAlmostEqual(sum(p["jalur_probabilities"].values()), 1.0, places=9)
        self.assertEqual(len(p["top_biji"]), 3)
        self.assertEqual(len(set(p["top_biji"])), 3)

    def test_twin_is_loss_for_non_twin_bbfs(self):
        history = [f"{(i * 137) % 10000:04d}" for i in range(20)]
        history[-1] = "8844"
        saved = {
            "ai3": [1, 2, 3], "ai4": [1, 2, 3, 4],
            "ai5": [1, 2, 3, 4, 5], "ai6": [0, 1, 2, 3, 4, 5],
            "bbfs6": [0, 1, 2, 3, 4, 5],
            "bbfs7": [0, 1, 2, 3, 4, 5, 6],
            "bbfs8": [0, 1, 2, 3, 4, 5, 6, 7],
            "bbfs9": [0, 1, 2, 3, 4, 5, 6, 7, 8],
        }
        audit = engine.audit_and_tune(history, saved)
        self.assertTrue(audit["is_twin"])
        self.assertEqual(audit["status_bbfs"], "LOSE")
        for size in (6, 7, 8, 9):
            self.assertEqual(audit["bbfs_tuning"]["tier_audits"][f"bbfs{size}"]["action"], "CALIBRATED")

    def test_duplicate_safe_history_alignment(self):
        existing = ["1111", "2222", "1234", "5678", "1234"]
        scraped = ["1234", "5678", "1234", "9999"]
        merged, _ = scraper.merge_histories_with_days(existing, [], scraped, [])
        self.assertEqual(merged, ["1111", "2222", "1234", "5678", "1234", "9999"])

    def test_consecutive_duplicate_draw_is_preserved(self):
        existing = ["1111", "2222", "1234", "1234"]
        scraped = ["2222", "1234", "1234", "9999"]
        merged, _ = scraper.merge_histories_with_days(existing, [], scraped, [])
        self.assertEqual(merged, ["1111", "2222", "1234", "1234", "9999"])


if __name__ == "__main__":
    unittest.main()
