"""Patch proposal pool persistence."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def _now_id(prefix: str, idx: int) -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{ts}_{idx:02d}"


def load_patch_pool(pool_path: Path) -> Dict:
    if not pool_path.exists():
        return {"proposals": []}
    return json.loads(pool_path.read_text(encoding="utf-8"))


def save_patch_pool(pool_path: Path, pool: Dict) -> None:
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    pool_path.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")


def append_proposals(
    pool_path: Path,
    trade_date: str,
    rule_suggestions: List[Dict],
    prompt_suggestions: List[Dict],
) -> List[Dict]:
    pool = load_patch_pool(pool_path)
    proposals = pool.get("proposals", [])
    added: List[Dict] = []

    idx = 1
    for p in rule_suggestions:
        item = dict(p)
        item["id"] = _now_id("rule", idx)
        item["trade_date"] = trade_date
        item["status"] = "proposed"
        proposals.append(item)
        added.append(item)
        idx += 1
    for p in prompt_suggestions:
        item = dict(p)
        item["id"] = _now_id("prompt", idx)
        item["trade_date"] = trade_date
        item["status"] = "proposed"
        proposals.append(item)
        added.append(item)
        idx += 1

    pool["proposals"] = proposals
    save_patch_pool(pool_path, pool)
    return added


def set_proposal_status(pool_path: Path, proposal_ids: List[str], status: str) -> List[Dict]:
    """Set proposal status to proposed/accepted/rejected."""
    if status not in {"proposed", "accepted", "rejected"}:
        raise ValueError("Invalid status")
    pool = load_patch_pool(pool_path)
    proposals = pool.get("proposals", [])
    updated: List[Dict] = []
    id_set = set(proposal_ids)
    for p in proposals:
        if p.get("id") in id_set:
            p["status"] = status
            updated.append(p)
    pool["proposals"] = proposals
    save_patch_pool(pool_path, pool)
    return updated


def apply_accepted_proposals(
    pool_path: Path,
    rulebook_path: Path,
    prompt_path: Path,
) -> Dict:
    """Apply accepted proposals into rulebook/prompt with idempotent marker."""
    pool = load_patch_pool(pool_path)
    proposals = pool.get("proposals", [])

    try:
        import yaml  # type: ignore
    except Exception as exc:
        raise RuntimeError("PyYAML is required to apply rule patches") from exc

    if rulebook_path.exists():
        rulebook = yaml.safe_load(rulebook_path.read_text(encoding="utf-8")) or {}
    else:
        rulebook = {}
    if not isinstance(rulebook, dict):
        rulebook = {}
    rulebook.setdefault("hard_filters", {})
    rulebook.setdefault("weights", {})
    rulebook.setdefault("applied_rule_notes", [])

    prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    if "## Iteration Patches" not in prompt_text:
        prompt_text = prompt_text.rstrip() + "\n\n## Iteration Patches\n"

    applied_rule_ids: List[str] = []
    applied_prompt_ids: List[str] = []
    for p in proposals:
        if p.get("status") != "accepted":
            continue
        if p.get("applied") is True:
            continue
        pid = str(p.get("id", ""))
        ptype = p.get("type")
        title = str(p.get("title", ""))
        suggestion = str(p.get("suggestion", ""))
        if ptype == "rule":
            # Minimal deterministic application rules.
            if "回撤过滤" in title:
                rulebook["hard_filters"]["max_3d_mdd_pct"] = -8.0
            if "高位加速权重" in title:
                base = float(rulebook["weights"].get("style_score", 0.10))
                rulebook["weights"]["style_score"] = round(max(0.05, base - 0.02), 3)
            rulebook["applied_rule_notes"].append({"id": pid, "title": title, "suggestion": suggestion})
            applied_rule_ids.append(pid)
        elif ptype == "prompt":
            prompt_text += f"\n- [{pid}] {title}: {suggestion}\n"
            applied_prompt_ids.append(pid)
        p["applied"] = True
        p["applied_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rulebook_path.parent.mkdir(parents=True, exist_ok=True)
    rulebook_path.write_text(yaml.safe_dump(rulebook, allow_unicode=True, sort_keys=False), encoding="utf-8")
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt_text, encoding="utf-8")

    pool["proposals"] = proposals
    save_patch_pool(pool_path, pool)
    return {
        "applied_rule_ids": applied_rule_ids,
        "applied_prompt_ids": applied_prompt_ids,
        "rulebook_path": str(rulebook_path),
        "prompt_path": str(prompt_path),
    }
