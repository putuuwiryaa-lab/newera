import copy
from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import patch

import engine
import production_evaluator as pe
from production_health import assess_market_health
from state_contract import prediction_integrity_errors
import scraper
from tests.test_engine_correctness import _FakeDB
from tests.test_production_evaluator import make_history

NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)


def healthy_market():
    history = make_history(70)
    state = pe.run_production_evaluation(history)
    saved = engine.audit_and_tune(history)['next_prediction']
    for actual in ['0011', '1234']:
        state = pe.update_production_evaluation(state, saved, actual, len(history) + 1, actual)
        history.append(actual)
        saved = engine.audit_and_tune(history, saved)['next_prediction']
    return {'id': 'FIXTURE', 'name': 'FIXTURE', 'order': 1, 'history_data': ' '.join(history),
            'next_prediction': saved, 'production_evaluation': state, 'last_checked_at': NOW.isoformat(), 'data_source': 'live'}


class ProductionHealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.market = healthy_market()

    def test_healthy_and_time_expiry(self):
        self.assertEqual(assess_market_health(self.market, NOW)['status'], 'HEALTHY')
        self.assertEqual(assess_market_health(self.market, NOW + timedelta(hours=27))['status'], 'STALE')

    def test_required_metadata_checks(self):
        cases = [('next_prediction', 'engine_version', 'old', 'DRIFT'),
                 ('production_evaluation', 'evaluator_version', pe.EVALUATOR_VERSION + '-unknown', 'DRIFT'),
                 ('next_prediction', 'basis_draw_count', 71, 'STALE'),
                 ('next_prediction', 'basis_last_draw', '9999', 'DRIFT'),
                 ('next_prediction', 'basis_draw_count', 'bad', 'ERROR')]
        for obj, key, value, expected in cases:
            with self.subTest(key=key):
                market = copy.deepcopy(self.market)
                market[obj][key] = value
                self.assertEqual(assess_market_health(market, NOW)['status'], expected)
        for key in ('next_prediction', 'production_evaluation'):
            market = copy.deepcopy(self.market)
            market.pop(key)
            self.assertEqual(assess_market_health(market, NOW)['status'], 'STALE')

    def test_malformed_prediction_is_error(self):
        for value in (None, {}, [1, 1, 1], [1, 2, float('nan')]):
            market = copy.deepcopy(self.market)
            market['next_prediction']['ai3'] = value
            self.assertTrue(prediction_integrity_errors(market['next_prediction']))
            self.assertEqual(assess_market_health(market, NOW)['status'], 'ERROR')

    def test_corrupt_prospective_and_projection_are_rejected(self):
        for mutate in (
            lambda s: s['accumulators']['live_only'].update(tested=90),
            lambda s: s['accumulators']['live_only']['ai']['3'].update(hits=-1),
            lambda s: s['accumulators']['live_only']['paito']['biji'].update(brier_sum=float('nan')),
            lambda s: s['prospective'].update(ready=True),
            lambda s: s['prospective']['ai_stats']['3'].update(lift_pp=99),
            lambda s: s['accumulators'].pop('live_only'),
            lambda s: s['accumulators'].update(live_draws=999),
            lambda s: s['accumulators']['paito'].update(biji={}),
            lambda s: s['accumulators'].update(live_only={}),
        ):
            market = copy.deepcopy(self.market)
            mutate(market['production_evaluation'])
            self.assertTrue(pe.evaluation_integrity_errors(market['production_evaluation']))
            self.assertEqual(assess_market_health(market, NOW)['status'], 'ERROR')

    def test_duplicate_or_stale_observation_cannot_increment(self):
        state = self.market['production_evaluation']
        pred = self.market['next_prediction']
        for n, actual, last, saved in (
            (72, '1234', '1234', pred), (74, '3456', '3456', pred),
            (73, 'bad', 'bad', pred), (73, '3456', '9999', pred),
            (73, '3456', '3456', {**pred, 'engine_version': 'old'}),
            (73, '3456', '3456', {**pred, 'basis_last_draw': '0000'}),
        ):
            self.assertEqual(pe.update_production_evaluation(state, saved, actual, n, last), {})
        self.assertEqual(state['live_draws'], 2)

    def test_repeated_numeric_result_is_a_new_draw_when_basis_advances(self):
        state = pe.update_production_evaluation(self.market['production_evaluation'], self.market['next_prediction'], '1234', 73, '1234')
        self.assertEqual(state['live_draws'], 3)
        self.assertEqual(pe.evaluation_integrity_errors(state), [])

    def test_scraper_batch_preserves_live_without_fake_logs(self):
        market = copy.deepcopy(self.market)
        history = market['history_data'].split() + ['2468', '1357']
        db = _FakeDB(market)
        self.assertTrue(scraper.sync_market_data(db, 'FIXTURE', ' '.join(history), 1))
        payload, _ = db.market_document.saved
        self.assertEqual(payload['production_evaluation']['accumulators'], market['production_evaluation']['accumulators'])
        self.assertEqual(payload['production_evaluation']['unscored_draws'], 2)
        self.assertEqual(payload['next_prediction']['basis_draw_count'], 74)
        self.assertEqual(db.tuning_logs.added, [])

    def test_scraper_correction_quarantines_and_retains_evidence(self):
        market = copy.deepcopy(self.market)
        history = market['history_data'].split()
        history[5] = '9999'
        db = _FakeDB(market)
        with patch.object(scraper, 'merge_histories_with_days', return_value=(history, ['Senin'] * len(history))):
            self.assertTrue(scraper.sync_market_data(db, 'FIXTURE', ' '.join(history), 1))
        payload, _ = db.market_document.saved
        self.assertEqual(payload['production_evaluation'], market['production_evaluation'])
        self.assertIn('evaluation_blocked_reason', payload)
        self.assertEqual(payload['production_health']['status'], 'DRIFT')
        self.assertEqual(db.tuning_logs.added, [])

    def test_corruption_is_not_silently_backfilled(self):
        market = copy.deepcopy(self.market)
        market['production_evaluation']['accumulators']['live_only']['tested'] = 500
        db = _FakeDB(market)
        with patch.object(pe, 'run_production_evaluation') as replay:
            self.assertTrue(scraper.sync_market_data(db, 'FIXTURE', market['history_data'], 1))
        replay.assert_not_called()
        payload, _ = db.market_document.saved
        self.assertEqual(payload['production_evaluation'], market['production_evaluation'])
        self.assertEqual(payload['production_health']['status'], 'ERROR')

    def test_scrape_failure_is_visible_without_refreshing_check_time(self):
        db = _FakeDB(self.market)
        scraper.record_health_failure(db, 'FIXTURE', 'Scrape failed')
        payload, _ = db.market_document.saved
        self.assertEqual(payload['production_health']['status'], 'ERROR')
        self.assertNotIn('last_checked_at', payload)

    def test_safe_legacy_migration_preserves_replay_and_does_not_claim_live(self):
        state = pe.run_production_evaluation(make_history(70))
        del state['accumulators']['live_only']
        del state['prospective']
        before = copy.deepcopy(state)
        upgraded = pe.upgrade_empty_live_state(state)
        self.assertEqual(state, before)
        for key in ('ai_stats', 'bbfs_stats', 'paito_stats', 'trimmer_stats', 'sniper_stats', 'tested_draws', 'replay_draws'):
            self.assertEqual(upgraded[key], before[key])
        self.assertEqual(upgraded['prospective']['tested_draws'], 0)
        self.assertEqual(pe.evaluation_integrity_errors(upgraded), [])
        state['engine_version'] = 'old'
        self.assertEqual(pe.upgrade_empty_live_state(state), state)

    def test_single_valid_draw_scores_once_and_scraper_retry_does_not_score_again(self):
        db = _FakeDB(copy.deepcopy(self.market))
        data = self.market['history_data'] + ' 4567'
        self.assertTrue(scraper.sync_market_data(db, 'FIXTURE', data, 1))
        payload, _ = db.market_document.saved
        self.assertEqual(payload['production_evaluation']['live_draws'], 3)
        self.assertEqual(len(db.tuning_logs.added), 1)
        saved = {**self.market, **payload}
        again = _FakeDB(saved)
        self.assertTrue(scraper.sync_market_data(again, 'FIXTURE', data, 1))
        updated, _ = again.market_document.saved
        self.assertEqual(updated['production_evaluation']['live_draws'], 3)
        self.assertEqual(again.tuning_logs.added, [])

    def test_stale_prediction_on_new_draw_cannot_create_live_evidence(self):
        market = copy.deepcopy(self.market)
        market['next_prediction']['engine_version'] = 'old'
        db = _FakeDB(market)
        self.assertTrue(scraper.sync_market_data(db, 'FIXTURE', market['history_data'] + ' 4567', 1))
        saved, _ = db.market_document.saved
        self.assertEqual(saved['production_evaluation']['live_draws'], 2)
        self.assertEqual(saved['production_evaluation']['unscored_draws'], 1)
        self.assertEqual(db.tuning_logs.added, [])


if __name__ == '__main__':
    unittest.main()
