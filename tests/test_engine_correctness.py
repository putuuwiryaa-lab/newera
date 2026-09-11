import unittest
from unittest.mock import patch

import engine
import scraper


class _FakeSnapshot:
    def __init__(self, data):
        self.exists = True
        self._data = data

    def to_dict(self):
        return self._data


class _FakeDocument:
    def __init__(self, data=None):
        self._data = data or {}
        self.saved = None

    def get(self):
        return _FakeSnapshot(self._data)

    def set(self, payload, merge=False):
        self.saved = (payload, merge)


class _FakeCollection:
    def __init__(self, document):
        self._document = document
        self.added = []

    def document(self, _doc_id):
        return self._document

    def add(self, payload):
        self.added.append(payload)


class _FakeDB:
    def __init__(self, market_data):
        self.market_document = _FakeDocument(market_data)
        self.markets = _FakeCollection(self.market_document)
        self.tuning_logs = _FakeCollection(_FakeDocument())

    def collection(self, name):
        if name == 'markets':
            return self.markets
        if name == 'tuning_logs':
            return self.tuning_logs
        raise KeyError(name)


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

    def test_next_prediction_carries_engine_and_history_basis(self):
        history = [f"{(i * 173) % 10000:04d}" for i in range(20)]
        result = engine.audit_and_tune(history, None)
        state = result["next_prediction"]
        self.assertEqual(state["engine_version"], engine.ENGINE_VERSION)
        self.assertEqual(state["basis_draw_count"], len(history))
        self.assertEqual(state["basis_last_draw"], history[-1])
        self.assertTrue(scraper.prediction_state_matches_history(state, history))
        self.assertFalse(scraper.prediction_state_matches_history({**state, "engine_version": "legacy"}, history))
        self.assertFalse(scraper.prediction_state_matches_history({**state, "basis_draw_count": len(history) - 1}, history))

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

    def test_history_correction_rebuilds_forward_state_without_fake_audit(self):
        existing = [f"{i:04d}" for i in range(15)]
        corrected = existing.copy()
        corrected[7] = "7777"
        stale_prediction = {"ai4": [0, 1, 2, 3], "bbfs7": [0, 1, 2, 3, 4, 5, 6]}
        db = _FakeDB({
            "history_data": " ".join(existing),
            "history_days": " ".join(["Senin"] * len(existing)),
            "next_prediction": stale_prediction,
            "last_audit": {"status_ai": "HIT"},
        })
        rebuilt = {
            "engine_version": engine.ENGINE_VERSION,
            "basis_draw_count": len(corrected),
            "basis_last_draw": corrected[-1],
            "ai4": [4, 5, 6, 7],
            "bbfs7": [1, 2, 3, 4, 5, 6, 7],
        }

        with patch.object(
            scraper,
            "merge_histories_with_days",
            return_value=(corrected, ["Senin"] * len(corrected)),
        ), patch.object(
            scraper.engine,
            "audit_and_tune",
            return_value={"next_prediction": rebuilt},
        ) as tune:
            ok = scraper.sync_market_data(
                db,
                "TEST",
                " ".join(corrected),
                1,
                " ".join(["Senin"] * len(corrected)),
            )

        self.assertTrue(ok)
        tune.assert_called_once_with(corrected, None)
        self.assertEqual(db.tuning_logs.added, [])
        payload, merge = db.market_document.saved
        self.assertTrue(merge)
        self.assertEqual(payload["next_prediction"], rebuilt)
        self.assertIs(payload["last_audit"], scraper.firestore.DELETE_FIELD)

    def test_legacy_state_migrates_without_fake_audit(self):
        history = [f"{i:04d}" for i in range(15)]
        legacy = {"ai4": [0, 1, 2, 3], "bbfs7": [0, 1, 2, 3, 4, 5, 6]}
        rebuilt = {
            "engine_version": engine.ENGINE_VERSION,
            "basis_draw_count": len(history),
            "basis_last_draw": history[-1],
            "ai4": [4, 5, 6, 7],
            "bbfs7": [1, 2, 3, 4, 5, 6, 7],
        }
        db = _FakeDB({
            "history_data": " ".join(history),
            "history_days": " ".join(["Senin"] * len(history)),
            "next_prediction": legacy,
            "last_audit": {"status_ai": "HIT"},
        })

        with patch.object(
            scraper,
            "merge_histories_with_days",
            return_value=(history, ["Senin"] * len(history)),
        ), patch.object(
            scraper.engine,
            "audit_and_tune",
            return_value={"next_prediction": rebuilt},
        ) as tune:
            ok = scraper.sync_market_data(
                db,
                "TEST",
                " ".join(history),
                1,
                " ".join(["Senin"] * len(history)),
            )

        self.assertTrue(ok)
        tune.assert_called_once_with(history, None)
        self.assertEqual(db.tuning_logs.added, [])
        payload, _ = db.market_document.saved
        self.assertEqual(payload["next_prediction"], rebuilt)
        self.assertIs(payload["last_audit"], scraper.firestore.DELETE_FIELD)

    def test_initial_import_is_warm_start_without_tuning_log(self):
        history = [f"{i:04d}" for i in range(15)]
        rebuilt = {
            "engine_version": engine.ENGINE_VERSION,
            "basis_draw_count": len(history),
            "basis_last_draw": history[-1],
            "ai4": [4, 5, 6, 7],
            "bbfs7": [1, 2, 3, 4, 5, 6, 7],
        }
        db = _FakeDB({})

        with patch.object(
            scraper.engine,
            "audit_and_tune",
            return_value={"next_prediction": rebuilt},
        ) as tune:
            ok = scraper.sync_market_data(
                db,
                "TEST",
                " ".join(history),
                1,
                " ".join(["Senin"] * len(history)),
            )

        self.assertTrue(ok)
        tune.assert_called_once_with(history, None)
        self.assertEqual(db.tuning_logs.added, [])
        payload, _ = db.market_document.saved
        self.assertEqual(payload["next_prediction"], rebuilt)
        self.assertIs(payload["last_audit"], scraper.firestore.DELETE_FIELD)


if __name__ == "__main__":
    unittest.main()
