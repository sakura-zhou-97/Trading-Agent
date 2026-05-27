import unittest

from tradingagents.market.schemas import MarketEnvironment
from tradingagents.opportunity.schemas import OpportunityScore
from tradingagents.planning import generate_trade_plans


def _opportunity(**overrides) -> OpportunityScore:
    data = {
        "trade_date": "2026-05-12",
        "symbol": "000001",
        "name": "Example",
        "sector": "Metals",
        "strategy_type": "mainline_trend",
        "total_score": 82.0,
        "grade": "A",
        "status": "key_opportunity",
        "risk_penalty": 4.0,
    }
    data.update(overrides)
    return OpportunityScore(**data)


def _candidate() -> dict:
    return {
        "symbol": "000001",
        "ma5": 11.0,
        "ma10": 10.0,
        "ma20": 9.0,
        "sector": "Metals",
    }


def _decision_card(**overrides) -> dict:
    data = {
        "symbol": "000001",
        "stage": "启动",
        "reversal_trigger": "放量突破前高且收盘不破 MA5",
        "max_risk": "冲高回落并跌破 MA10",
        "expectation_gap": "新增催化不及预期",
    }
    data.update(overrides)
    return data


class TradePlanTests(unittest.TestCase):
    def test_normal_market_key_opportunity_gets_active_conditional_plan(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_score=68.0,
            market_state="normal",
            allowed_action="normal",
        )

        plans = generate_trade_plans(
            trade_date="2026-05-12",
            market_environment=environment,
            opportunities=[_opportunity()],
            decision_cards=[_decision_card()],
            candidates=[_candidate()],
        )

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].plan_status, "active")
        self.assertGreater(plans[0].max_position_pct, 0)
        self.assertTrue(plans[0].entry_conditions)
        self.assertTrue(plans[0].stop_loss_conditions)
        self.assertTrue(plans[0].invalidation_conditions)
        self.assertTrue(plans[0].allows_new_position())

    def test_defensive_market_blocks_new_position_plans(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_score=30.0,
            market_state="defensive",
            allowed_action="no_new_position",
        )

        plans = generate_trade_plans(
            trade_date="2026-05-12",
            market_environment=environment,
            opportunities=[_opportunity(grade="S", total_score=88.0)],
            decision_cards=[_decision_card()],
            candidates=[_candidate()],
        )

        self.assertEqual(plans[0].plan_status, "blocked")
        self.assertEqual(plans[0].max_position_pct, 0.0)
        self.assertFalse(plans[0].allows_new_position())
        self.assertIn("defensive_market_blocks_new_positions", plans[0].risk_notes)

    def test_high_risk_penalty_blocks_or_caps_position(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_score=78.0,
            market_state="attack",
            allowed_action="normal",
        )

        plans = generate_trade_plans(
            trade_date="2026-05-12",
            market_environment=environment,
            opportunities=[_opportunity(grade="S", total_score=86.0, risk_penalty=13.0)],
            decision_cards=[_decision_card()],
            candidates=[_candidate()],
        )

        self.assertEqual(plans[0].plan_status, "blocked")
        self.assertEqual(plans[0].max_position_pct, 0.0)
        self.assertIn("high_risk_penalty_caps_position", plans[0].risk_notes)


if __name__ == "__main__":
    unittest.main()
