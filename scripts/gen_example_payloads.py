# -*- coding: utf-8 -*-
"""生成 002498 的 C 阶段三种输入示例（含故事特征），供数据流文档使用。"""
import json
import sys
from pathlib import Path

# Windows 控制台 UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tradingagents.analyzer.fine_filter_engine import (
    _build_raw_stock_payload,
    _build_story_features,
    _build_sector_payload,
)

# A 的一条 (002498)，并带上 B 阶段写入的板块字段
item = {
    "symbol": "002498",
    "ts_code": "002498.SZ",
    "name": "汉缆股份",
    "market": "主板",
    "industry": "电气设备",
    "is_st": False,
    "change_pct": 10.0813,
    "close": 6.77,
    "open": 6.28,
    "high": 6.77,
    "low": 6.28,
    "volume": 2741560.81,
    "amount": 1829739.761,
    "trend_label": "uptrend",
    "recent_3d_change": 17.83,
    "last_close": 6.77,
    "ma5": 6.024,
    "ma10": 5.909,
    "ma20": 5.761,
    "vol_ratio": 0.947,
    "coarse_reason_tags": ["breakout", "trend_aligned", "high_position", "concept_present"],
    "sector": "电气设备",
    "sector_day_strength": 10.037,
    "sector_trend_3d": 16.07,
    "sector_multiplier": 1.15,
    "sector_leader_symbol": "002498",
    "sector_leader_status": "强",
    "calibration_reason": "板块走强，上调评估",
}
stock = _build_raw_stock_payload(item)
sector_ctx = {
    "002498": {
        "sector": "电气设备",
        "sector_day_strength": 10.037,
        "sector_trend_3d": 16.07,
        "sector_multiplier": 1.15,
        "sector_leader_symbol": "002498",
        "sector_leader_status": "强",
        "calibration_reason": "板块走强，上调评估",
    }
}
sector = _build_sector_payload(item, sector_ctx)

# 故事特征：无新闻
story_empty = _build_story_features("")
# 故事特征：有新闻示例
news_sample = """### 汉缆股份涨停 电气设备龙头获机构关注
公司为电缆龙头，近期政策利好。龙虎榜显示机构买入。
### 风险提示：短期涨幅较大
"""
story_with_news = _build_story_features(news_sample)

out = {
    "stock_payload": stock,
    "sector_payload": sector,
    "story_payload_empty": story_empty,
    "story_payload_with_news": story_with_news,
    "news_sample": news_sample.strip(),
}
print(json.dumps(out, ensure_ascii=False, indent=2))
