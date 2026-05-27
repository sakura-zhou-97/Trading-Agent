import unittest

from tradingagents.market.schemas import MarketEnvironment
from tradingagents.opportunity.schemas import OpportunityScore
from tradingagents.planning.schemas import TradePlan
from tradingagents.reporting import build_daily_report, render_daily_report_md
from tradingagents.sector.schemas import SectorScore


class DailyReportTests(unittest.TestCase):
    def test_daily_report_summarizes_market_opportunities_and_plans(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_score=68.0,
            market_state="normal",
            allowed_action="normal",
            data_gaps=["index_trend_missing"],
        )
        opportunity = OpportunityScore(
            trade_date="2026-05-12",
            symbol="000001",
            name="Example",
            sector="Metals",
            total_score=82.0,
            grade="A",
            status="key_opportunity",
            rank_reason="sector and trend resonance",
        )
        plan = TradePlan(
            trade_date="2026-05-12",
            symbol="000001",
            name="Example",
            grade="A",
            plan_status="active",
            max_position_pct=0.07,
            entry_conditions=["放量突破前高或关键平台，且收盘不明显回落时再观察。"],
            stop_loss_conditions=["跌破 MA20"],
            invalidation_conditions=["市场转防守"],
        )

        report = build_daily_report(
            trade_date="2026-05-12",
            market_environment=environment,
            sector_scores=[
                SectorScore(
                    sector="Metals",
                    sector_score=80.0,
                    sector_state="mainline",
                    sector_rank=1,
                    sector_count=3,
                )
            ],
            candidates=[{"symbol": "000001"}],
            opportunities=[opportunity],
            trade_plans=[plan],
        )

        self.assertEqual(report.summary.candidate_count, 1)
        self.assertEqual(report.summary.key_opportunity_count, 1)
        self.assertEqual(report.summary.trade_plan_count, 1)
        self.assertEqual(report.tomorrow_watchlist[0].symbol, "000001")
        self.assertIn("index_trend_missing", report.data_gaps)

    def test_defensive_report_marks_blocked_positions(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_score=30.0,
            market_state="defensive",
            allowed_action="no_new_position",
        )
        opportunity = OpportunityScore(
            trade_date="2026-05-12",
            symbol="000001",
            total_score=88.0,
            grade="S",
            status="key_opportunity",
        )
        plan = TradePlan(
            trade_date="2026-05-12",
            symbol="000001",
            grade="S",
            plan_status="blocked",
            max_position_pct=0.0,
        )

        report = build_daily_report(
            trade_date="2026-05-12",
            market_environment=environment,
            sector_scores=[],
            candidates=[{"symbol": "000001"}],
            opportunities=[opportunity],
            trade_plans=[plan],
        )

        self.assertTrue(report.has_blocked_new_positions())
        self.assertEqual(report.summary.trade_plan_count, 1)
        self.assertEqual(report.summary.blocked_plan_count, 1)
        self.assertIn("Defensive market", report.summary.main_risk)

    def test_markdown_renders_human_decision_sections(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_state="normal",
            allowed_action="normal",
        )
        report = build_daily_report(
            trade_date="2026-05-12",
            market_environment=environment,
            sector_scores=[],
            candidates=[],
            opportunities=[],
            trade_plans=[],
        )

        markdown = render_daily_report_md(report)

        self.assertIn("今日市场状态", markdown)
        self.assertIn("板块语境排名", markdown)
        self.assertIn("明日观察清单", markdown)
        self.assertIn("复盘钩子", markdown)


if __name__ == "__main__":
    unittest.main()
