import unittest

from tradingagents.iteration import evaluate_forward_groups, generate_patch_suggestions


def _metric(symbol: str, grade: str, risk_bucket: str, f5: float, mdd: float, entry: str = "true") -> dict:
    return {
        "symbol": symbol,
        "opportunity_grade": grade,
        "strategy_type": "mainline_trend",
        "risk_bucket": risk_bucket,
        "sector_state": "mainline",
        "plan_status": "active",
        "scoring_profile": "v1_default",
        "entry_triggered": entry,
        "future_1d_return_pct": f5 / 2,
        "future_5d_return_pct": f5,
        "future_10d_return_pct": f5 + 1,
        "future_20d_return_pct": f5 + 2,
        "max_gain_pct": max(f5, 1.0),
        "max_drawdown_pct": mdd,
        "t1_return_pct": f5 / 2,
        "t2_return_pct": f5 / 1.5,
        "t3_return_pct": f5,
        "mdd_3d_pct": mdd,
        "should_remove": mdd <= -8,
    }


class ForwardValidationTests(unittest.TestCase):
    def test_evaluate_forward_groups_groups_by_grade_risk_plan_and_profile(self) -> None:
        metrics = [
            _metric("000001", "A", "low", 3.0, -2.0, "true"),
            _metric("000002", "A", "low", 1.0, -1.0, "false"),
            _metric("000003", "B", "high", -4.0, -8.0, "unknown"),
        ]

        groups = evaluate_forward_groups(metrics)

        self.assertIn("opportunity_grade", groups)
        grade_a = next(row for row in groups["opportunity_grade"] if row["group"] == "A")
        self.assertEqual(grade_a["count"], 2)
        self.assertEqual(grade_a["entry_trigger_rate"], 0.5)
        self.assertIn("risk_bucket", groups)
        self.assertIn("scoring_profile", groups)

    def test_patch_suggestions_include_weak_forward_group_evidence(self) -> None:
        metrics = [
            _metric("000001", "A", "high", -2.0, -7.0),
            _metric("000002", "A", "high", -3.0, -6.5),
            _metric("000003", "A", "high", -1.0, -6.2),
        ]

        payload = generate_patch_suggestions(metrics, min_valid_t3_samples=1)

        self.assertIn("forward_group_summary", payload)
        evidence_titles = [item["title"] for item in payload["rule_patch_suggestions"]]
        self.assertIn("按分组证据收紧弱势组合", evidence_titles)


if __name__ == "__main__":
    unittest.main()
