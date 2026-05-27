"""Markdown rendering for the V1 daily report."""

from __future__ import annotations

from tradingagents.reporting.schemas import DailyReport


def render_daily_report_md(report: DailyReport) -> str:
    lines = [
        "# R. 每日报告",
        "",
        f"- 交易日: {report.trade_date}",
        f"- 市场状态: {report.summary.market_state}",
        f"- 市场分: {report.summary.market_score if report.summary.market_score is not None else 'unknown'}",
        f"- 候选股数量: {report.summary.candidate_count}",
        f"- S/A 重点机会: {report.summary.key_opportunity_count}",
        f"- 交易计划: {report.summary.trade_plan_count}",
        f"- Blocked 计划: {report.summary.blocked_plan_count}",
        f"- 主要风险: {report.summary.main_risk}",
        "",
        "## 今日市场状态",
        f"- 系统动作: {report.market_environment.allowed_action}",
    ]
    for reason in report.market_environment.reasons:
        lines.append(f"- {reason}")

    lines.extend(["", "## 板块语境排名"])
    if report.sector_rankings:
        lines.append("| 排名 | 板块 | 分数 | 状态 | 候选数 | 龙头 |")
        lines.append("|---:|---|---:|---|---:|---|")
        for sector in report.sector_rankings[:10]:
            score = sector.sector_score if sector.sector_score is not None else "unknown"
            lines.append(
                f"| {sector.sector_rank or ''} | {sector.sector} | {score} | "
                f"{sector.sector_state} | {sector.sector_count} | {sector.leader_symbol} |"
            )
    else:
        lines.append("- 暂无板块排名。")

    lines.extend(["", "## S/A 重点机会"])
    if report.key_opportunities:
        lines.append("| 股票 | 板块 | 分数 | 等级 | 风险扣分 |")
        lines.append("|---|---|---:|---|---:|")
        for item in report.key_opportunities:
            lines.append(
                f"| {item.symbol} {item.name} | {item.sector} | {item.total_score:.2f} | "
                f"{item.grade} | {item.risk_penalty:.2f} |"
            )
    else:
        lines.append("- 暂无 S/A 重点机会。")

    lines.extend(["", "## 交易计划"])
    if report.trade_plans:
        lines.append("| 股票 | 等级 | 状态 | 仓位上限 | 关键触发条件 |")
        lines.append("|---|---|---|---:|---|")
        for plan in report.trade_plans:
            first_entry = plan.entry_conditions[0] if plan.entry_conditions else ""
            lines.append(
                f"| {plan.symbol} {plan.name} | {plan.grade} | {plan.plan_status} | "
                f"{round(plan.max_position_pct * 100, 2)}% | {first_entry} |"
            )
    else:
        lines.append("- 暂无交易计划。")

    lines.extend(["", "## 明日观察清单"])
    if report.tomorrow_watchlist:
        for item in report.tomorrow_watchlist:
            lines.append(
                f"- {item.symbol} {item.name} | grade={item.grade} | "
                f"sector={item.sector} | plan_status={item.plan_status}"
            )
    else:
        lines.append("- 暂无明日重点观察。")

    lines.extend(["", "## 风险和数据缺口"])
    if report.risk_notices:
        for notice in report.risk_notices:
            symbols = f" symbols={','.join(notice.symbols)}" if notice.symbols else ""
            lines.append(f"- [{notice.level}] {notice.title}: {notice.detail}{symbols}")
    if report.data_gaps:
        lines.append("")
        lines.append("### 数据缺口")
        for gap in report.data_gaps[:20]:
            lines.append(f"- {gap}")
    elif not report.risk_notices:
        lines.append("- 暂无。")

    lines.extend(["", "## 复盘钩子"])
    lines.append("- 后续前向验证按 scoring_profile、grade、strategy_type、risk_penalty 和 sector_state 分组。")
    lines.append("- 本报告不代表交易执行记录；买点触发只能由后续日线数据验证。")
    lines.append("")
    return "\n".join(lines)
