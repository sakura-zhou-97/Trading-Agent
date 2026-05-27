import unittest

from tradingagents.pipelines.trace_builder import build_stock_analysis_trace_log


class _Coarse:
    candidates = [
        {
            "symbol": "000001",
            "name": "Example",
            "change_pct": 8.0,
            "coarse_reason_tags": ["trend_aligned"],
        }
    ]
    dropped = [{"symbol": "000002", "drop_reasons": ["change_pct_below_threshold"]}]


class PipelineTraceBuilderTests(unittest.TestCase):
    def test_trace_builder_records_new_mopr_steps_without_pipeline_writer_logic(self) -> None:
        trace = build_stock_analysis_trace_log(
            trade_date="2026-05-12",
            min_change_pct=5.0,
            max_universe=400,
            enable_ai=False,
            rulebook={"hard_filters": {"min_change_pct": 5.0}},
            prompt_path="prompt.md",
            universe=[{"symbol": "000001"}],
            coarse=_Coarse(),
            result_c={"sector_scores": [], "calibrated_analysis_list": _Coarse.candidates},
            result_story={"count": 1, "story_by_symbol": {"000001": {}}},
            result_b={"decision_cards": [{"symbol": "000001", "stage": "启动"}]},
            result_o={"scoring_profile": "v1_default", "count": 1, "opportunities": [{"symbol": "000001"}]},
            result_p={"count": 1, "plans": [{"symbol": "000001"}]},
            result_r={"summary": {"market_state": "normal"}, "source_artifacts": {"R": "R_daily_report.json"}},
        )

        self.assertIn("step_4_opportunity_scoring", trace)
        self.assertIn("step_5_trade_planning", trace)
        self.assertIn("step_6_daily_report", trace)
        self.assertEqual(
            trace["step_1_coarse_screen"]["output"]["dropped_reason_stats"]["change_pct_below_threshold"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
