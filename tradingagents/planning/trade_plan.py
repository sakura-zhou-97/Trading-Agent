"""Deterministic conditional trade-plan generation."""

from __future__ import annotations

from typing import Dict, List, Optional

from tradingagents.market.schemas import MarketEnvironment
from tradingagents.opportunity.schemas import OpportunityScore
from tradingagents.planning.schemas import TradePlan


MIN_PLAN_GRADES = {"S", "A"}


def _position_cap(market_state: str, grade: str) -> float:
    if market_state == "attack":
        return 0.15 if grade == "S" else 0.10
    if market_state == "normal":
        return 0.10 if grade == "S" else 0.07
    if market_state == "cautious":
        return 0.05 if grade == "S" else 0.03
    return 0.0


def _plan_status(environment: MarketEnvironment, opportunity: OpportunityScore) -> str:
    if environment.blocks_new_positions():
        return "blocked"
    if opportunity.risk_penalty >= 12.0:
        return "blocked"
    if environment.market_state == "cautious" and opportunity.grade != "S":
        return "watch"
    if opportunity.grade in MIN_PLAN_GRADES:
        return "active"
    return "watch"


def _apply_risk_cap(max_position_pct: float, opportunity: OpportunityScore) -> float:
    if opportunity.risk_penalty >= 12.0:
        return 0.0
    if opportunity.risk_penalty >= 9.0:
        return round(max_position_pct * 0.5, 4)
    return max_position_pct


def _entry_conditions(opportunity: OpportunityScore, decision_card: Dict, candidate: Dict) -> List[str]:
    stage = str(decision_card.get("stage", ""))
    reversal_trigger = str(decision_card.get("reversal_trigger", "")).strip()
    sector = opportunity.sector or str(candidate.get("sector", ""))
    ma5 = candidate.get("ma5")
    ma10 = candidate.get("ma10")
    conditions: List[str] = []

    if stage == "加速":
        conditions.append("不追高，等待回踩 MA5/MA10 附近缩量企稳后再观察。")
    elif stage == "二次启动":
        conditions.append("缩量横盘后再次放量突破短期平台高点时再观察。")
    elif stage == "调整":
        conditions.append("重新站回 MA10 且板块同步转强后再观察。")
    else:
        conditions.append("放量突破前高或关键平台，且收盘不明显回落时再观察。")

    if reversal_trigger and reversal_trigger != "待观察":
        conditions.append(f"确认条件：{reversal_trigger}")
    if ma5 or ma10:
        conditions.append(f"均线条件：价格保持在 MA5={ma5}、MA10={ma10} 的强势结构内。")
    if sector:
        conditions.append(f"板块条件：{sector} 保持强势语境，不能明显退潮。")
    return conditions


def _stop_loss_conditions(decision_card: Dict, candidate: Dict) -> List[str]:
    ma10 = candidate.get("ma10")
    ma20 = candidate.get("ma20")
    conditions = [
        f"技术止损：有效跌破 MA20={ma20} 或平台下沿。",
        f"短线走弱：跌破 MA10={ma10} 后无法快速收复。",
    ]
    max_risk = str(decision_card.get("max_risk", "")).strip()
    if max_risk and max_risk != "待观察":
        conditions.append(f"风险止损：{max_risk}")
    return conditions


def _take_profit_rules(opportunity: OpportunityScore) -> List[str]:
    rules = [
        "若放量加速后次日不能继续走强，优先保护利润。",
        "若板块主线转弱或同板块高位股亏钱效应扩散，降低预期。",
    ]
    if opportunity.grade == "S":
        rules.append("S 级机会可分批观察趋势延续，但不得突破仓位上限。")
    else:
        rules.append("A 级观察以买点质量优先，不把反弹当成趋势确认。")
    return rules


def _invalidation_conditions(
    environment: MarketEnvironment,
    opportunity: OpportunityScore,
    decision_card: Dict,
) -> List[str]:
    conditions = [
        "市场状态转为 defensive 时，新增仓位计划立即失效。",
        f"板块语境不再支持：{opportunity.sector} 跌出强势或观察状态。",
    ]
    if opportunity.risk_flags:
        conditions.append("风险标记触发或恶化：" + ", ".join(opportunity.risk_flags))
    expectation_gap = str(decision_card.get("expectation_gap", "")).strip()
    if expectation_gap and expectation_gap != "待观察":
        conditions.append(f"预期差证伪：{expectation_gap}")
    if environment.data_gaps:
        conditions.append("关键市场数据缺口未补齐时，不提高计划等级。")
    return conditions


def _watch_variables(opportunity: OpportunityScore, decision_card: Dict) -> List[str]:
    variables = [
        "market_state",
        f"sector:{opportunity.sector}",
        "volume_confirmation",
        "MA10/MA20",
    ]
    if decision_card.get("reversal_trigger"):
        variables.append("reversal_trigger")
    if opportunity.data_gaps:
        variables.append("data_gaps")
    return variables


def generate_trade_plans(
    trade_date: str,
    market_environment: MarketEnvironment,
    opportunities: List[OpportunityScore],
    decision_cards: Optional[List[Dict]] = None,
    candidates: Optional[List[Dict]] = None,
    min_plan_grades: Optional[set[str]] = None,
) -> List[TradePlan]:
    """Generate conditional plans for key opportunities using deterministic risk rules."""
    min_plan_grades = min_plan_grades or MIN_PLAN_GRADES
    card_by_symbol = {str(card.get("symbol", "")): card for card in (decision_cards or [])}
    candidate_by_symbol = {str(item.get("symbol", "")): item for item in (candidates or [])}
    plans: List[TradePlan] = []

    for opportunity in opportunities:
        if opportunity.grade not in min_plan_grades:
            continue

        card = card_by_symbol.get(opportunity.symbol, {})
        candidate = candidate_by_symbol.get(opportunity.symbol, {})
        status = _plan_status(market_environment, opportunity)
        max_position_pct = _position_cap(market_environment.market_state, opportunity.grade)
        max_position_pct = _apply_risk_cap(max_position_pct, opportunity)
        if status != "active":
            max_position_pct = 0.0

        risk_notes = list(opportunity.risk_flags)
        if market_environment.blocks_new_positions():
            risk_notes.append("defensive_market_blocks_new_positions")
        if opportunity.risk_penalty >= 9.0:
            risk_notes.append("high_risk_penalty_caps_position")

        plans.append(
            TradePlan(
                trade_date=trade_date,
                symbol=opportunity.symbol,
                name=opportunity.name,
                strategy_type=opportunity.strategy_type,
                grade=opportunity.grade,
                plan_status=status,
                entry_conditions=_entry_conditions(opportunity, card, candidate),
                stop_loss_conditions=_stop_loss_conditions(card, candidate),
                take_profit_rules=_take_profit_rules(opportunity),
                invalidation_conditions=_invalidation_conditions(market_environment, opportunity, card),
                max_position_pct=round(max_position_pct, 4),
                holding_period="3-10 trading days",
                watch_variables=_watch_variables(opportunity, card),
                risk_notes=risk_notes,
                data_gaps=list(dict.fromkeys(opportunity.data_gaps + market_environment.data_gaps)),
                source_refs={
                    "opportunity": "O_opportunity_scores.json",
                    "market": "M_market_environment.json",
                    "decision_card": "C_ai_analysis_with_cards.json",
                },
            )
        )

    return plans
