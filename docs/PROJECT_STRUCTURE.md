# 项目结构说明

本文档描述 TradingAgents 代码与流水线布局，便于维护与扩展。

**更详细的模块输入输出与字段含义见 [SYSTEM_DESIGN.md](SYSTEM_DESIGN.md)。**

## 顶层目录

```
TradingAgents/
├── cli/                    # 命令行入口 (python -m cli.main)
├── tradingagents/          # 核心包
├── scripts/                # 辅助脚本（单票故事、校验、示例生成）
├── docs/                   # 文档
├── results/                # 流水线输出（本地，已 gitignore）
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 核心包 `tradingagents/`

| 模块 | 职责 |
|------|------|
| **dataflows/** | 数据源：行情、基本面、新闻、概念。按市场路由（A 股 / 美股）。 |
| **screener/** | 粗筛规则（coarse_rules）：涨跌幅、趋势、标签等硬规则。 |
| **sector/** | 板块校准：行业强度、龙头状态、乘数。 |
| **analyzer/** | 故事两层分析（story_two_layer）、细筛与决策卡（fine_filter_engine）。 |
| **pipelines/** | 流水线编排：stock_analysis_pipeline（A→B→C）、iteration_pipeline。 |
| **llm_clients/** | LLM 多厂商封装（OpenAI / Google / Anthropic 等）。 |
| **agents/** | 分析师 / 研究员 / 交易员 / 风控等 Agent（LangGraph 用）。 |
| **graph/** | 交易图：传播、信号、反思。 |
| **utils/** | 通用工具（如 A 股代码规范化）。 |
| **iteration/** | 迭代：跟踪、复盘、补丁池。 |

## 数据流与路由

- **dataflows/interface.py**：`route_by_market_*` 按 `is_china_a_stock()` 选择 A 股或美股数据源。
- **dataflows/china/**：A 股用 akshare（优先）、tushare；含行情、基本面、新闻、**概念板块**（get_stock_concepts_em）。
- **dataflows/config.py**：与 `tradingagents/default_config.py` 配合，供 dataflows 读取配置。

## 股票分析流水线（A → B → C）

1. **A**：粗筛候选（screener + batch_quotes），输出 `A_candidates.json`。
2. **B**：板块校准（sector） + 故事两层分析（analyzer.story_two_layer），输出 `B_sector_calibration.json`、`B_story_analysis.json`、`story_prompt_io/<symbol>/`。
3. **C**：细筛 + AI 决策卡（analyzer.fine_filter_engine），输出 `C_ai_analysis_with_cards.json`、`decision_cards/`。
4. **Z**：`Z_pipeline_trace_log.json/.md` 为当次运行的可选追踪日志。

配置入口：`default_config.py` 中 `stock_analysis.story_analysis_mode`（`simple` / `two_layer`）、`enable_ai` 等。

## 脚本 `scripts/`

| 脚本 | 用途 |
|------|------|
| **run_single_story.py** | 单票两层故事（如 603667），写 `results/screener/<date>/single_<symbol>/`。 |
| **validate_story_result.py** | 校验 `B_story_analysis.json` 的 prompt_io 与结构。 |
| **gen_example_payloads.py** | 生成 C 阶段输入示例，供文档/测试用。 |

## 输出目录 `results/`（本地，不提交）

- **results/screener/\<date\>/**：当日的 A/B/C JSON、MD、decision_cards、story_prompt_io、Z_pipeline_trace_log。
- **results/screener/\<date\>/single_<symbol>/**：单票故事测试输出。
- **results/iteration/\<date\>/**：迭代流水线输出。

## 配置统一

- 运行时配置：`tradingagents/default_config.py`（`DEFAULT_CONFIG`）+ `tradingagents/dataflows/config.py`（get_config/set_config）。
- CLI 可覆盖：`cli/main.py` 中通过参数或环境覆盖 `stock_analysis`、`market_type` 等。
