import unittest

from tradingagents.market import build_market_environment


def _record(symbol: str, change_pct: float) -> dict:
    return {
        "symbol": symbol,
        "name": f"Stock {symbol}",
        "change_pct": change_pct,
        "amount": 100000.0,
    }


class MarketEnvironmentBuilderTests(unittest.TestCase):
    def test_empty_strong_universe_is_defensive(self) -> None:
        environment = build_market_environment(
            trade_date="2026-05-12",
            universe=[],
            candidates=[],
        )

        self.assertEqual(environment.market_state, "defensive")
        self.assertEqual(environment.allowed_action, "no_new_position")
        self.assertTrue(environment.blocks_new_positions())

    def test_strong_universe_can_be_attack_with_fallback_gaps(self) -> None:
        universe = [_record(f"000{i:03d}", 9.8) for i in range(100)]
        candidates = universe[:60]

        environment = build_market_environment(
            trade_date="2026-05-12",
            universe=universe,
            candidates=candidates,
        )

        self.assertEqual(environment.market_state, "attack")
        self.assertEqual(environment.allowed_action, "normal")
        self.assertFalse(environment.blocks_new_positions())
        self.assertIn("index_trend_missing", environment.data_gaps)
        self.assertIn("full_market_breadth_missing", environment.data_gaps)

    def test_components_mark_missing_and_fallback_sources(self) -> None:
        environment = build_market_environment(
            trade_date="2026-05-12",
            universe=[_record("000001", 7.2)],
            candidates=[],
        )
        status_by_name = {component.name: component.status for component in environment.components}

        self.assertEqual(status_by_name["index_trend"], "missing")
        self.assertEqual(status_by_name["turnover"], "missing")
        self.assertEqual(status_by_name["breadth"], "fallback")
        self.assertEqual(status_by_name["limit_sentiment"], "fallback")
        self.assertEqual(status_by_name["risk_appetite"], "fallback")


if __name__ == "__main__":
    unittest.main()
