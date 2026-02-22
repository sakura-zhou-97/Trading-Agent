"""Decision card schema for stock analysis output."""

from __future__ import annotations

from typing import Literal, List

from pydantic import BaseModel, Field


StageType = Literal["启动", "加速", "调整", "二次启动"]
ConclusionType = Literal["趋势", "情绪", "混合"]


class DecisionCard(BaseModel):
    symbol: str
    name: str
    industry: str = ""
    conclusion_type: ConclusionType
    stage: StageType
    evidence_chain: List[str]
    tradability: str
    sustainability: str
    expectation_gap: str
    structure_position: str
    max_risk: str
    reversal_trigger: str
    info_gaps: List[str] = Field(default_factory=list)

    def to_five_line_card(self) -> str:
        return "\n".join(
            [
                f"1) 结论: {self.conclusion_type}",
                f"2) 阶段: {self.stage}",
                f"3) 证据链: {self.evidence_chain[0]} / {self.evidence_chain[1]} / {self.evidence_chain[2]}",
                f"4) 可交易性/可持续性/预期差: {self.tradability} | {self.sustainability} | {self.expectation_gap}",
                f"5) 结构位/最大风险/反转条件: {self.structure_position} | {self.max_risk} | {self.reversal_trigger}",
            ]
        )
