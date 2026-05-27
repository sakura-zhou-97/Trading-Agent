import unittest

from pydantic import ValidationError

from tradingagents.market.schemas import MarketEnvironment
from tradingagents.opportunity.schemas import OpportunityScore
from tradingagents.planning.schemas import TradePlan
from tradingagents.reporting.schemas import DailyReport, DailyReportSummary
from tradingagents.sector.schemas import SectorScore


class P0SchemaTests(unittest.TestCase):
    def test_defensive_market_blocks_new_positions(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_score=32.5,
            market_state="defensive",
            allowed_action="no_new_position",
            reasons=["Market breadth weakened."],
        )

        self.assertTrue(environment.blocks_new_positions())

    def test_non_defensive_market_allows_new_positions(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_score=65.0,
            market_state="normal",
            allowed_action="normal",
        )

        self.assertFalse(environment.blocks_new_positions())

    def test_trade_plan_allows_only_active_positioned_plans(self) -> None:
        active_plan = TradePlan(
            trade_date="2026-05-12",
            symbol="000001",
            grade="A",
            plan_status="active",
            entry_conditions=["Break above pivot with volume confirmation."],
            stop_loss_conditions=["Close below support."],
            max_position_pct=0.1,
        )
        watch_plan = TradePlan(
            trade_date="2026-05-12",
            symbol="000002",
            grade="B",
            plan_status="watch",
            max_position_pct=0.0,
        )

        self.assertTrue(active_plan.allows_new_position())
        self.assertFalse(watch_plan.allows_new_position())

    def test_daily_report_delegates_market_blocking_rule(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_state="defensive",
            allowed_action="no_new_position",
        )
        report = DailyReport(
            trade_date="2026-05-12",
            summary=DailyReportSummary(
                market_state="defensive",
                market_score=None,
                candidate_count=0,
                key_opportunity_count=0,
                trade_plan_count=0,
                blocked_plan_count=1,
                main_risk="Defensive market blocks new positions.",
            ),
            market_environment=environment,
        )

        self.assertTrue(report.has_blocked_new_positions())
        self.assertEqual(report.formats, ["json", "markdown"])

    def test_opportunity_key_flag_requires_grade_and_status(self) -> None:
        key_opportunity = OpportunityScore(
            trade_date="2026-05-12",
            symbol="000001",
            total_score=88.0,
            grade="A",
            status="key_opportunity",
        )
        lower_grade = OpportunityScore(
            trade_date="2026-05-12",
            symbol="000002",
            total_score=72.0,
            grade="B",
            status="key_opportunity",
        )

        self.assertTrue(key_opportunity.is_key_opportunity())
        self.assertFalse(lower_grade.is_key_opportunity())

    def test_sector_score_defaults_to_industry_adapter(self) -> None:
        score = SectorScore(
            sector="Semiconductor",
            sector_score=82.0,
            sector_state="mainline",
            sector_rank=1,
            sector_count=35,
        )

        self.assertEqual(score.sector_adapter, "industry")

    def test_scores_validate_zero_to_one_hundred_range(self) -> None:
        with self.assertRaises(ValidationError):
            MarketEnvironment(
                trade_date="2026-05-12",
                market_score=101.0,
            )


if __name__ == "__main__":
    unittest.main()
