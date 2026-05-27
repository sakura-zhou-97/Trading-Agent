"""Markdown rendering for opportunity scoring artifacts."""

from __future__ import annotations

from typing import List

from tradingagents.opportunity.schemas import OpportunityScore


def render_opportunity_scores_md(opportunities: List[OpportunityScore]) -> str:
    lines = ["# O. 机会评分", ""]
    if not opportunities:
        return "# O. 机会评分\n\n- 暂无候选机会。\n"

    lines.append("| 排名 | 股票 | 板块 | 总分 | 等级 | 状态 | 风险扣分 | 排名原因 |")
    lines.append("|---:|---|---|---:|---|---|---:|---|")
    for idx, item in enumerate(opportunities, start=1):
        stock = f"{item.symbol} {item.name}".strip()
        lines.append(
            f"| {idx} | {stock} | {item.sector} | {item.total_score:.2f} | "
            f"{item.grade} | {item.status} | {item.risk_penalty:.2f} | {item.rank_reason} |"
        )

    lines.extend(["", "## 重点机会"])
    key_items = [item for item in opportunities if item.is_key_opportunity()]
    if not key_items:
        lines.append("- 暂无 S/A 重点机会。")
    for item in key_items:
        flags = ", ".join(item.risk_flags) if item.risk_flags else "none"
        gaps = ", ".join(item.data_gaps[:5]) if item.data_gaps else "none"
        lines.append(
            f"- {item.symbol} {item.name}: grade={item.grade}, score={item.total_score:.2f}, "
            f"sector={item.sector}, risk_flags={flags}, data_gaps={gaps}"
        )

    lines.append("")
    return "\n".join(lines)
