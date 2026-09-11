import unittest

import scraper


class HistoryDaysIntegrityTests(unittest.TestCase):
    def test_sejahtera_date_fallback_derives_real_indonesian_weekday(self):
        self.assertEqual(scraper._weekday_from_ddmmyyyy("11/09/2026"), "Jumat")
        self.assertEqual(scraper._weekday_from_ddmmyyyy("12/09/2026"), "Sabtu")
        self.assertEqual(scraper._weekday_from_ddmmyyyy("invalid"), "")

    def test_valid_scraped_days_replace_stale_days_on_overlap(self):
        draws = ["1111", "2222", "3333"]
        existing_days = ["Senin", "Selasa", "Rabu"]
        scraped_days = ["Kamis", "Jumat", "Sabtu"]

        merged, merged_days = scraper.merge_histories_with_days(
            draws,
            existing_days,
            draws,
            scraped_days,
        )

        self.assertEqual(merged, draws)
        self.assertEqual(merged_days, scraped_days)

    def test_missing_scraped_days_preserve_existing_days(self):
        draws = ["1111", "2222", "3333"]
        existing_days = ["Senin", "Selasa", "Rabu"]

        merged, merged_days = scraper.merge_histories_with_days(
            draws,
            existing_days,
            draws,
            [],
        )

        self.assertEqual(merged, draws)
        self.assertEqual(merged_days, existing_days)


if __name__ == "__main__":
    unittest.main()
