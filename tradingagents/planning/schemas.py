"""Schemas for conditional trade plans."""

from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field

from tradingagents.opportunity.schemas import OpportunityGrade


PlanStatus = Literal["active", "watch", "blocked"]


class TradePlan(BaseModel):
    trade_date: str
    symbol: str
    name: str = ""
    strategy_type: str = "mainline_trend"
    grade: OpportunityGrade = "C"
    plan_status: PlanStatus = "watch"
    entry_conditions: List[str] = Field(default_factory=list)
    stop_loss_conditions: List[str] = Field(default_factory=list)
    take_profit_rules: List[str] = Field(default_factory=list)
    invalidation_conditions: List[str] = Field(default_factory=list)
    max_position_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    holding_period: str = "3-10 trading days"
    watch_variables: List[str] = Field(default_factory=list)
    risk_notes: List[str] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)
    source_refs: Dict[str, str] = Field(default_factory=dict)

    def allows_new_position(self) -> bool:
        return self.plan_status == "active" and self.max_position_pct > 0
