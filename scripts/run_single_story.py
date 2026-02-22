# -*- coding: utf-8 -*-
"""单票运行两层故事分析，用于测试（如五洲新春 603667）主故事 A/B 结构。"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根在 path 中并加载 .env
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

from dotenv import load_dotenv
load_dotenv()

from tradingagents.dataflows.config import set_config, get_config
from tradingagents.analyzer import run_story_analysis_2layer


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_story_prompt_io(result_story: dict, output_dir: Path) -> None:
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


def main():
    symbol = "603667"
    name = "五洲新春"
    trade_date = datetime.now().strftime("%Y-%m-%d")

    # 单票候选（最小字段即可，故事层会拉取新闻/基本面/概念）
    candidates = [
        {
            "symbol": symbol,
            "name": name,
            "industry": "通用设备",
            "change_pct": 0.0,
            "recent_3d_change": None,
        }
    ]

    cfg = get_config()
    cfg["market_type"] = "china_a"
    cfg.setdefault("stock_analysis", {})["story_analysis_mode"] = "two_layer"
    cfg.setdefault("stock_analysis", {})["enable_ai"] = True
    set_config(cfg)
    run_cfg = get_config()

    print(f"Running two-layer story for {symbol} {name} @ {trade_date} ...")
    result_story = run_story_analysis_2layer(
        candidates=candidates,
        trade_date=trade_date,
        config=run_cfg,
    )
    result_story["trade_date"] = trade_date

    out_dir = Path(run_cfg["results_dir"]) / "screener" / trade_date / f"single_{symbol}"
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_json(out_dir / f"B_story_analysis_{symbol}.json", result_story)
    _write_story_prompt_io(result_story, out_dir)

    card = (result_story.get("story_by_symbol") or {}).get(symbol, {}).get("story_card") or {}
    main_a = (card.get("main_story_A") or "").strip()
    main_b = (card.get("main_story_B") or "").strip()
    impression = (card.get("market_impression") or "").strip()

    print("\n--- 主故事 A ---")
    print(main_a or "(未输出)")
    print("\n--- 主故事 B ---")
    print(main_b or "(未输出)")
    print("\n--- 市场印象 ---")
    print(impression or "(未输出)")
    print(f"\n结果已写入: {out_dir}")


if __name__ == "__main__":
    main()
