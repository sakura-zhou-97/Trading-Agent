import unittest

from tradingagents.market.schemas import MarketEnvironment
from tradingagents.opportunity import score_opportunities


def _candidate(**overrides) -> dict:
    item = {
        "symbol": "000001",
        "name": "Example",
        "industry": "Metals",
        "sector": "Metals",
        "sector_adapter": "industry",
        "sector_score": 84.0,
        "sector_state": "mainline",
        "sector_rank": 1,
        "sector_count": 3,
        "sector_score_data_gaps": ["index_relative_strength_baseline_missing"],
        "change_pct": 8.2,
        "recent_3d_change": 9.0,
        "last_close": 12.0,
        "ma5": 11.0,
        "ma10": 10.0,
        "ma20": 9.0,
        "high": 12.02,
        "vol_ratio": 1.6,
        "coarse_reason_tags": ["trend_aligned", "volume_expansion", "breakout", "concept_present"],
    }
    item.update(overrides)
    return item


def _decision_card(**overrides) -> dict:
    card = {
        "symbol": "000001",
        "name": "Example",
        "stage": "启动",
        "conclusion_type": "趋势",
        "evidence_chain": ["板块强", "趋势转强", "量能确认"],
        "tradability": "条件满足后可观察",
        "sustainability": "取决于板块量能维持",
        "expectation_gap": "新增催化可打开空间",
        "structure_position": "MA alignment",
        "max_risk": "跌破 MA10 后结构转弱",
        "reversal_trigger": "放量突破前高且不破 MA5",
        "info_gaps": [],
    }
    card.update(overrides)
    return card


class OpportunityScoringTests(unittest.TestCase):
    def test_scores_key_opportunity_from_market_sector_stock_and_ai_inputs(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_score=78.0,
            market_state="attack",
            allowed_action="normal",
        )

        scores = score_opportunities(
            trade_date="2026-05-12",
            market_environment=environment,
            candidates=[_candidate()],
            decision_cards=[_decision_card()],
            story_by_symbol={
                "000001": {
                    "story_payload": {
                        "story_heat_level": "high",
                        "is_mainline_candidate": True,
                        "has_risk_alert": False,
                    }
                }
            },
            analysis_trace={"000001": {"mode": "ai", "error": ""}},
        )

        self.assertEqual(len(scores), 1)
        self.assertIn(scores[0].grade, {"S", "A"})
        self.assertEqual(scores[0].status, "key_opportunity")
        self.assertEqual(scores[0].scoring_profile, "v1_default")
        self.assertGreater(scores[0].sector_score_component, 0)
        self.assertGreater(scores[0].entry_quality_component, 0)

    def test_enable_ai_false_fallback_still_scores_with_data_gap(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_score=62.0,
            market_state="normal",
            allowed_action="normal",
        )

        scores = score_opportunities(
            trade_date="2026-05-12",
            market_environment=environment,
            candidates=[_candidate()],
            decision_cards=[_decision_card()],
            analysis_trace={"000001": {"mode": "fallback", "error": ""}},
        )

        self.assertEqual(len(scores), 1)
        self.assertIn(scores[0].grade, {"A", "B", "C"})
        self.assertIn("ai_analysis_fallback", scores[0].data_gaps)

    def test_high_risk_and_weak_sector_are_penalized(self) -> None:
        environment = MarketEnvironment(
            trade_date="2026-05-12",
            market_score=50.0,
            market_state="cautious",
            allowed_action="light",
        )

        scores = score_opportunities(
            trade_date="2026-05-12",
            market_environment=environment,
            candidates=[_candidate(sector_score=52.0, sector_state="weak", change_pct=9.8)],
            decision_cards=[
                _decision_card(
                    max_risk="风险较高，可能冲高回落并兑现",
                    info_gaps=["缺少资金流", "缺少公告验证"],
                )
            ],
            story_by_symbol={"000001": {"story_payload": {"has_risk_alert": True}}},
            analysis_trace={"000001": {"mode": "ai", "error": ""}},
        )

        self.assertGreaterEqual(scores[0].risk_penalty, 10.0)
        self.assertIn("weak_sector_context", scores[0].risk_flags)
        self.assertLess(scores[0].total_score, 75.0)


if __name__ == "__main__":
    unittest.main()
