"""Schemas for opportunity scoring outputs."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


OpportunityGrade = Literal["S", "A", "B", "C"]
OpportunityStatus = Literal["key_opportunity", "watch", "low_priority", "dropped"]


class OpportunityScoreComponent(BaseModel):
    name: str
    weight: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    contribution: float = 0.0
    reason: str = ""


class OpportunityScore(BaseModel):
    trade_date: str
    symbol: str
    name: str = ""
    sector: str = ""
    sector_adapter: str = "industry"
    strategy_type: str = "mainline_trend"
    scoring_profile: str = "v1_default"
    total_score: float = Field(default=0.0, ge=0.0, le=100.0)
    grade: OpportunityGrade = "C"
    status: OpportunityStatus = "low_priority"
    market_score_component: float = 0.0
    sector_score_component: float = 0.0
    stock_score_component: float = 0.0
    structure_score_component: float = 0.0
    strategy_score_component: float = 0.0
    ai_score_component: float = 0.0
    entry_quality_component: float = 0.0
    risk_penalty: float = 0.0
    components: List[OpportunityScoreComponent] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)
    rank_reason: str = ""
    source_refs: Dict[str, str] = Field(default_factory=dict)

    def is_key_opportunity(self) -> bool:
        return self.grade in {"S", "A"} and self.status == "key_opportunity"
