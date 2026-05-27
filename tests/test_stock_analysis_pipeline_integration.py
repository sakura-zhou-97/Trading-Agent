import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tradingagents.pipelines.stock_analysis_pipeline import run_stock_analysis_pipeline


def _universe():
    return [
        {
            "symbol": "000001",
            "name": "Example A",
            "industry": "Metals",
            "change_pct": 8.2,
            "high": 12.0,
            "amount": 500000.0,
            "is_st": False,
        },
        {
            "symbol": "000002",
            "name": "Example B",
            "industry": "Metals",
            "change_pct": 6.5,
            "high": 10.0,
            "amount": 300000.0,
            "is_st": False,
        },
    ]


def _attach_struct_features(universe, trade_date, lookback_days):
    enriched = []
    for idx, item in enumerate(universe):
        enriched.append(
            {
                **item,
                "last_close": 11.8 - idx,
                "ma5": 11.0 - idx,
                "ma10": 10.0 - idx,
                "ma20": 9.0 - idx,
                "vol_ratio": 1.6,
                "recent_3d_change": 9.0 - idx,
                "trend_label": "uptrend",
            }
        )
    return enriched


def _story(candidates, trade_date):
    return {
        "trade_date": trade_date,
        "count": len(candidates),
        "mode": "simple",
        "story_by_symbol": {
            item["symbol"]: {
                "story_payload": {
                    "story_heat_level": "high",
                    "is_mainline_candidate": True,
                    "has_risk_alert": False,
                },
                "news_text": "",
            }
            for item in candidates
        },
    }


def _analysis(candidates, trade_date, config, max_selected, enable_ai, sector_context_by_symbol, story_by_symbol):
    cards = []
    five_line = {}
    trace = {}
    for item in candidates:
        symbol = item["symbol"]
        card = {
            "symbol": symbol,
            "name": item.get("name", ""),
            "stage": "启动",
            "conclusion_type": "趋势",
            "evidence_chain": ["板块强", "趋势转强", "量能确认"],
            "tradability": "条件满足后可观察",
            "sustainability": "板块延续则可观察",
            "expectation_gap": "新增催化可打开空间",
            "structure_position": "MA alignment",
            "max_risk": "跌破 MA10 后结构转弱",
            "reversal_trigger": "放量突破前高且收盘不破 MA5",
            "info_gaps": [],
        }
        cards.append(card)
        five_line[symbol] = "1) 结论: 趋势"
        trace[symbol] = {"mode": "fallback" if not enable_ai else "ai", "error": ""}
    return {
        "analysis_list": cards,
        "decision_cards": cards,
        "decision_card_5lines": five_line,
        "analysis_trace": trace,
        "info_gaps": [],
    }


class StockAnalysisPipelineIntegrationTests(unittest.TestCase):
    def test_pipeline_generates_mopr_daily_artifacts_with_mocked_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "results_dir": tmp,
                "market_type": "china_a",
                "stock_analysis": {
                    "rulebook_path": "",
                    "prompt_path": "",
                    "story_analysis_mode": "simple",
                },
            }
            with (
                patch("tradingagents.pipelines.stock_analysis_pipeline.get_daily_universe", return_value=_universe()),
                patch("tradingagents.pipelines.stock_analysis_pipeline.attach_struct_features", side_effect=_attach_struct_features),
                patch("tradingagents.pipelines.stock_analysis_pipeline.run_story_analysis", side_effect=_story),
                patch("tradingagents.pipelines.stock_analysis_pipeline.analyze_candidates", side_effect=_analysis),
            ):
                result = run_stock_analysis_pipeline(
                    config=config,
                    trade_date="2026-05-12",
                    top_n=30,
                    initial_n=10,
                    enable_ai=False,
                )

            output_dir = Path(result["output_dir"])
            for filename in [
                "M_market_environment.json",
                "O_opportunity_scores.json",
                "P_trade_plans.json",
                "R_daily_report.json",
                "R_daily_report.md",
                "Z_pipeline_trace_log.json",
            ]:
                self.assertTrue((output_dir / filename).exists(), filename)
            self.assertIn("R", result)
            self.assertGreaterEqual(result["O"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
