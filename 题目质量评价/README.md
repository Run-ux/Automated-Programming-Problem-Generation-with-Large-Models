# 题目质量评价

该目录提供“题面质量 + 反换皮”单题评估器。它直接消费 `生成题面/artifacts/*.json`，同时读取原始 schema、prepared schema 和原题文本，输出：

- `reports/json/*_quality_report.json`
- `reports/md/*_quality_report.md`

## 核心能力

- 质量评分：`variant_fidelity`、`spec_completeness`、`cross_section_consistency`、`sample_quality`、`oj_readability`
- 反换皮判定：基于 `schema_distance`、`changed_axes`、原题文本对比和 `solution_transfer_risk`
- 状态输出：`pass`、`revise_quality`、`reject_as_retheme`、`reject_invalid`

## 运行

```bash
python main.py ^
  --original-schema D:\AutoProblemGen\生成题面\prepared_schemas\CF25E.json ^
  --prepared-schema D:\AutoProblemGen\生成题面\prepared_schemas\CF25E.json ^
  --artifact D:\AutoProblemGen\生成题面\artifacts\CF25E_v1_campus_ops_20260315_233917.json ^
  --disable-llm
```

如果已配置 `QWEN_API_KEY` 或 `DASHSCOPE_API_KEY`，默认会启用 LLM Judge。也可以使用 `--disable-llm` 退回启发式评估。

默认情况下，报告会保存到当前项目目录下的 `reports/json` 和 `reports/md`；如需覆盖该行为，可显式传入 `--output-json` 或 `--output-md`。

## 测试

```bash
python -m unittest discover -s D:\AutoProblemGen\题目质量评价\tests -v
```
