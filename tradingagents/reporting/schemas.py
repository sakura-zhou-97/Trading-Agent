"""Schemas for the daily report data contract."""

from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field

from tradingagents.market.schemas import MarketEnvironment
from tradingagents.opportunity.schemas import OpportunityScore
from tradingagents.planning.schemas import TradePlan
from tradingagents.sector.schemas import SectorScore


ReportFormat = Literal["json", "markdown"]


class DailyReportSummary(BaseModel):
    market_state: str = "unknown"
    market_score: float | None = None
    candidate_count: int = 0
    key_opportunity_count: int = 0
    trade_plan_count: int = 0
    blocked_plan_count: int = 0
    main_risk: str = ""


class WatchListItem(BaseModel):
    symbol: str
    name: str = ""
    grade: str = ""
    sector: str = ""
    watch_reason: str = ""
    plan_status: str = "watch"


class RiskNotice(BaseModel):
    level: Literal["high", "medium", "low", "unknown"] = "unknown"
    title: str
    detail: str = ""
    symbols: List[str] = Field(default_factory=list)


class DailyReport(BaseModel):
    report_version: str = "v1"
    trade_date: str
    generated_at: str = ""
    formats: List[ReportFormat] = Field(default_factory=lambda: ["json", "markdown"])
    scoring_profile: str = "v1_default"
    summary: DailyReportSummary
    market_environment: MarketEnvironment
    sector_rankings: List[SectorScore] = Field(default_factory=list)
    key_opportunities: List[OpportunityScore] = Field(default_factory=list)
    trade_plans: List[TradePlan] = Field(default_factory=list)
    tomorrow_watchlist: List[WatchListItem] = Field(default_factory=list)
    risk_notices: List[RiskNotice] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)
    source_artifacts: Dict[str, str] = Field(default_factory=dict)

    def has_blocked_new_positions(self) -> bool:
        return self.market_environment.blocks_new_positions()
