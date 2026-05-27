import unittest

from tradingagents.sector import calibrate_with_sector, score_sector_context


def _candidate(
    symbol: str,
    industry: str,
    change_pct: float,
    recent_3d_change: float,
    amount: float = 100000.0,
) -> dict:
    return {
        "symbol": symbol,
        "name": f"Stock {symbol}",
        "industry": industry,
        "change_pct": change_pct,
        "recent_3d_change": recent_3d_change,
        "amount": amount,
    }


class SectorScoringTests(unittest.TestCase):
    def test_score_sector_context_ranks_stronger_sector_first(self) -> None:
        candidates = [
            _candidate("000001", "Metals", 9.8, 12.0, 500000.0),
            _candidate("000002", "Metals", 7.2, 9.0, 400000.0),
            _candidate("000003", "Utilities", 5.1, 2.0, 100000.0),
        ]

        scores = score_sector_context(candidates)

        self.assertEqual(scores[0].sector, "Metals")
        self.assertEqual(scores[0].sector_rank, 1)
        self.assertEqual(scores[0].sector_adapter, "industry")
        self.assertIn(scores[0].sector_state, {"mainline", "strong"})
        self.assertGreater(scores[0].sector_score or 0, scores[1].sector_score or 0)

    def test_calibration_preserves_legacy_fields_and_adds_sector_scores(self) -> None:
        candidates = [
            _candidate("000001", "Metals", 9.8, 12.0, 500000.0),
            _candidate("000002", "Utilities", 5.1, 2.0, 100000.0),
        ]

        result = calibrate_with_sector(analysis_list=candidates, all_candidates=candidates)
        row = result["calibrated_analysis_list"][0]

        self.assertIn("sector_stats", result)
        self.assertIn("sector_scores", result)
        self.assertIn("sector_multiplier", row)
        self.assertIn("calibration_reason", row)
        self.assertEqual(row["sector_adapter"], "industry")
        self.assertIsNotNone(row["sector_score"])
        self.assertIsNotNone(row["sector_rank"])
        self.assertGreaterEqual(row["sector_count"], 1)

    def test_unknown_sector_is_capped_conservatively(self) -> None:
        candidates = [
            _candidate("000001", "", 10.0, 15.0, 1000000.0),
            _candidate("000002", "", 9.8, 13.0, 900000.0),
        ]

        result = calibrate_with_sector(analysis_list=candidates, all_candidates=candidates)
        row = result["calibrated_analysis_list"][0]

        self.assertEqual(row["sector"], "unknown_sector")
        self.assertLessEqual(row["sector_score"], 55.0)
        self.assertEqual(row["sector_state"], "weak")
        self.assertIn("sector_adapter_field_missing", row["sector_score_data_gaps"])


if __name__ == "__main__":
    unittest.main()
