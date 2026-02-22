# -*- coding: utf-8 -*-
"""校验 B_story_analysis.json：prompt_io 完整性及解析结果结构。"""
import json
import sys
from pathlib import Path

# Windows 控制台 UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main():
    base = Path(__file__).resolve().parents[1]
    # 支持传入路径，如: python validate_story_result.py results/screener/2026-02-13/single_603667/B_story_analysis_603667.json
    if len(sys.argv) > 1 and sys.argv[1].strip():
        path = Path(sys.argv[1])
        if not path.is_absolute():
            path = base / path
    else:
        path = base / "results" / "screener" / "2026-02-13" / "B_story_analysis.json"
    if not path.exists():
        print(f"不存在: {path}")
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    mode = data.get("mode", "")
    count = data.get("count", 0)
    story_by_symbol = data.get("story_by_symbol", {})

    print("=== B_story_analysis 校验 ===\n")
    print(f"mode: {mode}")
    print(f"count: {count}\n")

    if mode != "two_layer":
        print("非 two_layer 模式，跳过 prompt_io 校验。")
        return 0

    ok = 0
    errs = []

    for symbol, rec in story_by_symbol.items():
        name = rec.get("story_card", {}).get("one_liner", "")[:40] or "(无)"
        prompt_io = rec.get("prompt_io", {})

        # 1) 三步都有
        for step in ("narrative_generator", "timeline_catalyst", "story_synthesizer"):
            if step not in prompt_io:
                errs.append(f"{symbol} 缺少 prompt_io.{step}")
                continue
            s = prompt_io[step]
            if not isinstance(s, dict):
                errs.append(f"{symbol}.{step} 不是 dict")
                continue
            if "prompt_input" not in s:
                errs.append(f"{symbol}.{step} 缺少 prompt_input")
            if "prompt_text" not in s:
                errs.append(f"{symbol}.{step} 缺少 prompt_text")
            if "raw_response" not in s:
                errs.append(f"{symbol}.{step} 缺少 raw_response")
            if "parsed" not in s:
                errs.append(f"{symbol}.{step} 缺少 parsed")

        # 2) 解析结果结构粗检
        ng = prompt_io.get("narrative_generator", {}).get("parsed", {})
        if ng and not isinstance(ng, dict):
            errs.append(f"{symbol} narrative_generator.parsed 不是 dict")
        elif ng:
            if "market_narrative" not in ng and "company_direction" not in ng:
                errs.append(f"{symbol} narrative.parsed 缺少 market_narrative/company_direction")

        tl = prompt_io.get("timeline_catalyst", {}).get("parsed", {})
        if tl and not isinstance(tl, dict):
            errs.append(f"{symbol} timeline_catalyst.parsed 不是 dict")
        elif tl:
            if "timeline_1_3m" not in tl and "catalyst_quality" not in tl:
                errs.append(f"{symbol} timeline.parsed 缺少 timeline_1_3m/catalyst_quality")

        sc = rec.get("story_card", {})
        if sc:
            if "one_liner" not in sc and "story" not in sc:
                errs.append(f"{symbol} story_card 缺少 one_liner/story")

        if not any(e.startswith(symbol) for e in errs[-10:]):
            ok += 1
        print(f"  {symbol} prompt_io 三步齐全, story_card 有 one_liner: {bool(sc.get('one_liner'))}")

    print()
    if errs:
        print("校验发现问题:")
        for e in errs[:30]:
            print(f"  - {e}")
        if len(errs) > 30:
            print(f"  ... 共 {len(errs)} 条")
    else:
        print("校验通过: prompt_io 三步均有 prompt_input / prompt_text / raw_response / parsed。")
    print(f"\n标的数: {len(story_by_symbol)}, 通过: {ok}")
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
