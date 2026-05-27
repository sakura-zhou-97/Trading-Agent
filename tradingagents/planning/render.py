"""Markdown rendering for conditional trade plans."""

from __future__ import annotations

from typing import List

from tradingagents.planning.schemas import TradePlan


def render_trade_plans_md(plans: List[TradePlan]) -> str:
    lines = ["# P. 交易计划", ""]
    if not plans:
        return "# P. 交易计划\n\n- 暂无 S/A 重点机会交易计划。\n"

    for plan in plans:
        lines.extend(
            [
                f"## {plan.symbol} {plan.name}",
                "",
                f"- 等级: {plan.grade}",
                f"- 策略: {plan.strategy_type}",
                f"- 状态: {plan.plan_status}",
                f"- 仓位上限: {round(plan.max_position_pct * 100, 2)}%",
                f"- 持有周期: {plan.holding_period}",
                "",
                "### 触发条件",
            ]
        )
        for condition in plan.entry_conditions:
            lines.append(f"- {condition}")
        lines.append("")
        lines.append("### 止损条件")
        for condition in plan.stop_loss_conditions:
            lines.append(f"- {condition}")
        lines.append("")
        lines.append("### 止盈/保护利润")
        for rule in plan.take_profit_rules:
            lines.append(f"- {rule}")
        lines.append("")
        lines.append("### 失效条件")
        for condition in plan.invalidation_conditions:
            lines.append(f"- {condition}")
        if plan.risk_notes:
            lines.append("")
            lines.append("### 风险标记")
            for note in plan.risk_notes:
                lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)
