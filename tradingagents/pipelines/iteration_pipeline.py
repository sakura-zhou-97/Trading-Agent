"""Iteration pipeline: 3-day tracking -> review -> patch pool."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from tradingagents.dataflows.config import set_config
from tradingagents.iteration import (
    load_tracking_targets,
    track_three_day_metrics,
    generate_patch_suggestions,
    generate_ai_review_suggestions,
    render_daily_review_card,
    append_proposals,
)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _write_json(path: Path, obj: Dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_tracking_md(result_d: Dict) -> str:
    lines = ["# D. 3天追踪指标", ""]
    for item in result_d.get("tracking_metrics", []):
        lines.append(
            f"- {item.get('symbol')} {item.get('name','')} | 源日期={item.get('source_trade_date')} | "
            f"T+1={item.get('t1_return_pct')}% | T+2={item.get('t2_return_pct')}% | T+3={item.get('t3_return_pct')}% | "
            f"MDD={item.get('mdd_3d_pct')}% | 剔除={item.get('should_remove')}"
        )
    return "\n".join(lines) + "\n"


def _render_patch_md(result_e: Dict) -> str:
    lines = ["# E. 规则/Prompt补丁建议", ""]
    lines.append("## Rule Patch Suggestions")
    for idx, p in enumerate(result_e.get("rule_patch_suggestions", []), start=1):
        lines.append(f"{idx}. {p.get('title')} | 置信度={p.get('confidence')} | {p.get('suggestion')}")
    lines.append("")
    lines.append("## Prompt Patch Suggestions")
    for idx, p in enumerate(result_e.get("prompt_patch_suggestions", []), start=1):
        lines.append(f"{idx}. {p.get('title')} | 置信度={p.get('confidence')} | {p.get('suggestion')}")
    return "\n".join(lines) + "\n"


def _dedupe_and_limit_proposals(proposals: list[Dict], max_items: int) -> list[Dict]:
    seen = set()
    ordered = sorted(proposals, key=lambda x: float(x.get("confidence", 0.0)), reverse=True)
    out: list[Dict] = []
    for p in ordered:
        key = (str(p.get("type", "")), str(p.get("title", "")).strip(), str(p.get("suggestion", "")).strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= max_items:
            break
    return out


def _build_iteration_trace_log(
    trade_date: str,
    lookback_days: int,
    targets: list[Dict],
    metrics: list[Dict],
    summary_payload: Dict,
    added: list[Dict],
    pool_path: Path,
) -> Dict:
    return {
        "trade_date": trade_date,
        "pipeline": "iteration",
        "step_1_tracking": {
            "input": {
                "lookback_days": lookback_days,
                "target_count": len(targets),
                "targets": targets,
            },
            "output": {
                "metrics_count": len(metrics),
                "tracking_metrics": metrics,
                "summary": summary_payload.get("summary", {}),
            },
        },
        "step_2_review_suggestions": {
            "input": {
                "metrics_count": len(metrics),
                "summary": summary_payload.get("summary", {}),
            },
            "output": {
                "rule_patch_count": len(summary_payload.get("rule_patch_suggestions", [])),
                "prompt_patch_count": len(summary_payload.get("prompt_patch_suggestions", [])),
                "rule_patch_suggestions": summary_payload.get("rule_patch_suggestions", []),
                "prompt_patch_suggestions": summary_payload.get("prompt_patch_suggestions", []),
            },
        },
        "step_3_patch_pool": {
            "input": {
                "pool_path": str(pool_path),
            },
            "output": {
                "added_count": len(added),
                "added_to_pool": added,
            },
        },
    }


def _render_iteration_trace_md(trace_log: Dict) -> str:
    s1 = trace_log.get("step_1_tracking", {})
    s2 = trace_log.get("step_2_review_suggestions", {})
    s3 = trace_log.get("step_3_patch_pool", {})
    lines = [
        "# Z. Pipeline Trace Log (股票迭代系统)",
        "",
        f"- 交易日: {trace_log.get('trade_date', '')}",
        "",
        "## Step 1 追踪",
        f"- 输入: {s1.get('input', {})}",
        f"- 输出统计: metrics={s1.get('output', {}).get('metrics_count', 0)}",
        "### 追踪明细",
    ]
    for m in s1.get("output", {}).get("tracking_metrics", []):
        lines.append(
            f"- {m.get('symbol')} {m.get('name', '')} | T+1={m.get('t1_return_pct')} | "
            f"T+2={m.get('t2_return_pct')} | T+3={m.get('t3_return_pct')} | "
            f"MDD3D={m.get('mdd_3d_pct')} | remove={m.get('should_remove')} | "
            f"reason={m.get('remove_reason', '')}"
        )

    lines.extend(
        [
            "",
            "## Step 2 复盘建议",
            f"- 输入: {s2.get('input', {})}",
            f"- 输出统计: rule={s2.get('output', {}).get('rule_patch_count', 0)}, "
            f"prompt={s2.get('output', {}).get('prompt_patch_count', 0)}",
            "### Rule 补丁建议",
        ]
    )
    for p in s2.get("output", {}).get("rule_patch_suggestions", []):
        lines.append(
            f"- {p.get('title', '')} | confidence={p.get('confidence')} | suggestion={p.get('suggestion', '')}"
        )
    lines.append("")
    lines.append("### Prompt 补丁建议")
    for p in s2.get("output", {}).get("prompt_patch_suggestions", []):
        lines.append(
            f"- {p.get('title', '')} | confidence={p.get('confidence')} | suggestion={p.get('suggestion', '')}"
        )

    lines.extend(
        [
            "",
            "## Step 3 写入补丁池",
            f"- 输入: {s3.get('input', {})}",
            f"- 输出统计: added={s3.get('output', {}).get('added_count', 0)}",
        ]
    )
    for p in s3.get("output", {}).get("added_to_pool", []):
        lines.append(
            f"- {p.get('id')} | {p.get('type')} | {p.get('status')} | {p.get('title')}"
        )
    lines.append("")
    return "\n".join(lines)


def run_iteration_pipeline(
    config: Dict,
    trade_date: Optional[str] = None,
    lookback_days: int = 3,
) -> Dict:
    """Run iteration system and output D/E artifacts."""
    trade_date = trade_date or _today()
    run_cfg = dict(config)
    run_cfg["market_type"] = "china_a"
    set_config(run_cfg)

    results_dir = run_cfg["results_dir"]
    targets = load_tracking_targets(results_dir=results_dir, trade_date=trade_date, lookback_days=lookback_days)
    metrics = track_three_day_metrics(targets)

    iter_cfg = run_cfg.get("iteration", {})
    min_valid_t3_samples = int(iter_cfg.get("min_valid_t3_samples", 5))
    max_rule_props = int(iter_cfg.get("max_rule_proposals", 8))
    max_prompt_props = int(iter_cfg.get("max_prompt_proposals", 8))
    summary_payload = generate_patch_suggestions(metrics, min_valid_t3_samples=min_valid_t3_samples)
    if bool(iter_cfg.get("enable_ai_review", True)) and metrics:
        try:
            ai_payload = generate_ai_review_suggestions(metrics, config=run_cfg)
            summary_payload["rule_patch_suggestions"].extend(ai_payload.get("rule_patch_suggestions", []))
            summary_payload["prompt_patch_suggestions"].extend(ai_payload.get("prompt_patch_suggestions", []))
        except Exception:
            # Keep deterministic review as baseline if AI review fails.
            pass
    summary_payload["rule_patch_suggestions"] = _dedupe_and_limit_proposals(
        summary_payload.get("rule_patch_suggestions", []),
        max_items=max_rule_props,
    )
    summary_payload["prompt_patch_suggestions"] = _dedupe_and_limit_proposals(
        summary_payload.get("prompt_patch_suggestions", []),
        max_items=max_prompt_props,
    )
    review_card = render_daily_review_card(summary_payload.get("summary", {}), summary_payload)

    output_dir = Path(results_dir) / "iteration" / trade_date
    output_dir.mkdir(parents=True, exist_ok=True)
    pool_path = Path(results_dir) / "iteration" / "patch_pool.json"
    added = append_proposals(
        pool_path=pool_path,
        trade_date=trade_date,
        rule_suggestions=summary_payload.get("rule_patch_suggestions", []),
        prompt_suggestions=summary_payload.get("prompt_patch_suggestions", []),
    )

    result_d = {
        "trade_date": trade_date,
        "lookback_days": lookback_days,
        "target_count": len(targets),
        "tracking_metrics": metrics,
        "summary": summary_payload.get("summary", {}),
    }
    result_e = {
        "trade_date": trade_date,
        "rule_patch_suggestions": summary_payload.get("rule_patch_suggestions", []),
        "prompt_patch_suggestions": summary_payload.get("prompt_patch_suggestions", []),
        "added_to_pool": added,
        "pool_path": str(pool_path),
    }

    _write_json(output_dir / "D_tracking_metrics.json", result_d)
    _write_json(output_dir / "E_patch_proposals.json", result_e)
    (output_dir / "D_tracking_metrics.md").write_text(_render_tracking_md(result_d), encoding="utf-8")
    (output_dir / "E_patch_proposals.md").write_text(_render_patch_md(result_e), encoding="utf-8")
    (output_dir / "daily_review_card.md").write_text(review_card, encoding="utf-8")

    trace_log = _build_iteration_trace_log(
        trade_date=trade_date,
        lookback_days=lookback_days,
        targets=targets,
        metrics=metrics,
        summary_payload=summary_payload,
        added=added,
        pool_path=pool_path,
    )
    _write_json(output_dir / "Z_pipeline_trace_log.json", trace_log)
    (output_dir / "Z_pipeline_trace_log.md").write_text(
        _render_iteration_trace_md(trace_log),
        encoding="utf-8",
    )

    return {
        "trade_date": trade_date,
        "output_dir": str(output_dir),
        "D": result_d,
        "E": result_e,
        "trace_log_path": str(output_dir / "Z_pipeline_trace_log.md"),
    }
