import unittest

import scraper


class HistoryMergeConfidenceTests(unittest.TestCase):
    def test_single_historical_correction_is_accepted_with_strong_alignment(self):
        existing = [f"{i:04d}" for i in range(10)]
        scraped = existing.copy()
        scraped[5] = "7777"
        scraped.append("0010")

        merged, _ = scraper.merge_histories_with_days(existing, [], scraped, [])

        self.assertEqual(merged, scraped)

    def test_unrelated_longer_scrape_never_replaces_existing_history(self):
        existing = [f"{i:04d}" for i in range(10)]
        scraped = [f"{9000 + i:04d}" for i in range(15)]

        merged, _ = scraper.merge_histories_with_days(existing, [], scraped, [])

        self.assertEqual(merged, existing)

    def test_short_exact_overlap_does_not_beat_long_high_confidence_alignment(self):
        existing = [
            "1000", "1001", "1002",
            "2000", "2001", "2002", "2003", "2004", "2005",
            "1000", "1001", "1002",
        ]
        scraped = existing.copy()
        scraped[6] = "7777"
        scraped.append("3000")

        alignment = scraper._best_sequence_alignment(existing, scraped, min_overlap=3)
        self.assertIsNotNone(alignment)
        overlap, offset, mode = alignment
        self.assertEqual((overlap, offset, mode), (12, 0, "fuzzy"))

        merged, _ = scraper.merge_histories_with_days(existing, [], scraped, [])
        self.assertEqual(merged, scraped)


if __name__ == "__main__":
    unittest.main()
