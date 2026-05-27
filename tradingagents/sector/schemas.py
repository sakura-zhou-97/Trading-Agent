"""Schemas for sector context scoring."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


SectorState = Literal["mainline", "strong", "watch", "weak", "unknown"]


class SectorScore(BaseModel):
    sector: str
    sector_adapter: str = "industry"
    sector_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    sector_state: SectorState = "unknown"
    sector_rank: Optional[int] = Field(default=None, ge=1)
    sector_count: int = Field(default=0, ge=0)
    short_term_return_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    relative_strength_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    turnover_expansion_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    breadth_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    limit_up_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    persistence_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    leader_symbol: str = ""
    leader_status: str = ""
    reasons: List[str] = Field(default_factory=list)
    data_gaps: List[str] = Field(default_factory=list)
