"""Default configuration dict. Runtime get/set: tradingagents.dataflows.config.get_config/set_config."""
import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.2",
    "quick_think_llm": "gpt-5-mini",
    "backend_url": "https://api.openai.com/v1",
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Market type: "us" (default) or "china_a"
    # When china_a, sentiment & social analysts are disabled automatically
    "market_type": "us",
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    # China A-share data source priority: "akshare" (free) > "tushare" (token auth)
    # Token env: TINYSHARE_TOKEN (fallback: TUSHARE_TOKEN)
    "china_data_priority": ["akshare", "tushare"],
    # Stock analysis system (screening + analyzer) defaults
    "stock_analysis": {
        "top_n_coarse": 30,
        "top_n_fine": 10,
        "min_change_pct": 5.0,
        "max_universe": 400,
        "enable_ai": True,
        "rulebook_path": "",
        "prompt_path": "tradingagents/analyzer/prompts/stock_analysis_prompt_cn.md",
        "story_analysis_mode": "simple",
    },
    "iteration": {
        "lookback_days": 3,
        "min_valid_t3_samples": 5,
        "enable_ai_review": True,
        "max_rule_proposals": 8,
        "max_prompt_proposals": 8,
    },
}
