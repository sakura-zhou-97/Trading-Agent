"""Build the V1 daily report data contract."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List

from tradingagents.market.schemas import MarketEnvironment
from tradingagents.opportunity.schemas import OpportunityScore
from tradingagents.planning.schemas import TradePlan
from tradingagents.reporting.schemas import (
    DailyReport,
    DailyReportSummary,
    RiskNotice,
    WatchListItem,
)
from tradingagents.sector.schemas import SectorScore


def _as_sector_score(item: SectorScore | Dict) -> SectorScore:
    if isinstance(item, SectorScore):
        return item
    return SectorScore(**item)


def _main_risk(
    market_environment: MarketEnvironment,
    risk_notices: List[RiskNotice],
    data_gaps: List[str],
) -> str:
    if market_environment.blocks_new_positions():
        return "Defensive market blocks new position plans."
    high_risks = [notice for notice in risk_notices if notice.level == "high"]
    if high_risks:
        return high_risks[0].title
    if data_gaps:
        return "Key data gaps require conservative interpretation."
    return "No dominant risk notice."


def _build_watchlist(
    opportunities: List[OpportunityScore],
    trade_plans: List[TradePlan],
) -> List[WatchListItem]:
    plan_by_symbol = {plan.symbol: plan for plan in trade_plans}
    watchlist: List[WatchListItem] = []
    for opportunity in opportunities:
        if opportunity.grade not in {"S", "A"}:
            continue
        plan = plan_by_symbol.get(opportunity.symbol)
        watchlist.append(
            WatchListItem(
                symbol=opportunity.symbol,
                name=opportunity.name,
                grade=opportunity.grade,
                sector=opportunity.sector,
                watch_reason=opportunity.rank_reason,
                plan_status=plan.plan_status if plan else "watch",
            )
        )
    return watchlist


def _build_risk_notices(
    market_environment: MarketEnvironment,
    opportunities: List[OpportunityScore],
    trade_plans: List[TradePlan],
) -> List[RiskNotice]:
    notices: List[RiskNotice] = []
    if market_environment.blocks_new_positions():
        notices.append(
            RiskNotice(
                level="high",
                title="Defensive market blocks new positions",
                detail="Market state is defensive or allowed_action is no_new_position.",
            )
        )
    if market_environment.data_gaps:
        notices.append(
            RiskNotice(
                level="medium",
                title="Market environment has fallback data gaps",
                detail=", ".join(market_environment.data_gaps[:8]),
            )
        )

    risky_symbols = [item.symbol for item in opportunities if item.risk_penalty >= 10.0]
    if risky_symbols:
        notices.append(
            RiskNotice(
                level="high",
                title="High risk-penalty opportunities require downgrade review",
                symbols=risky_symbols,
            )
        )

    blocked_symbols = [plan.symbol for plan in trade_plans if plan.plan_status == "blocked"]
    if blocked_symbols:
        notices.append(
            RiskNotice(
                level="medium",
                title="Some trade plans are blocked",
                detail="Blocked plans have zero max_position_pct.",
                symbols=blocked_symbols,
            )
        )
    return notices


def _collect_data_gaps(
    market_environment: MarketEnvironment,
    opportunities: Iterable[OpportunityScore],
    trade_plans: Iterable[TradePlan],
) -> List[str]:
    gaps: List[str] = list(market_environment.data_gaps)
    for opportunity in opportunities:
        gaps.extend(opportunity.data_gaps)
    for plan in trade_plans:
        gaps.extend(plan.data_gaps)
    return list(dict.fromkeys(gaps))


def build_daily_report(
    trade_date: str,
    market_environment: MarketEnvironment,
    sector_scores: List[SectorScore | Dict],
    candidates: List[Dict],
    opportunities: List[OpportunityScore],
    trade_plans: List[TradePlan],
    source_artifacts: Dict[str, str] | None = None,
) -> DailyReport:
    """Assemble the daily report JSON contract from upstream artifacts."""
    sector_rankings = sorted(
        [_as_sector_score(item) for item in sector_scores],
        key=lambda item: item.sector_rank or 9999,
    )
    key_opportunities = [item for item in opportunities if item.is_key_opportunity()]
    risk_notices = _build_risk_notices(market_environment, opportunities, trade_plans)
    data_gaps = _collect_data_gaps(market_environment, opportunities, trade_plans)
    blocked_plan_count = sum(1 for plan in trade_plans if plan.plan_status == "blocked")

    summary = DailyReportSummary(
        market_state=market_environment.market_state,
        market_score=market_environment.market_score,
        candidate_count=len(candidates),
        key_opportunity_count=len(key_opportunities),
        trade_plan_count=len(trade_plans),
        blocked_plan_count=blocked_plan_count,
        main_risk=_main_risk(market_environment, risk_notices, data_gaps),
    )

    return DailyReport(
        trade_date=trade_date,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        summary=summary,
        market_environment=market_environment,
        sector_rankings=sector_rankings,
        key_opportunities=key_opportunities,
        trade_plans=trade_plans,
        tomorrow_watchlist=_build_watchlist(opportunities, trade_plans),
        risk_notices=risk_notices,
        data_gaps=data_gaps,
        source_artifacts=source_artifacts or {},
    )
