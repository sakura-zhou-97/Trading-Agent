"""Stock analysis pipeline: coarse -> sector -> fine."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.china.universe_provider import get_daily_universe
from tradingagents.dataflows.china.batch_quotes_provider import attach_struct_features
from tradingagents.screener import run_coarse_screen, load_rulebook
from tradingagents.analyzer import analyze_candidates, run_story_analysis, run_story_analysis_2layer
from tradingagents.sector import calibrate_with_sector
from tradingagents.market import build_market_environment, render_market_environment_md
from tradingagents.opportunity import SCORING_PROFILE, render_opportunity_scores_md, score_opportunities
from tradingagents.planning import generate_trade_plans, render_trade_plans_md
from tradingagents.reporting import build_daily_report, model_to_dict, render_daily_report_md, write_json, write_text
from tradingagents.pipelines.stock_analysis_steps import build_sector_context_by_symbol, build_theme_heatmap
from tradingagents.pipelines.trace_builder import build_stock_analysis_trace_log, render_stock_analysis_trace_md


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


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
            f"板块={item.get('sector')} | 板块分={item.get('sector_score')} | "
            f"状态={item.get('sector_state')} | 排名={item.get('sector_rank')} | "
            f"乘数={item.get('sector_multiplier')} | 原因={item.get('calibration_reason')}"
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
            write_text(symbol_dir / f"{prefix}_input.txt", raw_in)
            write_text(symbol_dir / f"{prefix}_output.txt", raw_out)


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
    market_environment = build_market_environment(
        trade_date=trade_date,
        universe=enriched,
        candidates=coarse.candidates,
    )
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

    sector_context_by_symbol = build_sector_context_by_symbol(result_c.get("calibrated_analysis_list", []))

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
    opportunities = score_opportunities(
        trade_date=trade_date,
        market_environment=market_environment,
        candidates=result_c.get("calibrated_analysis_list", []),
        decision_cards=result_b.get("decision_cards", []),
        story_by_symbol=result_story.get("story_by_symbol", {}),
        analysis_trace=result_b.get("analysis_trace", {}),
    )
    result_o = {
        "trade_date": trade_date,
        "scoring_profile": SCORING_PROFILE,
        "count": len(opportunities),
        "opportunities": [model_to_dict(item) for item in opportunities],
    }
    trade_plans = generate_trade_plans(
        trade_date=trade_date,
        market_environment=market_environment,
        opportunities=opportunities,
        decision_cards=result_b.get("decision_cards", []),
        candidates=result_c.get("calibrated_analysis_list", []),
    )
    result_p = {
        "trade_date": trade_date,
        "count": len(trade_plans),
        "plans": [model_to_dict(item) for item in trade_plans],
    }
    daily_report = build_daily_report(
        trade_date=trade_date,
        market_environment=market_environment,
        sector_scores=result_c.get("sector_scores", []),
        candidates=coarse.candidates,
        opportunities=opportunities,
        trade_plans=trade_plans,
        source_artifacts={
            "M": "M_market_environment.json",
            "A": "A_candidates.json",
            "B": "B_sector_calibration.json",
            "B_story": "B_story_analysis.json",
            "C": "C_ai_analysis_with_cards.json",
            "O": "O_opportunity_scores.json",
            "P": "P_trade_plans.json",
        },
    )
    result_r = model_to_dict(daily_report)
    result_s = build_theme_heatmap(
        top_candidates=coarse.candidates,
        decision_cards=result_b.get("decision_cards", []),
    )
    result_s["trade_date"] = trade_date

    output_dir = Path(run_cfg["results_dir"]) / "screener" / trade_date
    output_dir.mkdir(parents=True, exist_ok=True)

    # JSON outputs
    write_json(output_dir / "M_market_environment.json", model_to_dict(market_environment))
    write_json(output_dir / "A_candidates.json", result_a)
    write_json(output_dir / "B_sector_calibration.json", result_c)
    write_json(output_dir / "B_story_analysis.json", result_story)
    _write_story_prompt_io(result_story, output_dir)
    write_json(output_dir / "C_ai_analysis_with_cards.json", result_b)
    write_json(output_dir / "O_opportunity_scores.json", result_o)
    write_json(output_dir / "P_trade_plans.json", result_p)
    write_json(output_dir / "R_daily_report.json", result_r)
    write_json(output_dir / "S_theme_heatmap.json", result_s)

    # Markdown outputs
    write_text(
        output_dir / "M_market_environment.md",
        render_market_environment_md(market_environment),
    )
    write_text(output_dir / "A_candidates.md", _render_candidates_md(result_a["candidates"]))
    write_text(output_dir / "B_sector_calibration.md", _render_calibrated_md(result_c))
    write_text(
        output_dir / "B_story_analysis.md",
        _render_story_analysis_md(result_story, coarse.candidates),
    )
    write_text(output_dir / "C_ai_analysis_with_cards.md", _render_initial_md(result_b))
    write_text(output_dir / "C_all_decision_cards.md", _render_all_cards_md(result_b))
    write_text(
        output_dir / "O_opportunity_scores.md",
        render_opportunity_scores_md(opportunities),
    )
    write_text(
        output_dir / "P_trade_plans.md",
        render_trade_plans_md(trade_plans),
    )
    write_text(
        output_dir / "R_daily_report.md",
        render_daily_report_md(daily_report),
    )
    write_text(
        output_dir / "S_theme_heatmap.md",
        "# S. Theme Heatmap\n\n"
        + "\n".join(
            [
                f"- {x['sector']} | 数量={x['count']} | 平均涨幅={x['avg_change_pct']}"
                for x in result_s.get("top_sectors", [])
            ]
        )
        + "\n\n"
        + f"- 故事标签统计: {result_s.get('story_tag_stats', {})}\n",
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
        write_text(per_stock_dir / f"{symbol}.md", "\n".join(lines) + "\n")

    trace_log = build_stock_analysis_trace_log(
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
        result_o=result_o,
        result_p=result_p,
        result_r=result_r,
    )
    write_json(output_dir / "Z_pipeline_trace_log.json", trace_log)
    write_text(output_dir / "Z_pipeline_trace_log.md", render_stock_analysis_trace_md(trace_log))

    return {
        "trade_date": trade_date,
        "output_dir": str(output_dir),
        "M": model_to_dict(market_environment),
        "A": result_a,
        "B": result_c,
        "B_story": result_story,
        "C": result_b,
        "O": result_o,
        "P": result_p,
        "R": result_r,
        "S": result_s,
        "trace_log_path": str(output_dir / "Z_pipeline_trace_log.md"),
    }
