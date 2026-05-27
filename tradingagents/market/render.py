"""Markdown rendering for market environment artifacts."""

from __future__ import annotations

from tradingagents.market.schemas import MarketEnvironment


def render_market_environment_md(environment: MarketEnvironment) -> str:
    lines = [
        "# M. 市场环境",
        "",
        f"- 交易日: {environment.trade_date}",
        f"- 市场状态: {environment.market_state}",
        f"- 市场分: {environment.market_score if environment.market_score is not None else 'unknown'}",
        f"- 系统动作: {environment.allowed_action}",
        "",
        "## 分项",
    ]

    for component in environment.components:
        score = component.score if component.score is not None else "unknown"
        lines.append(
            f"- {component.name}: score={score}, weight={component.weight}, "
            f"status={component.status}, reason={component.reason}"
        )

    lines.extend(["", "## 结论依据"])
    if environment.reasons:
        for reason in environment.reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("- 暂无。")

    lines.extend(["", "## 数据缺口"])
    if environment.data_gaps:
        for gap in environment.data_gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("- 无。")

    lines.append("")
    return "\n".join(lines)
