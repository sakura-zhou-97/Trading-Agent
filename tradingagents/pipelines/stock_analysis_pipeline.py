"""Stock analysis pipeline: coarse -> sector -> fine."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Any

from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.china.universe_provider import get_daily_universe
from tradingagents.dataflows.china.batch_quotes_provider import attach_struct_features
from tradingagents.screener import run_coarse_screen, load_rulebook
from tradingagents.analyzer import analyze_candidates, run_story_analysis, run_story_analysis_2layer
from tradingagents.sector import calibrate_with_sector


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _write_json(path: Path, obj: Dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_candidates_md(candidates: List[Dict]) -> str:
    lines = ["# A. 候选池（全量通过硬规则）", ""]
    for item in candidates:
        lines.append(
            f"- {item.get('symbol')} {item.get('name','')} | "
            f"涨幅={item.get('change_pct')}% | 标签={','.join(item.get('coarse_reason_tags', []))}"
        )
    return "\n".join(lines) + "\n"


def _render_initial_md(result_b: Dict) -> str:
    lines = ["# C. AI全量分析清单 + 决策卡", ""]
    for item in result_b.get("analysis_list", []):
        symbol = item.get("symbol")
        lines.append(f"## {symbol} {item.get('name', '')}")
        card = result_b.get("decision_card_5lines", {}).get(symbol, "")
        lines.append(card)
        lines.append("")
    return "\n".join(lines)


def _render_all_cards_md(result_b: Dict) -> str:
    lines = ["# C2. 全量候选决策卡（逐票）", ""]
    trace = result_b.get("analysis_trace", {})
    card_5 = result_b.get("decision_card_5lines", {})
    for card in result_b.get("decision_cards", []):
        symbol = card.get("symbol", "")
        name = card.get("name", "")
        mode = trace.get(symbol, {}).get("mode", "unknown")
        lines.append(f"## {symbol} {name}")
        lines.append(f"- 分析模式: {mode}")
        lines.append("")
        lines.append(card_5.get(symbol, ""))
        lines.append("")
    return "\n".join(lines)


def _render_calibrated_md(result_c: Dict) -> str:
    lines = ["# B. 板块校准结果", ""]
    for item in result_c.get("calibrated_analysis_list", []):
        lines.append(
            f"- {item.get('symbol')} {item.get('name','')} | "
            f"板块={item.get('sector')} | 乘数={item.get('sector_multiplier')} | 原因={item.get('calibration_reason')}"
        )
    return "\n".join(lines) + "\n"


def _write_story_prompt_io(result_story: Dict, output_dir: Path) -> None:
    """将三层 prompt 的原始输入/输出写入 story_prompt_io/<symbol>/ 下的文本文件。"""
    if result_story.get("mode") != "two_layer":
        return
    io_dir = output_dir / "story_prompt_io"
    io_dir.mkdir(parents=True, exist_ok=True)
    steps = [
        ("narrative_generator", "1_narrative"),
        ("timeline_catalyst", "2_timeline"),
        ("story_synthesizer", "3_synthesizer"),
    ]
    for symbol, rec in result_story.get("story_by_symbol", {}).items():
        prompt_io = rec.get("prompt_io", {})
        if not prompt_io:
            continue
        symbol_dir = io_dir / symbol
        symbol_dir.mkdir(parents=True, exist_ok=True)
        for step_key, prefix in steps:
            step_data = prompt_io.get(step_key, {})
            raw_in = step_data.get("raw_input") or step_data.get("prompt_text") or ""
            raw_out = step_data.get("raw_output") or step_data.get("raw_response") or ""
            (symbol_dir / f"{prefix}_input.txt").write_text(raw_in, encoding="utf-8")
            (symbol_dir / f"{prefix}_output.txt").write_text(raw_out, encoding="utf-8")


def _render_story_analysis_md(result_story: Dict, candidates: List[Dict]) -> str:
    """Render B_story_analysis.md: per-symbol story features (same tier as B sector)."""
    name_by_symbol = {c.get("symbol", ""): c.get("name", "") for c in candidates}
    mode = result_story.get("mode", "simple")
    lines = ["# B2. 故事性分析结果", ""]
    if mode == "two_layer":
        lines.append("模式: 两层（叙事假设+时间轴催化 → 故事卡合成）\n")
    for symbol, data in result_story.get("story_by_symbol", {}).items():
        name = name_by_symbol.get(symbol, "")
        sp = data.get("story_payload", {})
        heat = sp.get("story_heat_level", "")
        n_count = sp.get("news_count", 0)
        mainline = "是" if sp.get("is_mainline_candidate") else "否"
        risk = "是" if sp.get("has_risk_alert") else "否"
        if mode == "two_layer" and data.get("story_card"):
            card = data["story_card"]
            one_liner = (card.get("one_liner") or "")[:80]
            market_impression = (card.get("market_impression") or "")[:100]
            ea = card.get("evidence_assessment", {}) or {}
            hardness = ea.get("hardness_grade", "")
            highlights = card.get("highlights", []) or []
            drawbacks = card.get("drawbacks", []) or []
            main_a = (card.get("main_story_A") or "").strip()
            main_b = (card.get("main_story_B") or "").strip()
            lines.append(
                f"- {symbol} {name} | 硬度={hardness} | 新闻条数={n_count} | 主线={mainline} | 风险={risk}"
            )
            if market_impression:
                lines.append(f"  - 市场印象: {market_impression}")
            if main_a:
                lines.append(f"  - 主故事A: {main_a[:120]}{'...' if len(main_a) > 120 else ''}")
            if main_b:
                lines.append(f"  - 主故事B: {main_b[:120]}{'...' if len(main_b) > 120 else ''}")
            if one_liner:
                lines.append(f"  - 一句话: {one_liner}")
            if highlights:
                top_h = "；".join([str(x.get("title", "")) for x in highlights[:3] if x.get("title")])
                if top_h:
                    lines.append(f"  - 亮点: {top_h}")
            if drawbacks:
                top_d = "；".join([str(x.get("title", "")) for x in drawbacks[:3] if x.get("title")])
                if top_d:
                    lines.append(f"  - 缺点: {top_d}")
        else:
            lines.append(f"- {symbol} {name} | 热度={heat} | 新闻条数={n_count} | 主线候选={mainline} | 风险提示={risk}")
    return "\n".join(lines) + "\n"


def _build_theme_heatmap(top_candidates: List[Dict], decision_cards: List[Dict]) -> Dict:
    sector_count: Dict[str, int] = {}
    sector_change_sum: Dict[str, float] = {}
    for item in top_candidates:
        sector = str(item.get("industry", "")).strip() or "unknown_sector"
        sector_count[sector] = sector_count.get(sector, 0) + 1
        sector_change_sum[sector] = sector_change_sum.get(sector, 0.0) + float(item.get("change_pct", 0.0))

    story_tags = {"risk_alert": 0, "theme_hot": 0, "breakout": 0}
    for c in decision_cards:
        text = " ".join(
            [
                str(c.get("tradability", "")),
                str(c.get("sustainability", "")),
                str(c.get("expectation_gap", "")),
                " ".join(c.get("evidence_chain", []) or []),
            ]
        )
        if any(k in text for k in ["风险", "回撤", "兑现"]):
            story_tags["risk_alert"] += 1
        if any(k in text for k in ["主线", "龙头", "题材", "催化"]):
            story_tags["theme_hot"] += 1
        if any(k in text for k in ["突破", "涨停", "加速"]):
            story_tags["breakout"] += 1

    sectors = []
    for s, cnt in sector_count.items():
        avg_change = sector_change_sum[s] / max(cnt, 1)
        sectors.append({"sector": s, "count": cnt, "avg_change_pct": round(avg_change, 3)})
    sectors.sort(key=lambda x: (x["count"], x["avg_change_pct"]), reverse=True)
    return {
        "top_sectors": sectors[:10],
        "story_tag_stats": story_tags,
    }


def _aggregate_drop_reasons(dropped: List[Dict]) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    for item in dropped:
        for reason in item.get("drop_reasons", []):
            key = str(reason)
            stats[key] = stats.get(key, 0) + 1
    return stats


def _build_analysis_trace_log(
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
    }


def _render_analysis_trace_md(trace_log: Dict) -> str:
    s0 = trace_log.get("step_0_goals_and_boundaries", {})
    s1 = trace_log.get("step_1_coarse_screen", {})
    s2 = trace_log.get("step_2_sector_calibration", {})
    s2_story = trace_log.get("step_2_story_analysis", {})
    s3 = trace_log.get("step_3_fine_screen", {})

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
            f"sector={item.get('sector', '')} | multiplier={item.get('sector_multiplier', '')} | "
            f"reason={item.get('calibration_reason', '')}"
        )

    out2_story = s2_story.get("output", {})
    lines.extend([
        "",
        "## Step 2b 故事性分析（前置，与板块同层）",
        f"- 输入: {s2_story.get('input', {})}",
        f"- 输出统计: story_count={out2_story.get('story_count', 0)}",
    ])

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
    lines.append("")
    return "\n".join(lines)


def run_stock_analysis_pipeline(
    config: Dict,
    trade_date: Optional[str] = None,
    top_n: int = 30,
    initial_n: int = 10,
    min_change_pct: float = 5.0,
    max_universe: int = 400,
    enable_ai: bool = True,
) -> Dict:
    """Run stock analysis system and output A/B/C artifacts."""
    trade_date = trade_date or _today()
    run_cfg = dict(config)
    run_cfg["market_type"] = "china_a"
    set_config(run_cfg)
    rulebook = load_rulebook(run_cfg.get("stock_analysis", {}).get("rulebook_path"))

    universe = get_daily_universe(
        trade_date=trade_date,
        min_change_pct=min_change_pct,
        main_board_only=True,
        non_st_only=True,
        max_items=max_universe,
    )

    enriched = attach_struct_features(universe=universe, trade_date=trade_date, lookback_days=30)
    coarse = run_coarse_screen(records=enriched, top_n=top_n, rulebook=rulebook)
    result_a = {
        "trade_date": trade_date,
        "count": len(coarse.candidates),
        "candidates": coarse.candidates,
    }

    result_c = calibrate_with_sector(
        analysis_list=coarse.candidates,
        all_candidates=coarse.candidates,
    )
    result_c["trade_date"] = trade_date

    sector_context_by_symbol = {
        str(row.get("symbol", "")): {
            "sector": row.get("sector", ""),
            "sector_day_strength": row.get("sector_day_strength"),
            "sector_trend_3d": row.get("sector_trend_3d"),
            "sector_multiplier": row.get("sector_multiplier"),
            "sector_leader_symbol": row.get("sector_leader_symbol", ""),
            "sector_leader_status": row.get("sector_leader_status", ""),
            "calibration_reason": row.get("calibration_reason", ""),
        }
        for row in result_c.get("calibrated_analysis_list", [])
    }

    # 故事性分析：与板块分析同一层，结果作为 C 的输入
    story_mode = run_cfg.get("stock_analysis", {}).get("story_analysis_mode", "simple")
    if story_mode == "two_layer" and enable_ai:
        result_story = run_story_analysis_2layer(
            candidates=coarse.candidates,
            trade_date=trade_date,
            config=run_cfg,
        )
    else:
        result_story = run_story_analysis(
            candidates=coarse.candidates,
            trade_date=trade_date,
        )
    result_story["trade_date"] = trade_date

    result_b = analyze_candidates(
        candidates=coarse.candidates,
        trade_date=trade_date,
        config=run_cfg,
        max_selected=initial_n,
        enable_ai=enable_ai,
        sector_context_by_symbol=sector_context_by_symbol,
        story_by_symbol=result_story.get("story_by_symbol", {}),
    )
    result_b["trade_date"] = trade_date
    result_s = _build_theme_heatmap(
        top_candidates=coarse.candidates,
        decision_cards=result_b.get("decision_cards", []),
    )
    result_s["trade_date"] = trade_date

    output_dir = Path(run_cfg["results_dir"]) / "screener" / trade_date
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON outputs
    _write_json(output_dir / "A_candidates.json", result_a)
    _write_json(output_dir / "B_sector_calibration.json", result_c)
    _write_json(output_dir / "B_story_analysis.json", result_story)
    _write_story_prompt_io(result_story, output_dir)
    _write_json(output_dir / "C_ai_analysis_with_cards.json", result_b)
    _write_json(output_dir / "S_theme_heatmap.json", result_s)

    # Markdown outputs
    (output_dir / "A_candidates.md").write_text(_render_candidates_md(result_a["candidates"]), encoding="utf-8")
    (output_dir / "B_sector_calibration.md").write_text(_render_calibrated_md(result_c), encoding="utf-8")
    (output_dir / "B_story_analysis.md").write_text(
        _render_story_analysis_md(result_story, coarse.candidates), encoding="utf-8"
    )
    (output_dir / "C_ai_analysis_with_cards.md").write_text(_render_initial_md(result_b), encoding="utf-8")
    (output_dir / "C_all_decision_cards.md").write_text(_render_all_cards_md(result_b), encoding="utf-8")
    (output_dir / "S_theme_heatmap.md").write_text(
        "# S. Theme Heatmap\n\n"
        + "\n".join(
            [
                f"- {x['sector']} | 数量={x['count']} | 平均涨幅={x['avg_change_pct']}"
                for x in result_s.get("top_sectors", [])
            ]
        )
        + "\n\n"
        + f"- 故事标签统计: {result_s.get('story_tag_stats', {})}\n",
        encoding="utf-8",
    )

    # Per-stock decision card files for quick manual review
    per_stock_dir = output_dir / "decision_cards"
    per_stock_dir.mkdir(parents=True, exist_ok=True)
    trace = result_b.get("analysis_trace", {})
    card_5 = result_b.get("decision_card_5lines", {})
    for card in result_b.get("decision_cards", []):
        symbol = card.get("symbol", "")
        if not symbol:
            continue
        name = card.get("name", "")
        mode = trace.get(symbol, {}).get("mode", "unknown")
        lines = [
            f"# {symbol} {name}",
            "",
            f"- 分析模式: {mode}",
        ]
        lines.extend(["", card_5.get(symbol, "")])
        (per_stock_dir / f"{symbol}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    trace_log = _build_analysis_trace_log(
        trade_date=trade_date,
        min_change_pct=min_change_pct,
        max_universe=max_universe,
        enable_ai=enable_ai,
        rulebook=rulebook,
        prompt_path=str(run_cfg.get("stock_analysis", {}).get("prompt_path", "")),
        universe=universe,
        coarse=coarse,
        result_c=result_c,
        result_story=result_story,
        result_b=result_b,
    )
    _write_json(output_dir / "Z_pipeline_trace_log.json", trace_log)
    (output_dir / "Z_pipeline_trace_log.md").write_text(
        _render_analysis_trace_md(trace_log),
        encoding="utf-8",
    )

    return {
        "trade_date": trade_date,
        "output_dir": str(output_dir),
        "A": result_a,
        "B": result_c,
        "B_story": result_story,
        "C": result_b,
        "S": result_s,
        "trace_log_path": str(output_dir / "Z_pipeline_trace_log.md"),
    }
