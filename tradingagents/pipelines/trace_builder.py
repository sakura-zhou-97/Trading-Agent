"""Trace builders for pipeline audit artifacts."""

from __future__ import annotations

from typing import Any, Dict, List


def _aggregate_drop_reasons(dropped: List[Dict]) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    for item in dropped:
        for reason in item.get("drop_reasons", []):
            key = str(reason)
            stats[key] = stats.get(key, 0) + 1
    return stats


def build_stock_analysis_trace_log(
    trade_date: str,
    min_change_pct: float,
    max_universe: int,
    enable_ai: bool,
    rulebook: Dict[str, Any],
    prompt_path: str,
    universe: List[Dict],
    coarse,
    result_c: Dict,
    result_story: Dict,
    result_b: Dict,
    result_o: Dict | None = None,
    result_p: Dict | None = None,
    result_r: Dict | None = None,
) -> Dict:
    coarse_map = {str(x.get("symbol", "")): x for x in coarse.candidates}
    analyzed_rows = []
    for item in result_b.get("decision_cards", []):
        symbol = str(item.get("symbol", ""))
        coarse_item = coarse_map.get(symbol, {})
        analyzed_rows.append(
            {
                "symbol": symbol,
                "name": item.get("name", ""),
                "change_pct": coarse_item.get("change_pct"),
                "coarse_reason_tags": coarse_item.get("coarse_reason_tags", []),
                "stage": item.get("stage", ""),
            }
        )

    return {
        "trade_date": trade_date,
        "pipeline": "stock_analysis",
        "step_0_goals_and_boundaries": {
            "input": {
                "min_change_pct": min_change_pct,
                "max_universe": max_universe,
                "enable_ai": enable_ai,
                "rulebook_hard_filters": rulebook.get("hard_filters", {}),
            },
            "output": {
                "ready": True,
                "notes": "粗筛看结构，先做板块定语境，再做AI个股分析，最终由人工决策",
            },
        },
        "step_1_coarse_screen": {
            "input": {
                "universe_count": len(universe),
                "min_change_pct": min_change_pct,
                "max_universe": max_universe,
                "hard_filters": rulebook.get("hard_filters", {}),
            },
            "output": {
                "dropped_count": len(coarse.dropped),
                "dropped_reason_stats": _aggregate_drop_reasons(coarse.dropped),
                "dropped_examples": coarse.dropped[:200],
                "candidate_count": len(coarse.candidates),
                "candidates": coarse.candidates,
            },
        },
        "step_2_sector_calibration": {
            "input": {
                "candidate_count": len(coarse.candidates),
            },
            "output": {
                "sector_stats": result_c.get("sector_stats", {}),
                "sector_scores": result_c.get("sector_scores", []),
                "calibrated_count": len(result_c.get("calibrated_analysis_list", [])),
                "calibrated_rows": result_c.get("calibrated_analysis_list", []),
            },
        },
        "step_2_story_analysis": {
            "input": {
                "candidate_count": len(coarse.candidates),
            },
            "output": {
                "story_count": result_story.get("count", 0),
                "story_by_symbol_keys": list(result_story.get("story_by_symbol", {}).keys()),
            },
        },
        "step_3_fine_screen": {
            "input": {
                "candidate_count": len(coarse.candidates),
                "enable_ai": enable_ai,
                "prompt_path": prompt_path,
                "has_sector_context": True,
                "has_story_context": bool(result_story.get("story_by_symbol")),
            },
            "output": {
                "analyzed_count": len(analyzed_rows),
                "analyzed_rows": analyzed_rows,
                "analysis_trace": result_b.get("analysis_trace", {}),
                "info_gaps": result_b.get("info_gaps", []),
            },
        },
        "step_4_opportunity_scoring": {
            "output": {
                "scoring_profile": (result_o or {}).get("scoring_profile"),
                "opportunity_count": (result_o or {}).get("count", 0),
                "opportunities": (result_o or {}).get("opportunities", []),
            },
        },
        "step_5_trade_planning": {
            "output": {
                "plan_count": (result_p or {}).get("count", 0),
                "plans": (result_p or {}).get("plans", []),
            },
        },
        "step_6_daily_report": {
            "output": {
                "summary": (result_r or {}).get("summary", {}),
                "source_artifacts": (result_r or {}).get("source_artifacts", {}),
            },
        },
    }


def render_stock_analysis_trace_md(trace_log: Dict) -> str:
    s0 = trace_log.get("step_0_goals_and_boundaries", {})
    s1 = trace_log.get("step_1_coarse_screen", {})
    s2 = trace_log.get("step_2_sector_calibration", {})
    s2_story = trace_log.get("step_2_story_analysis", {})
    s3 = trace_log.get("step_3_fine_screen", {})
    s4 = trace_log.get("step_4_opportunity_scoring", {})
    s5 = trace_log.get("step_5_trade_planning", {})
    s6 = trace_log.get("step_6_daily_report", {})

    lines = [
        "# Z. Pipeline Trace Log (股票分析系统)",
        "",
        f"- 交易日: {trace_log.get('trade_date', '')}",
        "",
        "## Step 0 目标与边界",
        f"- 输入参数: {s0.get('input', {})}",
        f"- 输出: {s0.get('output', {})}",
        "",
        "## Step 1 粗筛（结构硬规则）",
        f"- 输入: {s1.get('input', {})}",
        f"- 输出统计: dropped={s1.get('output', {}).get('dropped_count', 0)}, candidates={s1.get('output', {}).get('candidate_count', 0)}",
        f"- 剔除原因统计: {s1.get('output', {}).get('dropped_reason_stats', {})}",
        "",
        "### 候选（粗筛后）",
    ]
    for item in s1.get("output", {}).get("candidates", []):
        lines.append(
            f"- {item.get('symbol')} {item.get('name', '')} | "
            f"change_pct={item.get('change_pct')} | tags={item.get('coarse_reason_tags', [])}"
        )

    lines.extend(["", "## Step 2 板块分析（前置）", f"- 输入: {s2.get('input', {})}"])
    out2 = s2.get("output", {})
    lines.append(f"- 输出统计: calibrated={out2.get('calibrated_count', 0)}")
    lines.append("### 板块校准结果")
    for item in out2.get("calibrated_rows", []):
        lines.append(
            f"- {item.get('symbol')} {item.get('name', '')} | "
            f"sector={item.get('sector', '')} | sector_score={item.get('sector_score', '')} | "
            f"state={item.get('sector_state', '')} | multiplier={item.get('sector_multiplier', '')} | "
            f"reason={item.get('calibration_reason', '')}"
        )

    out2_story = s2_story.get("output", {})
    lines.extend(
        [
            "",
            "## Step 2b 故事性分析（前置，与板块同层）",
            f"- 输入: {s2_story.get('input', {})}",
            f"- 输出统计: story_count={out2_story.get('story_count', 0)}",
        ]
    )

    lines.extend(["", "## Step 3 精筛（AI个股分析）", f"- 输入: {s3.get('input', {})}"])
    out3 = s3.get("output", {})
    lines.append(f"- 输出统计: analyzed={out3.get('analyzed_count', 0)}")
    lines.append("")
    lines.append("### 分析明细（全量）")
    for item in out3.get("analyzed_rows", []):
        lines.append(
            f"- {item.get('symbol')} {item.get('name', '')} | "
            f"change_pct={item.get('change_pct')} | stage={item.get('stage')} | tags={item.get('coarse_reason_tags', [])}"
        )

    out4 = s4.get("output", {})
    lines.extend(["", "## Step 4 机会评分", f"- scoring_profile={out4.get('scoring_profile')}, count={out4.get('opportunity_count')}"])
    for item in out4.get("opportunities", [])[:10]:
        lines.append(f"- {item.get('symbol')} {item.get('name', '')} | grade={item.get('grade')} | score={item.get('total_score')}")

    out5 = s5.get("output", {})
    lines.extend(["", "## Step 5 交易计划", f"- plan_count={out5.get('plan_count')}"])
    for item in out5.get("plans", [])[:10]:
        lines.append(f"- {item.get('symbol')} | status={item.get('plan_status')} | max_position={item.get('max_position_pct')}")

    out6 = s6.get("output", {})
    lines.extend(["", "## Step 6 每日报告", f"- summary={out6.get('summary', {})}", ""])
    return "\n".join(lines)
