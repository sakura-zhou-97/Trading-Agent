"""Review engine for rule/prompt patch suggestions."""

from __future__ import annotations

import json
from statistics import mean
from typing import Dict, List, Optional

from tradingagents.llm_clients import create_llm_client

def _nonnull(values: List):
    return [v for v in values if v is not None]


def _build_proposal(
    proposal_type: str,
    title: str,
    suggestion: str,
    evidence: Dict,
    confidence: float,
    trigger_samples: Optional[List[Dict]] = None,
) -> Dict:
    return {
        "type": proposal_type,  # rule | prompt
        "title": title,
        "suggestion": suggestion,
        "evidence": evidence,
        "trigger_samples": trigger_samples or [],
        "confidence": round(confidence, 3),
        "status": "proposed",  # proposed | accepted | rejected
    }


def _estimate_filter_impact(tracking_metrics: List[Dict], symbol_set: set[str]) -> Dict:
    """Rough offline estimate for rule change impact."""
    before = tracking_metrics
    after = [x for x in tracking_metrics if x.get("symbol") not in symbol_set]

    def _avg(arr: List[Dict], key: str):
        vals = [x.get(key) for x in arr if x.get(key) is not None]
        return round(mean(vals), 3) if vals else None

    return {
        "before_count": len(before),
        "after_count": len(after),
        "before_avg_t1": _avg(before, "t1_return_pct"),
        "after_avg_t1": _avg(after, "t1_return_pct"),
        "before_avg_mdd": _avg(before, "mdd_3d_pct"),
        "after_avg_mdd": _avg(after, "mdd_3d_pct"),
    }


def generate_patch_suggestions(tracking_metrics: List[Dict], min_valid_t3_samples: int = 5) -> Dict:
    """Generate rule/prompt patch proposals from rolling 3-day tracking."""
    if not tracking_metrics:
        return {
            "summary": {"sample_size": 0},
            "rule_patch_suggestions": [],
            "prompt_patch_suggestions": [],
        }

    t1 = _nonnull([x.get("t1_return_pct") for x in tracking_metrics])
    t2 = _nonnull([x.get("t2_return_pct") for x in tracking_metrics])
    t3 = _nonnull([x.get("t3_return_pct") for x in tracking_metrics])
    mdd = _nonnull([x.get("mdd_3d_pct") for x in tracking_metrics])

    wins_t3 = [v for v in t3 if v > 0]
    remove_cnt = sum(1 for x in tracking_metrics if x.get("should_remove"))
    sample_size = len(tracking_metrics)
    avg_mdd = mean(mdd) if mdd else 0.0
    has_valid_t3 = len(t3) >= min_valid_t3_samples
    win_rate_t3 = (len(wins_t3) / len(t3)) if has_valid_t3 else None

    rule_suggestions: List[Dict] = []
    prompt_suggestions: List[Dict] = []

    if avg_mdd <= -6.0:
        trigger = [
            {
                "symbol": x.get("symbol"),
                "mdd_3d_pct": x.get("mdd_3d_pct"),
                "reason_t1": x.get("reason_t1"),
            }
            for x in tracking_metrics
            if x.get("mdd_3d_pct") is not None and x.get("mdd_3d_pct") <= -6.0
        ]
        symbols = {str(t.get("symbol", "")) for t in trigger if t.get("symbol")}
        impact = _estimate_filter_impact(tracking_metrics, symbols)
        rule_suggestions.append(
            _build_proposal(
                "rule",
                "强化回撤过滤",
                "建议在粗筛阶段新增高波动剔除条件，并提高量能持续性门槛（例如vol_ratio下限上调）。",
                {"avg_mdd_3d_pct": round(avg_mdd, 3), "sample_size": sample_size, "estimated_impact": impact},
                confidence=0.72,
                trigger_samples=trigger,
            )
        )
        prompt_suggestions.append(
            _build_proposal(
                "prompt",
                "增强风险项约束",
                "建议在决策卡Prompt中增加“若3天MDD预估>8%必须下调续涨评分并给出量化止损位”的硬性规则。",
                {"avg_mdd_3d_pct": round(avg_mdd, 3), "estimated_impact": impact},
                confidence=0.68,
                trigger_samples=trigger,
            )
        )

    if has_valid_t3 and win_rate_t3 is not None and win_rate_t3 < 0.45:
        trigger = [
            {
                "symbol": x.get("symbol"),
                "t3_return_pct": x.get("t3_return_pct"),
                "decision_stage": x.get("decision_stage"),
            }
            for x in tracking_metrics
            if x.get("t3_return_pct") is not None and x.get("t3_return_pct") <= 0
        ]
        rule_suggestions.append(
            _build_proposal(
                "rule",
                "下调高位加速权重",
                "建议降低‘高位突破+高换手’组合权重，增加‘次日延续性’验证后再入选初选池。",
                {"win_rate_t3": round(win_rate_t3, 3), "sample_size_t3": len(t3)},
                confidence=0.7,
                trigger_samples=trigger,
            )
        )
        prompt_suggestions.append(
            _build_proposal(
                "prompt",
                "强化兑现识别",
                "建议Prompt增加‘上涨来自兑现还是预期扩张’的判别模板，兑现型个股置信度上限下调。",
                {"win_rate_t3": round(win_rate_t3, 3)},
                confidence=0.66,
                trigger_samples=trigger,
            )
        )

    if remove_cnt > max(2, int(sample_size * 0.35)):
        rule_suggestions.append(
            _build_proposal(
                "rule",
                "启用追踪剔除机制",
                "建议将‘3天内大跌或连续下跌’剔除机制设为默认生效，以降低劣化样本在后续日重复入池。",
                {"remove_count": remove_cnt, "sample_size": sample_size},
                confidence=0.75,
                trigger_samples=[
                    {"symbol": x.get("symbol"), "remove_reason": x.get("remove_reason")}
                    for x in tracking_metrics
                    if x.get("should_remove")
                ],
            )
        )

    if not has_valid_t3:
        rule_suggestions.append(
            _build_proposal(
                "rule",
                "样本不足暂缓激进调参",
                "当前T+3有效样本不足，建议继续累积样本后再对核心权重做大幅调整。",
                {"valid_t3_samples": len(t3), "required": min_valid_t3_samples},
                confidence=0.8,
                trigger_samples=[{"valid_t3_samples": len(t3), "required": min_valid_t3_samples}],
            )
        )
        prompt_suggestions.append(
            _build_proposal(
                "prompt",
                "补充样本期判定提示",
                "建议Prompt在输出结论时增加‘样本期充分性检查’，样本不足时主动提示保守决策。",
                {"valid_t3_samples": len(t3), "required": min_valid_t3_samples},
                confidence=0.78,
                trigger_samples=[{"valid_t3_samples": len(t3), "required": min_valid_t3_samples}],
            )
        )

    if not rule_suggestions:
        rule_suggestions.append(
            _build_proposal(
                "rule",
                "维持当前硬规则",
                "当前样本未显示明显规则劣化，建议继续观察并累积样本后再调整权重。",
                {"sample_size": sample_size, "win_rate_t3": round(win_rate_t3, 3) if win_rate_t3 is not None else None},
                confidence=0.58,
            )
        )
    if not prompt_suggestions:
        prompt_suggestions.append(
            _build_proposal(
                "prompt",
                "维持当前Prompt结构",
                "当前样本下Prompt输出稳定，建议先保持模板并继续收集误判案例。",
                {"sample_size": sample_size},
                confidence=0.57,
            )
        )

    summary = {
        "sample_size": sample_size,
        "avg_t1_return_pct": round(mean(t1), 3) if t1 else None,
        "avg_t2_return_pct": round(mean(t2), 3) if t2 else None,
        "avg_t3_return_pct": round(mean(t3), 3) if t3 else None,
        "avg_mdd_3d_pct": round(avg_mdd, 3) if mdd else None,
        "win_rate_t3": round(win_rate_t3, 3) if win_rate_t3 is not None else None,
        "valid_t3_samples": len(t3),
        "required_t3_samples": min_valid_t3_samples,
        "remove_count": remove_cnt,
    }

    return {
        "summary": summary,
        "rule_patch_suggestions": rule_suggestions,
        "prompt_patch_suggestions": prompt_suggestions,
    }


def render_daily_review_card(track_summary: Dict, suggestions: Dict) -> str:
    lines = [
        "# Daily Review Card",
        "",
        "## 3-Day Tracking Snapshot",
        f"- 样本数: {track_summary.get('sample_size')}",
        f"- T+3 胜率: {track_summary.get('win_rate_t3')}",
        f"- 3天平均回撤(MDD): {track_summary.get('avg_mdd_3d_pct')}",
        f"- 剔除数量: {track_summary.get('remove_count')}",
        "",
        "## Rule Patch Suggestions",
    ]
    for idx, p in enumerate(suggestions.get("rule_patch_suggestions", []), start=1):
        lines.append(f"{idx}. {p['title']} | 置信度={p['confidence']} | {p['suggestion']}")
    lines.append("")
    lines.append("## Prompt Patch Suggestions")
    for idx, p in enumerate(suggestions.get("prompt_patch_suggestions", []), start=1):
        lines.append(f"{idx}. {p['title']} | 置信度={p['confidence']} | {p['suggestion']}")
    lines.append("")
    return "\n".join(lines)


def _extract_json(text: str) -> Dict:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON content")
    return json.loads(text[start : end + 1])


def generate_ai_review_suggestions(tracking_metrics: List[Dict], config: Dict) -> Dict:
    """Use LLM to summarize misjudgment patterns and suggest patch candidates."""
    provider = config.get("llm_provider", "openai")
    model = config.get("quick_think_llm", "gpt-5-mini")
    kwargs: Dict = {}
    if provider == "openai" and config.get("openai_reasoning_effort"):
        kwargs["reasoning_effort"] = config["openai_reasoning_effort"]
    if provider == "google" and config.get("google_thinking_level"):
        kwargs["thinking_level"] = config["google_thinking_level"]
    client = create_llm_client(provider=provider, model=model, base_url=config.get("backend_url"), **kwargs)
    llm = client.get_llm()

    prompt = (
        "你是交易系统复盘分析师。请根据3天追踪数据，输出规则补丁与Prompt补丁建议。"
        "你必须只返回JSON，不要解释。\n"
        "输入样本:\n"
        f"{json.dumps(tracking_metrics, ensure_ascii=False)[:18000]}\n\n"
        "输出JSON结构:\n"
        "{\n"
        "  \"rule_patch_suggestions\": [\n"
        "    {\"type\":\"rule\",\"title\":\"...\",\"suggestion\":\"...\",\"evidence\":{\"k\":\"v\"},\"confidence\":0.0-1.0}\n"
        "  ],\n"
        "  \"prompt_patch_suggestions\": [\n"
        "    {\"type\":\"prompt\",\"title\":\"...\",\"suggestion\":\"...\",\"evidence\":{\"k\":\"v\"},\"confidence\":0.0-1.0}\n"
        "  ]\n"
        "}"
    )
    resp = llm.invoke(prompt)
    content = getattr(resp, "content", str(resp))
    obj = _extract_json(content)

    def _norm(proposals: List[Dict], expected_type: str) -> List[Dict]:
        out: List[Dict] = []
        for p in proposals or []:
            out.append(
                {
                    "type": expected_type,
                    "title": str(p.get("title", f"{expected_type}_patch")),
                    "suggestion": str(p.get("suggestion", "")),
                    "evidence": p.get("evidence", {}),
                    "confidence": round(float(p.get("confidence", 0.5)), 3),
                    "status": "proposed",
                    "source": "ai_review",
                }
            )
        return out

    return {
        "rule_patch_suggestions": _norm(obj.get("rule_patch_suggestions", []), "rule"),
        "prompt_patch_suggestions": _norm(obj.get("prompt_patch_suggestions", []), "prompt"),
    }
