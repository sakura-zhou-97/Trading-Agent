# Scripts

辅助脚本，需在项目根目录执行（或确保 `PYTHONPATH` 含项目根）。

| 脚本 | 说明 |
|------|------|
| **run_single_story.py** | 对单只股票（默认 603667）跑两层故事分析，写入 `results/screener/<日期>/single_<symbol>/`。需配置 `market_type=china_a` 与 API Key。 |
| **validate_story_result.py** | 校验 `B_story_analysis.json` 的 prompt_io 与解析结构，用于调试。 |
| **gen_example_payloads.py** | 生成 C 阶段输入示例 JSON，供数据流文档或测试使用。 |

示例：

```bash
# 项目根目录
python scripts/run_single_story.py
python scripts/validate_story_result.py   # 需修改脚本内 results 路径或传参
```
