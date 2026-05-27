import unittest

from tradingagents.pipelines.stock_analysis_steps import build_sector_context_by_symbol, build_theme_heatmap


class StockAnalysisStepsTests(unittest.TestCase):
    def test_build_sector_context_by_symbol_exposes_new_sector_score_fields(self) -> None:
        rows = [
            {
                "symbol": "000001",
                "sector": "Metals",
                "sector_score": 82.0,
                "sector_state": "mainline",
                "sector_rank": 1,
                "sector_count": 3,
            }
        ]

        context = build_sector_context_by_symbol(rows)

        self.assertEqual(context["000001"]["sector_score"], 82.0)
        self.assertEqual(context["000001"]["sector_state"], "mainline")
        self.assertEqual(context["000001"]["sector_adapter"], "industry")

    def test_build_theme_heatmap_counts_sectors_and_story_tags(self) -> None:
        heatmap = build_theme_heatmap(
            top_candidates=[
                {"symbol": "000001", "industry": "Metals", "change_pct": 8.0},
                {"symbol": "000002", "industry": "Metals", "change_pct": 6.0},
                {"symbol": "000003", "industry": "Power", "change_pct": 5.0},
            ],
            decision_cards=[
                {
                    "tradability": "主线题材",
                    "sustainability": "突破后延续",
                    "expectation_gap": "风险可控",
                    "evidence_chain": ["催化扩散"],
                }
            ],
        )

        self.assertEqual(heatmap["top_sectors"][0]["sector"], "Metals")
        self.assertEqual(heatmap["story_tag_stats"]["theme_hot"], 1)
        self.assertEqual(heatmap["story_tag_stats"]["risk_alert"], 1)


if __name__ == "__main__":
    unittest.main()
