# 四元组抽取

当前目录直接面向 `D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs` 中的单题 schema JSON。

输入约定已经固定为新结构：

- 每个输入文件对应 1 道题
- 顶层字段至少包含 `problem_id`、`title`、`description`、`source`
- `description` 中包含题面正文以及 `Input`、`Output`、`Examples` 等分节
- `reference_solution.code` 为标准解法代码，当前仅在 invariant 抽取时使用

抽取时会自动完成两件事：

- 保留完整 `description` 作为 prompt 主输入
- 从 `description` 中尝试切分 `input / output / constraints` 作为辅助信息
- 从 `limits` 中补充时间与空间限制

## 主流程

单题抽取：

```powershell
python extract.py --input D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs\16_codeforces_1399_e1_weights_division_easy_version.json --output output\single\ --rounds 3 --resume
```

目录批量抽取：

```powershell
python extract.py --input D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs --output output\batch\ --rounds 3 --resume
```

后续处理：

```powershell
python normalize.py --input output\batch\raw\ --output output\batch\normalized\ --embedding-threshold 0.85
python vote.py --input output\batch\normalized\ --output output\batch\voted\
```

## Prompt 验证

```powershell
python verify_prompts_structure.py
```

需要实际调用模型时：

```powershell
python test_prompts_qa.py
```

## 环境要求

- 设置 `DASHSCOPE_API_KEY` 或 `QWEN_API_KEY`
- 输入文件来自 `D:\AutoProblemGen\爬取题目\output\imandra_curated_schema_inputs`
