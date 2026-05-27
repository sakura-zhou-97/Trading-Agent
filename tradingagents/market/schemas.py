"""Schemas for market environment outputs."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


MarketState = Literal["attack", "normal", "cautious", "defensive", "unknown"]
MarketAllowedAction = Literal["normal", "light", "observe_only", "no_new_position", "unknown"]
ComponentStatus = Literal["ok", "missing", "fallback"]


class MarketScoreComponent(BaseModel):
    name: str
    weight: float = Field(default=0.0, ge=0.0, le=1.0)
    score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    status: ComponentStatus = "ok"
    reason: str = ""


class MarketEnvironment(BaseModel):
    trade_date: str
    market_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    market_state: MarketState = "unknown"
    allowed_action: MarketAllowedAction = "unknown"
    index_trend_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    breadth_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    turnover_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    limit_sentiment_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    risk_appetite_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    components: List[MarketScoreComponent] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)

    def blocks_new_positions(self) -> bool:
        return self.market_state == "defensive" or self.allowed_action == "no_new_position"
